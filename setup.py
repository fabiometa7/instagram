"""One-shot Graph API bootstrapper.

Run this once on your machine after pasting your short-lived user token:

    python setup.py

It will:
  1. Verify the token and show what account it belongs to.
  2. Discover your Instagram Business Account ID from the linked FB Page(s).
  3. (Optional) Exchange the short-lived token for a 60-day long-lived one,
     if you also provide APP_ID and APP_SECRET.
  4. Write everything to `.env` so the dashboard picks it up on next start.

Nothing is sent anywhere except graph.facebook.com.
"""
from __future__ import annotations

import getpass
import json
import sys
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError

GRAPH = "https://graph.facebook.com/v21.0"
ENV_PATH = Path(__file__).parent / ".env"


def _get(path: str, **params) -> dict:
    url = f"{GRAPH}/{path.lstrip('/')}?{urlencode(params)}"
    try:
        with urlopen(Request(url), timeout=30) as r:
            return json.loads(r.read().decode())
    except HTTPError as e:
        raise SystemExit(f"[graph API] {e.code}: {e.read().decode()}")


def _prompt(label: str, default: str = "", secret: bool = False) -> str:
    hint = f" [{default}]" if default else ""
    fn = getpass.getpass if secret else input
    raw = fn(f"{label}{hint}: ")
    val = "".join(raw.split()).strip("'\"")
    return val or default


def _write_env(pairs: dict[str, str]) -> None:
    existing: dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                existing[k.strip()] = v.strip()
    existing.update(pairs)
    ENV_PATH.write_text("\n".join(f"{k}={v}" for k, v in existing.items()) + "\n")
    print(f"\n  wrote {len(pairs)} keys to {ENV_PATH}")


def main() -> int:
    print("Content Hub — Graph API setup\n")
    print("Tip: if your token is very long, save it to token.txt in this")
    print("     folder and press Enter at the prompt (it'll load it from there).\n")
    token = _prompt("Paste your Graph API user token", secret=True)
    if not token:
        token_file = Path(__file__).parent / "token.txt"
        if token_file.exists():
            token = "".join(token_file.read_text().split()).strip("'\"")
            print(f"  loaded token from {token_file.name} ({len(token)} chars)")
    if not token:
        print("no token provided; aborting")
        return 1
    print(f"  token: {token[:12]}…{token[-6:]} ({len(token)} chars)")
    if len(token) < 100:
        print("  ⚠ this looks too short for a Graph API token — likely truncated.")
        print("    Try saving the full token to token.txt and re-running.")

    print("\n→ Verifying token…")
    debug = _get("debug_token", input_token=token, access_token=token).get("data", {})
    if not debug.get("is_valid"):
        print(f"  token is invalid: {debug}")
        return 1
    scopes = debug.get("scopes", [])
    print(f"  ok · app_id={debug.get('app_id')} · user_id={debug.get('user_id')}")
    print(f"  scopes: {', '.join(scopes) or '(none)'}")
    for needed in ("instagram_basic", "instagram_manage_insights", "pages_show_list"):
        if needed not in scopes:
            print(f"  ⚠ missing scope: {needed} — add it in the Graph API Explorer & regenerate")

    print("\n→ Looking up Instagram business accounts on your Pages…")
    pages = _get(
        "me/accounts",
        fields="id,name,instagram_business_account{id,username,followers_count,media_count},"
               "connected_instagram_account{id,username}",
        access_token=token,
        limit=100,
    ).get("data", [])

    print(f"  found {len(pages)} Facebook Page(s) accessible to this token:")
    for p in pages:
        ig = p.get("instagram_business_account")
        conn = p.get("connected_instagram_account")
        if ig:
            tag = f"→ IG business @{ig.get('username')} ({ig['id']})"
        elif conn:
            tag = f"→ IG @{conn.get('username')} connected but NOT as Business/Creator"
        else:
            tag = "(no IG linked to this Page)"
        print(f"    · {p['name']}  ({p['id']})  {tag}")

    ig_candidates = [
        (p["instagram_business_account"], p) for p in pages if p.get("instagram_business_account")
    ]
    if not ig_candidates:
        print("\n  No Page above has an IG business account visible to this token.")
        print("  This is almost always one of three things:\n")
        print("  A) The token doesn't include the right Page.")
        print("     In the Graph API Explorer, click the token → 'Add or Remove Pages'")
        print("     (or regenerate the token). In the popup that Facebook shows,")
        print("     make sure you EXPLICITLY select the Page @fabiometa_ is linked to.")
        print("     'Ask again for the ones you didn't choose' means the Page is opted out.")
        print()
        print("  B) The Page shown above has @fabiometa_ connected but not as")
        print("     Business/Creator (marked '(NOT as Business/Creator)' above).")
        print("     On the Instagram app: Settings → Account type and tools →")
        print("     Switch to Professional Account (Business or Creator).")
        print()
        print("  C) The Facebook Page you own isn't shown at all above.")
        print("     Then @fabiometa_ isn't linked to a Page you admin.")
        print("     Meta Business Suite → your Page → Linked Accounts → Instagram.")
        print()
        print("  After fixing, generate a NEW token (permissions may need re-approval)")
        print("  and re-run: python3 setup.py")
        return 1

    if len(ig_candidates) == 1:
        ig, page = ig_candidates[0]
    else:
        print("  Multiple IG accounts found:")
        for i, (ig, page) in enumerate(ig_candidates):
            print(f"    [{i}] @{ig.get('username')}  ({ig['id']})  via page {page['name']}")
        idx = int(_prompt("Pick one by number", default="0"))
        ig, page = ig_candidates[idx]

    print(f"  picked @{ig.get('username')}  (id {ig['id']})")
    print(
        f"  followers={ig.get('followers_count')}  media={ig.get('media_count')}  "
        f"via page {page['name']}"
    )

    print("\n→ Long-lived token exchange (optional).")
    print("  Skip by pressing Enter — the short-lived token expires in ~1 hour.")
    app_id = _prompt("App ID", default="")
    long_token = token
    if app_id:
        app_secret = _prompt("App Secret", secret=True)
        exch = _get(
            "oauth/access_token",
            grant_type="fb_exchange_token",
            client_id=app_id,
            client_secret=app_secret,
            fb_exchange_token=token,
        )
        long_token = exch.get("access_token", token)
        ttl = exch.get("expires_in")
        if ttl:
            print(f"  ok · long-lived token acquired · expires in {int(ttl)//86400} days")
        else:
            print("  ok · long-lived token acquired")

    _write_env({"IG_GRAPH_TOKEN": long_token, "IG_BUSINESS_ID": ig["id"]})
    print("\nAll set. Start the app with ./run.sh (or run.bat) and hit Refresh.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
