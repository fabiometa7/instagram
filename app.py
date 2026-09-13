import os
from pathlib import Path

from flask import Flask, jsonify, render_template, request

import analytics
import graph_api
from db import init_db
from scraper import fetch as scraper_fetch

DEFAULT_USER = os.environ.get("IG_USERNAME", "fabiometa_")

app = Flask(__name__, template_folder="templates", static_folder="static")
init_db()


@app.route("/")
def home():
    return render_template("index.html", username=DEFAULT_USER)


@app.route("/api/refresh", methods=["POST"])
def refresh():
    username = request.json.get("username", DEFAULT_USER) if request.is_json else DEFAULT_USER
    max_posts = int((request.json or {}).get("max_posts", 50)) if request.is_json else 50
    try:
        if graph_api.enabled():
            profile, saved = graph_api.fetch(username, max_posts=max_posts)
            source = "graph_api"
        else:
            profile, saved = scraper_fetch(username, max_posts=max_posts)
            source = "public_scrape"
        return jsonify({"ok": True, "source": source, "profile": profile, "posts_saved": saved})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.route("/api/summary")
def summary():
    username = request.args.get("username", DEFAULT_USER)
    return jsonify(analytics.summary(username))


@app.route("/api/recent")
def recent():
    username = request.args.get("username", DEFAULT_USER)
    limit = int(request.args.get("limit", 5))
    return jsonify(analytics.recent_posts(username, limit=limit))


@app.route("/api/insights")
def insights():
    username = request.args.get("username", DEFAULT_USER)
    limit = int(request.args.get("limit", 50))
    return jsonify(analytics.insights(username, limit=limit))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(host="127.0.0.1", port=port, debug=False)
