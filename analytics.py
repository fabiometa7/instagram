from __future__ import annotations

from datetime import datetime, timedelta, timezone
from collections import Counter, defaultdict

from db import connect

WINDOWS = [7, 30, 60, 90]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _parse(dt: str) -> datetime:
    # Graph API sends "+0000" (no colon); Python <3.11's fromisoformat needs "+00:00".
    if len(dt) >= 5 and dt[-5] in "+-" and dt[-3] != ":":
        dt = dt[:-2] + ":" + dt[-2:]
    # Strip fractional-seconds Z if present, etc.
    if dt.endswith("Z"):
        dt = dt[:-1] + "+00:00"
    return datetime.fromisoformat(dt)


def summary(username: str):
    with connect() as c:
        rows = c.execute(
            "SELECT taken_at, followers FROM follower_snapshot "
            "WHERE username=? ORDER BY taken_at ASC",
            (username,),
        ).fetchall()

    if not rows:
        return {
            "username": username,
            "current_followers": None,
            "snapshots": 0,
            "windows": {str(d): None for d in WINDOWS},
            "history": [],
        }

    current = rows[-1]["followers"]
    now = _parse(rows[-1]["taken_at"])
    windows = {}
    for d in WINDOWS:
        cutoff = now - timedelta(days=d)
        past = None
        for r in rows:
            if _parse(r["taken_at"]) <= cutoff:
                past = r["followers"]
            else:
                break
        # If no snapshot old enough, fall back to the oldest we have.
        if past is None and rows:
            oldest = rows[0]
            past = oldest["followers"] if _parse(oldest["taken_at"]) < now else None
        windows[str(d)] = {
            "delta": (current - past) if past is not None else None,
            "from": past,
            "to": current,
            "has_full_window": past is not None
            and _parse(rows[0]["taken_at"]) <= cutoff,
        }

    return {
        "username": username,
        "current_followers": current,
        "snapshots": len(rows),
        "windows": windows,
        "history": [
            {"t": r["taken_at"], "followers": r["followers"]} for r in rows
        ],
    }


def _engagement(row, followers):
    if not followers:
        return 0.0
    likes = row["likes"] or 0
    comments = row["comments"] or 0
    return (likes + comments) / followers * 100.0


def _post_dict(row, followers):
    return {
        "shortcode": row["shortcode"],
        "url": row["url"],
        "posted_at": row["posted_at"],
        "media_type": row["media_type"],
        "caption": (row["caption"] or "").strip(),
        "likes": row["likes"] or 0,
        "comments": row["comments"] or 0,
        "video_views": row["video_views"],
        "video_duration": row["video_duration"],
        "engagement_rate": round(_engagement(row, followers), 3),
    }


def _current_followers(username: str) -> int | None:
    with connect() as c:
        r = c.execute(
            "SELECT followers FROM follower_snapshot WHERE username=? "
            "ORDER BY taken_at DESC LIMIT 1",
            (username,),
        ).fetchone()
    return r["followers"] if r else None


def recent_posts(username: str, limit: int = 5):
    followers = _current_followers(username) or 0
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM post WHERE username=? ORDER BY posted_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
    return [_post_dict(r, followers) for r in rows]


