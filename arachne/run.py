import importlib
import subprocess
import sys
from pathlib import Path


def _bootstrap() -> None:
    import importlib
    import subprocess
    import sys

    # Install system build dependencies first — needed for clipspy on Python 3.12
    try:
        subprocess.check_call(
            [
                "sudo",
                "apt-get",
                "install",
                "-y",
                "-qq",
                "build-essential",
                "libffi-dev",
                "python3-dev",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass  # not on apt system, continue

    # Core packages excluding clipspy
    required = {
        "flask": "Flask==3.0.3",
        "transformers": "transformers==4.43.4",
        "torch": "torch==2.3.1",
        "requests": "requests==2.32.3",
        "nltk": "nltk==3.9.1",
        "yaml": "PyYAML==6.0.2",
        "huggingface_hub": "huggingface-hub>=0.23.0",
        "safetensors": "safetensors>=0.4.0",
    }
    missing = []
    for module, package in required.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(package)
    if missing:
        print(f"[ARACHNE] Installing {len(missing)} packages...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--quiet", *missing])

    # Install clipspy with multi-strategy fallback for Python 3.12 Codespaces
    try:
        importlib.import_module("clips")
        return
    except ImportError:
        pass

    print("[ARACHNE] Installing clipspy...")
    strategies = [
        # Strategy 1: no-build-isolation fixes clips.h lookup on Python 3.12
        [sys.executable, "-m", "pip", "install", "--quiet", "--no-build-isolation", "clipspy==1.0.0"],
        # Strategy 2: older version with prebuilt wheel
        [sys.executable, "-m", "pip", "install", "--quiet", "clipspy==0.1.1"],
        # Strategy 3: latest available
        [sys.executable, "-m", "pip", "install", "--quiet", "clipspy"],
    ]
    for cmd in strategies:
        try:
            subprocess.check_call(cmd)
            importlib.import_module("clips")
            print("[ARACHNE] clipspy installed successfully.")
            return
        except Exception:
            continue

    print("[ARACHNE] FATAL: Could not install clipspy on any strategy.")
    print(
        "Manual fix: sudo apt-get install build-essential libffi-dev && pip install clipspy --no-build-isolation"
    )
    sys.exit(1)


_bootstrap()

import json
import os
import threading
import time
import webbrowser
from datetime import datetime

import nltk
import requests

for _corpus in ("wordnet", "omw-1.4"):
    try:
        nltk.data.find(f"corpora/{_corpus}")
    except LookupError:
        nltk.download(_corpus, quiet=True)

from benchmarks.imo_suite import maybe_write_gate, run_imo_suite
from engine.bert_parser import BertParser
from engine.clips_engine import ClipsEngine
from engine.ilp import ILPEngine, InductionEvent
from engine.nars import NARSMemory
from engine.verbalizer import Verbalizer
from interface.app import create_app
from self_modify.diff_generator import git_diff
from self_modify.pr_manager import PRManager
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
        self._start_time = time.time()
        self._start_ilp()

    def _start_ilp(self) -> None:
        pending_batch: list[InductionEvent] = []
        batch_lock = threading.Lock()

        def on_event(evt: InductionEvent) -> None:
            with batch_lock:
                self.ilp_events += 1
                self.last_inductions.append(evt)
                self.last_inductions = self.last_inductions[-20:]
                pending_batch.append(evt)
                self.new_rule_flash = min(self.new_rule_flash + 1, 10)

        def flush_batch() -> None:
            while not self.ilp.stop_event.is_set():
                time.sleep(6)
                accepted = []
                all_events = []
                with batch_lock:
                    if not pending_batch:
                        continue
                    accepted = [e for e in pending_batch if e.accepted]
                    all_events = list(pending_batch)
                    pending_batch.clear()

                if not accepted:
                    continue

                rule_lines = []
                for i, evt in enumerate(accepted, 1):
                    rule_lines.append(
                        f"Rule {i}: {evt.signature}\n"
                        f"  Support: {evt.support} | Confidence: {evt.confidence:.2f}"
                    )
                wm_sample = json.dumps(self.clips.fetch_facts()[:10], indent=2)[:3000]
                diff_sample = git_diff()[:4000]
                body = (
                    f"Batch induction — {len(accepted)} rule(s) accepted "
                    f"({len(all_events)} total candidates)\n\n"
                    + "\n\n".join(rule_lines)
                    + f"\n\nWorking memory snapshot (truncated):\n{wm_sample}"
                    + f"\n\nGit diff (truncated):\n{diff_sample}"
                )[:60000]
                title = (
                    f"[ARACHNE] Batch induction: {len(accepted)} rule(s) — "
                    + ", ".join(e.signature for e in accepted[:3])
                    + ("..." if len(accepted) > 3 else "")
                )
                repo = os.environ.get("GITHUB_REPOSITORY", "")
                if repo:
                    try:
                        pr = PRManager(repo)
                        result = pr.open_pr(title, body, rulebase_path=str(BASE / "rulebase.clp"))
                        status = result.get("status")
                        step = result.get("step", "unknown")
                        reason = result.get("reason", "")
                        if status == "ok":
                            pr_url = result.get("payload", {}).get("html_url", "unknown")
                            print(f"[ARACHNE] PR opened: {pr_url}")
                        else:
                            print(f"[ARACHNE] PR failed at step={step}: {reason[:500]}")
                    except Exception as exc:
                        print(f"[ARACHNE] PR publish failed: {exc}")
                else:
                    print(f"[ARACHNE] {title}")

        self.ilp = ILPEngine(
            self.clips.fetch_facts,
            self.clips.add_rule_runtime,
            on_event,
            fetch_rules=self.clips.fetch_rules,
        )
        self.ilp.start()
        threading.Thread(target=flush_batch, daemon=True).start()

    def stop(self) -> None:
        self.ilp.stop()
        self.nars.save(BASE / "nars_memory.json")

    @staticmethod
    def _sanitize_value(text: str) -> str:
        return text.replace('"', "'").replace("\\", "").strip()[:200]

    def _ingest_source_facts(self, entities: list[str]) -> None:
        for ent in entities[:2]:
            try:
                for fact in query_entity_relations(ent)[:2]:
                    self._assert_relation_fact(fact)
            except Exception as exc:
                print(f"[ARACHNE] Wikidata ingestion failed: {exc}")
            try:
                for fact in enrich_concept(ent)[:2]:
                    self._assert_relation_fact(fact)
            except Exception as exc:
                print(f"[ARACHNE] ConceptNet ingestion failed: {exc}")
            try:
                for fact in lexical_relations(ent)[:2]:
                    self._assert_relation_fact(fact)
            except Exception as exc:
                print(f"[ARACHNE] WordNet ingestion failed: {exc}")

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
        except Exception as exc:
            print(f"[ARACHNE] Watchdog poll failed: {exc}")

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
        except Exception as exc:
            print(f"[ARACHNE] Source ingestion failed: {exc}")
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
    return subprocess.Popen([sys.executable, "watchdog.py"], cwd=str(BASE))


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
    induced = len([r for r in snap["rules"] if r["name"].startswith("induced-")])
    seeded = snap["rule_count"] - induced
    print("")
    print("╔══════════════════════════════════════════════════════════════════╗")
    print("║                    ARACHNE v1.0  ONLINE                         ║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print(f"║  Rules loaded    : {snap['rule_count']:<46}║")
    print(f"║  Pre-seeded      : {seeded:<46}║")
    print(f"║  Induced (learned): {induced:<45}║")
    print(f"║  Sources active  : {','.join(state.sources_active):<46}║")
    print(f"║  Watchdog PID    : {watchdog_pid:<46}║")
    print(f"║  Interface       : http://localhost:5000{'':<26}║")
    print("╠══════════════════════════════════════════════════════════════════╣")
    print("║  CLIPS + NARS + ILP + BERT  |  Self-modifying symbolic AGI      ║")
    print("╚══════════════════════════════════════════════════════════════════╝")
    print("")


def main() -> None:
    _ensure_readme()
    watchdog_proc = start_watchdog()

    state = ArachneState()

    score = run_imo_suite(state)
    maybe_write_gate(score, BASE / "imo_gate.json")
    print(f"[ARACHNE] IMO score: {score:.2f} | gate={'OPEN' if score > 0.70 else 'CLOSED'}")

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
