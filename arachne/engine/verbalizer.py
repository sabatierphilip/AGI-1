from __future__ import annotations

from typing import Dict, List


class Verbalizer:
    def verbalize(self, conclusions: List[Dict[str, str]], templates: Dict[str, str]) -> List[Dict[str, str]]:
        output = []
        for c in conclusions:
            text = c.get("text", "")
            trace_id = c.get("trace-id", "unknown")
            if text in templates:
                output.append({"message": templates[text], "trace": trace_id})
            else:
                output.append({"message": "I have a conclusion but no verbalization rule for it yet", "trace": trace_id, "raw": text})
        return output
