from __future__ import annotations

import json
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import requests

from benchmarks.imo_suite import maybe_write_gate, run_imo_suite
from engine.bert_parser import BertParser
from engine.clips_engine import ClipsEngine
from engine.ilp import ILPEngine, InductionEvent
from engine.nars import NARSMemory
from engine.verbalizer import Verbalizer
from interface.app import create_app
from self_modify.diff_generator import git_diff
from sources.conceptnet import enrich_concept
from sources.wikidata import query_entity_relations
from sources.wordnet import lexical_relations

BASE = Path(__file__).resolve().parent


class ArachneState:
    def __init__(self) -> None:
        self.nars = NARSMemory(threshold=0.6)
        self.nars.load(BASE / "nars_memory.json")
        self.clips = ClipsEngine(BASE / "rulebase.clp", self.nars)
        self.parser = BertParser()
        self.verbalizer = Verbalizer()
        self.ilp_events = 0
        self.last_inductions: list[InductionEvent] = []
        self.sources_active = ["wikidata", "conceptnet", "wordnet"]
        self.watchdog_seconds = 7200
        self.new_rule_flash = 0
        self._start_ilp()

    def _start_ilp(self) -> None:
        def on_event(evt: InductionEvent) -> None:
            self.ilp_events += 1
            self.last_inductions.append(evt)
            self.last_inductions = self.last_inductions[-20:]
            self.new_rule_flash = 3
            print(f"[ARACHNE] Rule induction: {evt.signature} support={evt.support} accepted={evt.accepted}")
            print(git_diff()[:500])

        self.ilp = ILPEngine(self.clips.fetch_facts, self.clips.add_rule_runtime, on_event, fetch_rules=self.clips.fetch_rules)
        self.ilp.start()

    def stop(self) -> None:
        self.ilp.stop()
        self.nars.save(BASE / "nars_memory.json")

    @staticmethod
    def _sanitize_value(text: str) -> str:
        return text.replace('"', "'").replace("\\", "").strip()[:200]

    def _ingest_source_facts(self, entities: list[str]) -> None:
        for ent in entities[:2]:
            for fact in query_entity_relations(ent)[:2]:
                self._assert_relation_fact(fact)
            for fact in enrich_concept(ent)[:2]:
                self._assert_relation_fact(fact)
            for fact in lexical_relations(ent)[:2]:
                self._assert_relation_fact(fact)

    def _assert_relation_fact(self, fact: dict) -> None:
        subject = self._sanitize_value(str(fact["subject"]))
        predicate = self._sanitize_value(str(fact["predicate"]))
        obj = self._sanitize_value(str(fact["object"]))
        expr = (
            f'(relation (subject "{subject}") (predicate "{predicate}") '
            f'(object "{obj}") (confidence {round(float(fact["confidence"]), 2)}))'
        )
        self.clips.assert_fact(expr, confidence=fact["confidence"], source=fact["source"])

    def _poll_watchdog(self) -> None:
        try:
            res = requests.get("http://127.0.0.1:9999/status", timeout=2)
            if res.ok:
                self.watchdog_seconds = int(res.json().get("seconds_remaining", self.watchdog_seconds))
        except Exception:
            pass

    def handle_message(self, message: str) -> dict:
        safe_message = self._sanitize_value(message)
        parsed = self.parser.parse(safe_message)
        self.clips.assert_fact(f'(intent (type "{parsed.intent}") (text "{safe_message}"))', confidence=0.8)
        for triple in parsed.triples:
            s = self._sanitize_value(triple["subject"])
            p = self._sanitize_value(triple["predicate"])
            o = self._sanitize_value(triple["object"])
            expr = f'(relation (subject "{s}") (predicate "{p}") (object "{o}") (confidence 0.7))'
            self.clips.assert_fact(expr, confidence=0.7)
        try:
            self._ingest_source_facts(parsed.entities)
        except Exception:
            pass
        self.clips.run(200)

        all_facts = self.clips.fetch_facts()
        conclusions = []
        templates = {}
        relation_facts = []
        for fact in all_facts:
            txt = fact["text"]
            if txt.startswith("(conclusion"):
                text = txt.split('(text "', 1)[1].split('"', 1)[0] if '(text "' in txt else txt
                trace = txt.split('(trace-id "', 1)[1].split('"', 1)[0] if '(trace-id "' in txt else "unknown"
                conclusions.append({"text": text, "trace-id": trace})
            elif txt.startswith("(verbalization-template"):
                p = txt.split('(pattern "', 1)[1].split('"', 1)[0]
                t = txt.split('(template "', 1)[1].rsplit('")', 1)[0]
                templates[p] = t
            elif txt.startswith("(relation"):
                relation_facts.append(fact)

        messages = self.verbalizer.verbalize(
            conclusions[-3:],
            templates,
            facts=relation_facts,
            intent=parsed.intent,
            original_text=safe_message,
        )
        self._poll_watchdog()
        self.new_rule_flash = max(0, self.new_rule_flash - 1)
        return {"messages": messages, "intent": parsed.intent, "triples": parsed.triples}

    def snapshot(self) -> dict:
        self._poll_watchdog()
        rules = sorted(self.clips.fetch_rules(), key=lambda r: r.get("confidence", 0), reverse=True)
        induction_log = [
            {
                "ts": datetime.utcnow().isoformat(timespec="seconds"),
                "signature": e.signature,
                "support": e.support,
                "accepted": e.accepted,
            }
            for e in self.last_inductions[-3:]
        ]
        return {
            "rule_count": len(rules),
            "ilp_events": self.ilp_events,
            "sources_active": len(self.sources_active),
            "watchdog_seconds": self.watchdog_seconds,
            "rules": rules[:200],
            "new_rule_flash": self.new_rule_flash,
            "induction_log": induction_log,
        }


def start_watchdog() -> subprocess.Popen:
    return subprocess.Popen(["python", "watchdog.py"], cwd=str(BASE))


def _ensure_readme() -> None:
    readme = BASE / "README.md"
    if readme.exists():
        return
    readme.write_text(
        "# ARACHNE\n\n"
        "Start with `python run.py`.\n"
        "Watchdog heartbeat endpoint: `GET http://127.0.0.1:9999/ping`\n"
        "Status endpoint: `GET http://127.0.0.1:9999/status`.\n",
        encoding="utf-8",
    )


def _print_banner(state: ArachneState, watchdog_pid: int) -> None:
    snap = state.snapshot()
    print("┌──────────────────────────────────────────────────────────────┐")
    print("│ ARACHNE v1.0 Startup                                         │")
    print(f"│ rules loaded: {snap['rule_count']:<47}│")
    print(f"│ sources connected: {','.join(state.sources_active):<41}│")
    print(f"│ watchdog pid: {watchdog_pid:<48}│")
    print("│ url: http://localhost:5000                                   │")
    print("└──────────────────────────────────────────────────────────────┘")


def main() -> None:
    score = run_imo_suite(None)
    maybe_write_gate(score, BASE / "imo_gate.json")
    _ensure_readme()

    watchdog_proc = start_watchdog()
    state = ArachneState()
    _print_banner(state, watchdog_proc.pid)
    app = create_app(state)

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    try:
        app.run(host="0.0.0.0", port=5000)
    except KeyboardInterrupt:
        print("ARACHNE shutdown cleanly")
    finally:
        state.stop()
        if watchdog_proc.poll() is None:
            watchdog_proc.terminate()
            time.sleep(0.2)


if __name__ == "__main__":
    main()