def insights(username: str, limit: int = 50):
    followers = _current_followers(username) or 0
    with connect() as c:
        rows = c.execute(
            "SELECT * FROM post WHERE username=? ORDER BY posted_at DESC LIMIT ?",
            (username, limit),
        ).fetchall()
        tag_rows = c.execute(
            "SELECT p.shortcode, p.likes, p.comments, h.hashtag "
            "FROM post p JOIN post_hashtag h ON p.shortcode = h.shortcode "
            "WHERE p.username=? "
            "AND p.shortcode IN (SELECT shortcode FROM post WHERE username=? "
            "                    ORDER BY posted_at DESC LIMIT ?)",
            (username, username, limit),
        ).fetchall()

    if not rows:
        return {
            "post_count": 0,
            "by_media_type": [],
            "by_day": [],
            "by_hour": [],
            "top_hashtags": [],
            "top_posts": [],
            "recommendations": ["Refresh once you have posts on the account."],
        }

    # By media type
    mt_bucket = defaultdict(list)
    for r in rows:
        mt_bucket[r["media_type"]].append(r)
    by_media_type = []
    for mt, items in mt_bucket.items():
        er = sum(_engagement(x, followers) for x in items) / len(items)
        by_media_type.append(
            {
                "media_type": mt,
                "count": len(items),
                "avg_engagement_rate": round(er, 3),
                "avg_likes": round(sum((x["likes"] or 0) for x in items) / len(items), 1),
                "avg_comments": round(
                    sum((x["comments"] or 0) for x in items) / len(items), 1
                ),
                "avg_video_views": (
                    round(
                        sum((x["video_views"] or 0) for x in items if x["video_views"])
                        / max(1, sum(1 for x in items if x["video_views"])),
                        0,
                    )
                    if any(x["video_views"] for x in items)
                    else None
                ),
            }
        )
    by_media_type.sort(key=lambda x: x["avg_engagement_rate"], reverse=True)

    # By day-of-week and hour-of-day (local: use UTC as-is; user can adjust)
    day_bucket = defaultdict(list)
    hour_bucket = defaultdict(list)
    for r in rows:
        t = _parse(r["posted_at"])
        day_bucket[t.weekday()].append(r)
        hour_bucket[t.hour].append(r)

    by_day = []
    for i in range(7):
        items = day_bucket.get(i, [])
        if items:
            er = sum(_engagement(x, followers) for x in items) / len(items)
            by_day.append(
                {"day": DAY_NAMES[i], "count": len(items), "avg_engagement_rate": round(er, 3)}
            )
        else:
            by_day.append({"day": DAY_NAMES[i], "count": 0, "avg_engagement_rate": 0.0})

    by_hour = []
    for h in range(24):
        items = hour_bucket.get(h, [])
        if items:
            er = sum(_engagement(x, followers) for x in items) / len(items)
            by_hour.append(
                {"hour": h, "count": len(items), "avg_engagement_rate": round(er, 3)}
            )
        else:
            by_hour.append({"hour": h, "count": 0, "avg_engagement_rate": 0.0})

    # Hashtag performance
    tag_engagement = defaultdict(list)
    for tr in tag_rows:
        tag_engagement[tr["hashtag"]].append(
            ((tr["likes"] or 0) + (tr["comments"] or 0)) / followers * 100.0
            if followers
            else 0.0
        )
    top_hashtags = [
        {
            "hashtag": tag,
            "uses": len(vals),
            "avg_engagement_rate": round(sum(vals) / len(vals), 3),
        }
        for tag, vals in tag_engagement.items()
        if len(vals) >= 2
    ]
    top_hashtags.sort(key=lambda x: x["avg_engagement_rate"], reverse=True)
    top_hashtags = top_hashtags[:15]

    # Top posts overall
    scored = sorted(
        rows, key=lambda r: _engagement(r, followers), reverse=True
    )[:5]
    top_posts = [_post_dict(r, followers) for r in scored]

    # Recommendations (data-driven, short)
    recs = []
    best_mt = by_media_type[0]
    recs.append(
        f"Post more **{best_mt['media_type']}s** — they average "
        f"{best_mt['avg_engagement_rate']}% engagement across "
        f"{best_mt['count']} recent posts."
    )
    best_day = max(by_day, key=lambda x: x["avg_engagement_rate"])
    if best_day["count"]:
        recs.append(
            f"**{best_day['day']}** posts perform best "
            f"(~{best_day['avg_engagement_rate']}% engagement)."
        )
    best_hour = max(by_hour, key=lambda x: x["avg_engagement_rate"])
    if best_hour["count"]:
        recs.append(
            f"Aim for posting around **{best_hour['hour']:02d}:00 UTC** — "
            f"your best-performing time window."
        )
    if top_hashtags:
        tags = ", ".join("#" + t["hashtag"] for t in top_hashtags[:5])
        recs.append(f"Highest-engagement hashtags you've used: {tags}.")

    # Caption length insight
    lengths = [(len(r["caption"] or ""), _engagement(r, followers)) for r in rows]
    short = [er for l, er in lengths if l < 80]
    long = [er for l, er in lengths if l >= 80]
    if short and long:
        s_avg = sum(short) / len(short)
        l_avg = sum(long) / len(long)
        if abs(s_avg - l_avg) > 0.3:
            winner = "shorter (<80 char)" if s_avg > l_avg else "longer (80+ char)"
            recs.append(f"{winner} captions outperform on this account.")

    return {
        "post_count": len(rows),
        "by_media_type": by_media_type,
        "by_day": by_day,
        "by_hour": by_hour,
        "top_hashtags": top_hashtags,
        "top_posts": top_posts,
        "recommendations": recs,
    }
