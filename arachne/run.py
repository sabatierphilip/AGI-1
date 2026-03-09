from __future__ import annotations

import json
import subprocess
import threading
import webbrowser
from pathlib import Path

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
            self.new_rule_flash = 3
            title = f"[ARACHNE] Rule induction: {evt.signature}"
            body = (
                f"Pattern triggered induction: {evt.signature}\n"
                f"Support count: {evt.support}\n"
                f"NARS confidence: {evt.confidence}\n"
                f"Accepted: {evt.accepted}\n\n"
                f"Working memory sample:\n{json.dumps(self.clips.fetch_facts()[:10], indent=2)}\n\n"
                f"Git diff:\n{git_diff()}"
            )
            print(title)
            print(body[:600])

        self.ilp = ILPEngine(self.clips.fetch_facts, self.clips.add_rule_runtime, on_event)
        self.ilp.start()

    def _ingest_source_facts(self, entities: list[str]) -> None:
        for ent in entities[:2]:
            for fact in query_entity_relations(ent)[:2]:
                self._assert_relation_fact(fact)
            for fact in enrich_concept(ent)[:2]:
                self._assert_relation_fact(fact)
            for fact in lexical_relations(ent)[:2]:
                self._assert_relation_fact(fact)

    def _assert_relation_fact(self, fact: dict) -> None:
        expr = (
            f'(relation (subject "{fact["subject"]}") (predicate "{fact["predicate"]}") '
            f'(object "{fact["object"]}") (confidence {round(float(fact["confidence"]), 2)}))'
        )
        self.clips.assert_fact(expr, confidence=fact["confidence"], source=fact["source"])

    def handle_message(self, message: str) -> dict:
        parsed = self.parser.parse(message)
        self.clips.assert_fact(f'(intent (type "{parsed.intent}") (text "{message}"))', confidence=0.8)
        for triple in parsed.triples:
            expr = (
                f'(relation (subject "{triple["subject"]}") (predicate "{triple["predicate"]}") '
                f'(object "{triple["object"]}") (confidence 0.7))'
            )
            self.clips.assert_fact(expr, confidence=0.7)
        try:
            self._ingest_source_facts(parsed.entities)
        except Exception:
            pass
        self.clips.run(200)

        conclusions = []
        templates = {}
        for fact in self.clips.fetch_facts():
            txt = fact["text"]
            if txt.startswith("(conclusion"):
                text = txt.split('(text "', 1)[1].split('"', 1)[0] if '(text "' in txt else txt
                trace = txt.split('(trace-id "', 1)[1].split('"', 1)[0] if '(trace-id "' in txt else "unknown"
                conclusions.append({"text": text, "trace-id": trace})
            if txt.startswith("(verbalization-template"):
                p = txt.split('(pattern "', 1)[1].split('"', 1)[0]
                t = txt.split('(template "', 1)[1].rsplit('")', 1)[0]
                templates[p] = t
        messages = self.verbalizer.verbalize(conclusions[-3:] if conclusions else [{"text": "no-conclusion", "trace-id": "none"}], templates)
        self.new_rule_flash = max(0, self.new_rule_flash - 1)
        return {"messages": messages, "intent": parsed.intent, "triples": parsed.triples}

    def snapshot(self) -> dict:
        rules = self.clips.fetch_rules()
        return {
            "rule_count": len(rules),
            "ilp_events": self.ilp_events,
            "sources_active": len(self.sources_active),
            "watchdog_seconds": self.watchdog_seconds,
            "rules": rules[:200],
            "new_rule_flash": self.new_rule_flash,
        }


def start_watchdog() -> subprocess.Popen:
    return subprocess.Popen(["python", "watchdog.py"], cwd=str(BASE))


def main() -> None:
    score = run_imo_suite(lambda prompt: "not" not in prompt.lower())
    maybe_write_gate(score, BASE / "imo_gate.json")

    watchdog_proc = start_watchdog()
    state = ArachneState()

    print("=== ARACHNE Startup Report ===")
    print(f"rules_loaded={state.snapshot()['rule_count']}")
    print(f"data_sources_connected={','.join(state.sources_active)}")
    print(f"watchdog_pid={watchdog_proc.pid}")

    app = create_app(state)

    threading.Timer(1.5, lambda: webbrowser.open("http://localhost:5000")).start()
    app.run(host="0.0.0.0", port=5000)


if __name__ == "__main__":
    main()
