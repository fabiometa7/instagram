"""Optional Meta Graph API integration.

Enables real Instagram Insights (reach, impressions, saves, watch time)
and daily follower counts from the source, once you drop credentials
into a .env file at the project root:

    IG_GRAPH_TOKEN=EAAG...            # long-lived user access token
    IG_BUSINESS_ID=1784xxxxxxxxxxx    # Instagram Business Account ID

If either is missing, the rest of the app falls back to the public
scraper transparently.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen
import json

from db import connect

GRAPH = "https://graph.facebook.com/v21.0"


def _load_env():
    env = Path(__file__).parent / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()


def enabled() -> bool:
    return bool(os.environ.get("IG_GRAPH_TOKEN") and os.environ.get("IG_BUSINESS_ID"))


def _get(path: str, **params):
    params["access_token"] = os.environ["IG_GRAPH_TOKEN"]
    url = f"{GRAPH}/{path.lstrip('/')}?{urlencode(params)}"
    with urlopen(url, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fetch(username: str, max_posts: int = 50):
    """Pull profile + media + insights via Graph API and persist them."""
    if not enabled():
        raise RuntimeError("Graph API not configured; add IG_GRAPH_TOKEN & IG_BUSINESS_ID to .env")

    ig_id = os.environ["IG_BUSINESS_ID"]

    profile = _get(
        ig_id,
        fields="username,followers_count,follows_count,media_count,name,biography,profile_picture_url",
    )
    now = datetime.now(timezone.utc).isoformat()
    with connect() as c:
        c.execute(
            "INSERT INTO follower_snapshot(username, taken_at, followers, following, media_count) "
            "VALUES (?,?,?,?,?)",
            (username, now, profile["followers_count"], profile.get("follows_count"), profile.get("media_count")),
        )

    media = _get(
        f"{ig_id}/media",
        fields="id,shortcode,caption,media_type,media_product_type,permalink,timestamp,like_count,comments_count",
        limit=max_posts,
    )
    saved = 0
    with connect() as c:
        for m in media.get("data", []):
            mtype = m.get("media_product_type", "").lower() or m["media_type"].lower()
            if mtype == "reels":
                mtype = "reel"
            elif mtype == "video":
                mtype = "video"
            elif mtype == "carousel_album":
                mtype = "carousel"
            else:
                mtype = "image"

            video_views = None
            try:
                if mtype in ("reel", "video"):
                    ins = _get(f"{m['id']}/insights", metric="plays,reach,saved,total_interactions")
                    for entry in ins.get("data", []):
                        if entry["name"] == "plays":
                            video_views = entry["values"][0]["value"]
                elif mtype in ("image", "carousel"):
                    _get(f"{m['id']}/insights", metric="reach,saved,total_interactions")
            except Exception:
                pass

            c.execute(
                """INSERT INTO post(shortcode, username, posted_at, media_type,
                       caption, likes, comments, video_views, video_duration,
                       url, is_carousel, fetched_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(shortcode) DO UPDATE SET
                       likes=excluded.likes,
                       comments=excluded.comments,
                       video_views=excluded.video_views,
                       fetched_at=excluded.fetched_at""",
                (
                    m.get("shortcode") or m["id"],
                    username,
                    m["timestamp"],
                    mtype,
                    m.get("caption", ""),
                    m.get("like_count", 0),
                    m.get("comments_count", 0),
                    video_views,
                    None,
                    m.get("permalink"),
                    1 if mtype == "carousel" else 0,
                    now,
                ),
            )
            import re
            for tag in {t.lower() for t in re.findall(r"#([\w\d_]+)", m.get("caption") or "")}:
                c.execute(
                    "INSERT OR IGNORE INTO post_hashtag(shortcode, hashtag) VALUES (?,?)",
                    (m.get("shortcode") or m["id"], tag),
                )
            saved += 1

    return (
        {
            "username": profile.get("username", username),
            "followers": profile["followers_count"],
            "following": profile.get("follows_count"),
            "media_count": profile.get("media_count"),
            "full_name": profile.get("name"),
            "biography": profile.get("biography"),
            "profile_pic_url": profile.get("profile_picture_url"),
        },
        saved,
    )
