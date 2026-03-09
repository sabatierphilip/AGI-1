from __future__ import annotations

from flask import Flask, jsonify, render_template, request


def create_app(state):
    app = Flask(__name__, template_folder="templates", static_folder="static")

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/state")
    def api_state():
        return jsonify(state.snapshot())

    @app.post("/api/pr-test")
    def api_pr_test():
        import os
        from pathlib import Path

        from self_modify.pr_manager import PRManager

        repo = os.environ.get("GITHUB_REPOSITORY", "")
        if not repo:
            return jsonify({"error": "GITHUB_REPOSITORY not set"})

        pr = PRManager(repo)
        result = pr.open_pr(
            title="[ARACHNE] PR connectivity test",
            body="This is an automated connectivity test from ARACHNE. Safe to close.",
            rulebase_path=str(Path(__file__).resolve().parent.parent / "rulebase.clp"),
        )
        return jsonify(result)

    @app.post("/api/chat")
    def api_chat():
        msg = request.json.get("message", "")
        response = state.handle_message(msg)
        return jsonify(response)

    return app
