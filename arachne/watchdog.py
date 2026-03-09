from __future__ import annotations

import os
import signal
import threading
import time
from datetime import datetime, timedelta

import requests
from flask import Flask, jsonify

CHECK_SECONDS = 2 * 60 * 60
LAST_PING = datetime.utcnow()
APP = Flask(__name__)


@APP.route("/ping", methods=["GET"])
def ping():
    global LAST_PING
    LAST_PING = datetime.utcnow()
    return jsonify({"status": "ok", "next_deadline": (LAST_PING + timedelta(seconds=CHECK_SECONDS)).isoformat()})


@APP.route("/status", methods=["GET"])
def status():
    deadline = LAST_PING + timedelta(seconds=CHECK_SECONDS)
    remaining = max(0, int((deadline - datetime.utcnow()).total_seconds()))
    return jsonify(
        {
            "last_ping_iso": LAST_PING.isoformat(),
            "seconds_remaining": remaining,
            "deadline_iso": deadline.isoformat(),
        }
    )


def stop_codespace() -> None:
    repo = os.environ.get("GITHUB_REPOSITORY")
    codespace = os.environ.get("CODESPACE_NAME")
    token = os.environ.get("GITHUB_TOKEN")
    if not (repo and codespace and token):
        return
    requests.post(
        f"https://api.github.com/repos/{repo}/codespaces/{codespace}/stop",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
        timeout=15,
    )


def monitor() -> None:
    while True:
        if datetime.utcnow() - LAST_PING > timedelta(seconds=CHECK_SECONDS):
            stop_codespace()
            os.kill(os.getpid(), signal.SIGTERM)
        time.sleep(30)


if __name__ == "__main__":
    threading.Thread(target=monitor, daemon=True).start()
    APP.run(host="127.0.0.1", port=9999)
