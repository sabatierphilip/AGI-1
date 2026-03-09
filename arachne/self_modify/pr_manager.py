from __future__ import annotations

import base64
import os
import random
from datetime import datetime
from pathlib import Path

import requests


class PRManager:
    def __init__(self, repo: str) -> None:
        self.repo = repo
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}

    def open_pr(self, title: str, body: str, rulebase_path: str | Path = "arachne/rulebase.clp") -> dict:
        if not self.token:
            return {"status": "skipped", "step": "auth", "reason": "missing GITHUB_TOKEN"}

        try:
            default_res = requests.get(
                f"https://api.github.com/repos/{self.repo}",
                headers=self.headers,
                timeout=15,
            )
            if default_res.status_code >= 300:
                return {"status": "failed", "step": "get_repo_info", "reason": default_res.text}
            default_branch = default_res.json().get("default_branch", "main")

            ref_res = requests.get(
                f"https://api.github.com/repos/{self.repo}/git/refs/heads/{default_branch}",
                headers=self.headers,
                timeout=15,
            )
            if ref_res.status_code >= 300:
                return {"status": "failed", "step": "get_base_sha", "reason": ref_res.text}
            base_sha = ref_res.json().get("object", {}).get("sha")

            branch = f"arachne-rules-{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"
            create_branch_res = requests.post(
                f"https://api.github.com/repos/{self.repo}/git/refs",
                headers=self.headers,
                json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                timeout=15,
            )
            if create_branch_res.status_code == 422:
                branch = f"{branch}-{random.randint(1000, 9999)}"
                create_branch_res = requests.post(
                    f"https://api.github.com/repos/{self.repo}/git/refs",
                    headers=self.headers,
                    json={"ref": f"refs/heads/{branch}", "sha": base_sha},
                    timeout=15,
                )
            if create_branch_res.status_code >= 300:
                return {"status": "failed", "step": "create_branch", "reason": create_branch_res.text}

            rulebase_candidate_paths = [
                "arachne/rulebase.clp",
                "rulebase.clp",
                "AGI-1-main/arachne/rulebase.clp",
            ]
            blob_sha = None
            api_path = None
            for candidate in rulebase_candidate_paths:
                content_res = requests.get(
                    f"https://api.github.com/repos/{self.repo}/contents/{candidate}",
                    headers=self.headers,
                    params={"ref": default_branch},
                    timeout=15,
                )
                if content_res.status_code == 200:
                    blob_sha = content_res.json().get("sha")
                    api_path = candidate
                    break

            if not blob_sha or not api_path:
                return {
                    "status": "failed",
                    "step": "get_rulebase_blob",
                    "reason": f"rulebase.clp not found at any candidate path: {rulebase_candidate_paths}",
                }

            raw = Path(rulebase_path).read_text(encoding="utf-8")
            encoded = base64.b64encode(raw.encode("utf-8")).decode("utf-8")
            commit_res = requests.put(
                f"https://api.github.com/repos/{self.repo}/contents/{api_path}",
                headers=self.headers,
                json={
                    "message": title,
                    "content": encoded,
                    "sha": blob_sha,
                    "branch": branch,
                },
                timeout=15,
            )
            if commit_res.status_code >= 300:
                return {"status": "failed", "step": "commit_rulebase", "reason": commit_res.text}

            safe_body = (body or "")[:60000]
            pr_res = requests.post(
                f"https://api.github.com/repos/{self.repo}/pulls",
                headers=self.headers,
                json={"title": title, "body": safe_body, "head": branch, "base": default_branch},
                timeout=15,
            )
            if pr_res.status_code >= 300:
                return {"status": "failed", "step": "open_pr", "reason": pr_res.text}
            return {"status": "ok", "step": "done", "payload": pr_res.json()}
        except Exception as exc:
            return {"status": "failed", "step": "exception", "reason": str(exc)}
