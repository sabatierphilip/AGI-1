from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass
class TruthValue:
    frequency: float
    confidence: float
    source: str = "internal"

    def reinforce(self, amount: float = 0.05) -> "TruthValue":
        self.confidence = min(1.0, self.confidence + amount)
        self.frequency = min(1.0, self.frequency + amount / 2)
        return self

    def contradict(self, amount: float = 0.1) -> "TruthValue":
        self.confidence = max(0.0, self.confidence - amount)
        self.frequency = max(0.0, self.frequency - amount / 2)
        return self


class NARSMemory:
    def __init__(self, threshold: float = 0.6) -> None:
        self.threshold = threshold
        self._store: Dict[str, TruthValue] = {}

    def set_fact(self, key: str, freq: float, conf: float, source: str = "internal") -> TruthValue:
        tv = TruthValue(freq, conf, source)
        self._store[key] = tv
        return tv

    def get(self, key: str) -> TruthValue | None:
        return self._store.get(key)

    def confirm(self, key: str, amount: float = 0.05) -> TruthValue:
        tv = self._store.setdefault(key, TruthValue(0.5, 0.5))
        return tv.reinforce(amount)

    def contradict(self, key: str, amount: float = 0.1) -> TruthValue:
        tv = self._store.setdefault(key, TruthValue(0.5, 0.5))
        return tv.contradict(amount)

    def gate_rule(self, signature: str, base_confidence: float) -> Tuple[bool, TruthValue]:
        tv = self._store.setdefault(signature, TruthValue(0.5, base_confidence, "ilp"))
        accepted = tv.confidence >= self.threshold
        return accepted, tv

    def all_scores(self) -> Dict[str, TruthValue]:
        return self._store
