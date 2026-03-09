from __future__ import annotations

from pathlib import Path
from typing import Dict, List

import clips

from engine.nars import NARSMemory


class ClipsEngine:
    def __init__(self, rulebase_path: Path, nars: NARSMemory) -> None:
        self.rulebase_path = rulebase_path
        self.nars = nars
        self.env = clips.Environment()
        self.trace_buffer: List[str] = []
        self._bootstrap()

    def _bootstrap(self) -> None:
        self.env.load(str(self.rulebase_path))
        self.env.reset()
        self.assert_fact('(self-state (key "startup") (value "ready"))', confidence=0.8)

    def assert_fact(self, fact_expr: str, confidence: float = 0.7, source: str = "internal") -> None:
        self.env.assert_string(fact_expr)
        self.nars.set_fact(fact_expr, freq=0.7, conf=confidence, source=source)

    def run(self, limit: int = 100) -> int:
        fired = self.env.run(limit)
        self.trace_buffer.append(f"fired={fired}")
        if len(self.trace_buffer) > 250:
            self.trace_buffer = self.trace_buffer[-250:]
        return fired

    def fetch_facts(self) -> List[Dict[str, str]]:
        facts = []
        for fact in self.env.facts():
            facts.append({"id": str(fact.index), "text": str(fact)})
        return facts

    def fetch_rules(self) -> List[Dict[str, str]]:
        rules = []
        for rule in self.env.rules():
            name = rule.name
            score = self.nars.get(name)
            confidence = score.confidence if score else 0.5
            rules.append({"name": name, "definition": str(rule), "confidence": round(confidence, 2)})
        return rules

    def add_rule_runtime(self, rule_text: str, signature: str, confidence: float) -> bool:
        accepted, tv = self.nars.gate_rule(signature, confidence)
        if not accepted:
            self.assert_fact(
                f'(self-state (key "quarantined_rule") (value "{signature}"))',
                confidence=tv.confidence,
                source="ilp",
            )
            return False
        self.env.build(rule_text)
        with self.rulebase_path.open("a", encoding="utf-8") as fh:
            fh.write("\n" + rule_text + "\n")
        self.nars.set_fact(signature, 0.7, tv.confidence, source="ilp")
        return True
