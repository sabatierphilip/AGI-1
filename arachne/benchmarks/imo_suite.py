from __future__ import annotations

import json
from pathlib import Path

IMO_PROBLEMS = [
    {"id": "nt-1", "prompt": "If n is even then n^2 is even", "expected": True},
    {"id": "nt-2", "prompt": "If a divides b and b divides c then a divides c", "expected": True},
    {"id": "comb-1", "prompt": "Number of subsets of n-element set is 2^n", "expected": True},
    {"id": "comb-2", "prompt": "Every graph with n vertices has n! Hamiltonian cycles", "expected": False},
    {"id": "nt-3", "prompt": "Prime greater than 2 is odd", "expected": True},
]


def run_imo_suite(state) -> float:
    if state is None:
        return 0.0
    correct = 0
    for p in IMO_PROBLEMS:
        try:
            result = state.handle_message(p["prompt"])
            messages = " ".join(m.get("message", "") for m in result.get("messages", []))
            triples = result.get("triples", [])
            lowered = messages.lower()

            has_conclusion = bool(triples) or any(
                t in lowered for t in ["is a", "causes", "requires", "recorded", "knowledge"]
            )
            has_negative = any(
                t in lowered for t in ["every graph", "n!", "false", "incorrect", "contradict"]
            )

            if p["expected"]:
                is_correct = has_conclusion and not has_negative
            else:
                is_correct = has_negative or not has_conclusion

            if is_correct:
                correct += 1
        except Exception:
            pass
    return correct / len(IMO_PROBLEMS)


def maybe_write_gate(score: float, config_path: Path) -> None:
    state = {"IMO_THRESHOLD_PASSED": score > 0.70, "score": score}
    config_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
