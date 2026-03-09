from __future__ import annotations

import re
import time
from collections import Counter

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

    @app.post("/api/ingest")
    def api_ingest():
        text = request.json.get("text", "")
        if not text:
            return jsonify({"error": "no text provided"})

        sentences = re.split(r"[.!?]+", text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 10]

        total_triples = []
        total_entities = []

        for sentence in sentences[:50]:  # cap at 50 sentences
            try:
                result = state.handle_message(sentence)
                total_triples.extend(result.get("triples", []))
                total_entities.extend(state.parser.parse(sentence).entities)
            except Exception:
                continue

        return jsonify(
            {
                "sentences_processed": len(sentences),
                "triples_extracted": len(total_triples),
                "entities_found": list(set(total_entities))[:20],
                "message": f"Ingested {len(sentences)} sentences. {len(total_triples)} facts added to working memory.",
            }
        )

    @app.get("/api/graph")
    def api_graph():
        facts = state.clips.fetch_facts()
        nodes = set()
        edges = []
        for f in facts:
            txt = f.get("text", "")
            if not txt.startswith("(relation"):
                continue
            subj = re.search(r'\(subject "([^"]+)"\)', txt)
            pred = re.search(r'\(predicate "([^"]+)"\)', txt)
            obj = re.search(r'\(object "([^"]+)"\)', txt)
            conf = re.search(r"\(confidence ([0-9.]+)\)", txt)
            if subj and pred and obj:
                s, p, o = subj.group(1), pred.group(1), obj.group(1)
                nodes.add(s)
                nodes.add(o)
                edges.append(
                    {
                        "source": s,
                        "target": o,
                        "predicate": p,
                        "confidence": float(conf.group(1)) if conf else 0.5,
                    }
                )
        return jsonify({"nodes": [{"id": n} for n in list(nodes)[:100]], "edges": edges[:200]})

    @app.get("/api/analytics")
    def api_analytics():
        facts = state.clips.fetch_facts()
        predicates = []
        for f in facts:
            txt = f.get("text", "")
            if txt.startswith("(relation"):
                m = re.search(r'\(predicate "([^"]+)"\)', txt)
                if m:
                    predicates.append(m.group(1))
        top_predicates = Counter(predicates).most_common(5)
        return jsonify(
            {
                "total_facts": len(facts),
                "total_rules": len(state.clips.fetch_rules()),
                "ilp_events_session": state.ilp_events,
                "top_predicates": [{"predicate": p, "count": c} for p, c in top_predicates],
                "nars_store_size": len(state.nars.all_scores()),
                "session_uptime_seconds": int(time.time() - state._start_time),
            }
        )

    return app
