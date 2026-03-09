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

    @app.post("/api/chat")
    def api_chat():
        msg = request.json.get("message", "")
        response = state.handle_message(msg)
        return jsonify(response)

    return app
