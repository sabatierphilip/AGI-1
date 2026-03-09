from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, Tuple


@dataclass
class TruthValue:
    frequency: float
    confidence: float
    source: str = "internal"
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def age_days(self) -> float:
        return (time.time() - self.timestamp) / 86400.0

    def decayed_confidence(self, decay_rate: float = 0.01) -> float:
        decay = self.age_days() * decay_rate
        return max(0.3, self.confidence - decay)

    def reinforce(self, amount: float = 0.05) -> "TruthValue":
        self.confidence = min(1.0, self.confidence + amount)
        self.frequency = min(1.0, self.frequency + amount / 2)
        self.timestamp = time.time()
        return self

    def contradict(self, amount: float = 0.1) -> "TruthValue":
        self.confidence = max(0.0, self.confidence - amount)
        self.frequency = max(0.0, self.frequency - amount / 2)
        self.timestamp = time.time()
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
        accepted = tv.decayed_confidence() >= self.threshold
        return accepted, tv

    def all_scores(self) -> Dict[str, TruthValue]:
        return self._store

    def save(self, path: str | Path) -> None:
        target = Path(path)
        payload = {k: asdict(v) for k, v in self._store.items()}
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def load(self, path: str | Path) -> None:
        target = Path(path)
        if not target.exists():
            return
        raw = json.loads(target.read_text(encoding="utf-8"))
        self._store = {
            k: TruthValue(
                frequency=float(v.get("frequency", 0.5)),
                confidence=float(v.get("confidence", 0.5)),
                source=v.get("source", "internal"),
                timestamp=float(v.get("timestamp", 0.0)),
            )
            for k, v in raw.items()
        }
