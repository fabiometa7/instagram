from __future__ import annotations

import re
from datetime import datetime, timezone
from itertools import islice

import instaloader

from db import connect

HASHTAG_RE = re.compile(r"#([\w\d_]+)", re.UNICODE)


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _media_type(post):
    if post.typename == "GraphVideo" or post.is_video:
        return "reel" if getattr(post, "product_type", "") == "clips" else "video"
    if post.typename == "GraphSidecar":
        return "carousel"
    return "image"


def fetch(username: str, max_posts: int = 50, session_file: str | None = None):
    """Scrape a public profile + its most recent posts and persist them.

    Returns (profile_summary_dict, posts_saved).
    """
    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        quiet=True,
    )
    if session_file:
        try:
            L.load_session_from_file(username, session_file)
        except Exception:
            pass

    profile = instaloader.Profile.from_username(L.context, username)

    with connect() as c:
        c.execute(
            "INSERT INTO follower_snapshot(username, taken_at, followers, following, media_count) "
            "VALUES (?,?,?,?,?)",
            (
                username,
                _now_iso(),
                profile.followers,
                profile.followees,
                profile.mediacount,
            ),
        )

    saved = 0
    with connect() as c:
        for post in islice(profile.get_posts(), max_posts):
            shortcode = post.shortcode
            media = _media_type(post)
            hashtags = HASHTAG_RE.findall(post.caption or "")
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
                    shortcode,
                    username,
                    post.date_utc.replace(tzinfo=timezone.utc).isoformat(),
                    media,
                    post.caption,
                    post.likes,
                    post.comments,
                    post.video_view_count if post.is_video else None,
                    post.video_duration if post.is_video else None,
                    f"https://www.instagram.com/p/{shortcode}/",
                    1 if media == "carousel" else 0,
                    _now_iso(),
                ),
            )
            c.execute("DELETE FROM post_hashtag WHERE shortcode = ?", (shortcode,))
            for tag in {t.lower() for t in hashtags}:
                c.execute(
                    "INSERT OR IGNORE INTO post_hashtag(shortcode, hashtag) VALUES (?,?)",
                    (shortcode, tag),
                )
            saved += 1

    return (
        {
            "username": username,
            "followers": profile.followers,
            "following": profile.followees,
            "media_count": profile.mediacount,
            "full_name": profile.full_name,
            "biography": profile.biography,
            "profile_pic_url": profile.profile_pic_url,
        },
        saved,
    )
