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
        fields="id,name,instagram_business_account{id,username,followers_count,media_count}",
        access_token=token,
    ).get("data", [])

    print(f"  found {len(pages)} Facebook Page(s) you admin:")
    for p in pages:
        ig = p.get("instagram_business_account")
        tag = f"→ IG @{ig.get('username')} ({ig['id']})" if ig else "(no IG linked)"
        print(f"    · {p['name']}  ({p['id']})  {tag}")

    ig_candidates = [
        (p["instagram_business_account"], p) for p in pages if p.get("instagram_business_account")
    ]
    if not ig_candidates:
        print("\n  No Facebook Page above has an Instagram business account linked.")
        print("  To fix:")
        print("    1. In the Instagram app, open @fabiometa_ → Settings → 'Account type")
        print("       and tools' → 'Switch to professional account' (Business or Creator).")
        print("    2. During that setup (or after), tap 'Connect Facebook page' and pick")
        print("       one of the Pages listed above (or create a new one you own).")
        print("    3. If @fabiometa_ is already Professional, on the Facebook Page's")
        print("       Settings → Linked Accounts → Instagram, link @fabiometa_.")
        print("    4. Generate a fresh token in the Graph API Explorer, then re-run this.")
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
