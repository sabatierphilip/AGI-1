from __future__ import annotations

import os
import requests


class PRManager:
    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.token = os.environ.get("GITHUB_TOKEN", "")

    def open_pr(self, title: str, body: str, head: str, base: str = "main") -> dict:
        if not self.token:
            return {"status": "skipped", "reason": "missing GITHUB_TOKEN"}
        response = requests.post(
            f"https://api.github.com/repos/{self.repo}/pulls",
            headers={"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"},
            json={"title": title, "body": body, "head": head, "base": base},
            timeout=15,
        )
        return {"status": response.status_code, "payload": response.json()}
