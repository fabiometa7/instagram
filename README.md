# Content Hub — Instagram analytics, running locally

Personal dashboard for **@fabiometa_** that shows:

- Followers gained/lost over the last **7 / 30 / 60 / 90 days**
- **Last 5 posts** with engagement rates
- What to post more of, based on the **last 50 posts** — best media type, best day/hour, best hashtags, top-performing posts, caption length insight

Everything runs on your PC. Data stays in a local SQLite file (`data/hub.sqlite3`).

## Requirements
- Python 3.10+
- The Instagram account **@fabiometa_** should be public **or** you supply a Graph API token (see below).

## Run it

Pick whichever feels best:

**A) Double-click launcher (Mac).**
In Finder, open the `instagram/` folder and double-click **`Content Hub.command`**. Terminal pops up, the server starts, your browser opens. Close the Terminal to stop it.

**B) Real Mac app in your Dock.**
```bash
./scripts/build_mac_app.sh install
```
Puts `Content Hub.app` in `/Applications/`. Open it once, then right-click its Dock icon → **Options → Keep in Dock**. Double-clicking it launches the server in the background and opens the dashboard. To stop the background server: `./scripts/stop_server.sh`.

**C) Auto-start at login (Mac).**
```bash
./scripts/install_autostart.sh
```
Content Hub runs as a background launchd agent — starts at login, restarts if it crashes, always at <http://127.0.0.1:5000>. To turn off: `./scripts/install_autostart.sh off`.

**D) Old-school terminal:**
```bash
./run.sh          # Mac / Linux
run.bat           # Windows
```

Then open <http://127.0.0.1:5000>. Hit **Refresh from Instagram** on the top-right to pull the latest data.

Each Refresh:
1. Snapshots your current follower count (this is what powers the 7/30/60/90-day deltas — hit Refresh once a day to build history).
2. Pulls the latest 50 posts and updates likes/comments/views.
3. Recomputes recommendations.

## Two data sources

**Default: public scraping** (works out of the box, no setup).
Pulls likes, comments, video view count, timestamps, media type, hashtags, and captions. No reach/impressions/watch time (Instagram doesn't expose those publicly).

**Optional: Meta Graph API** (adds real Insights: reach, impressions, saves, plays, watch time, and follower daily deltas from Meta itself).

To enable:
1. Switch @fabiometa_ to a Business or Creator account (IG app → Settings → Account type) and link it to a Facebook Page you own.
2. Create a Business app at <https://developers.facebook.com/apps/> and add the **Instagram Graph API** product.
3. In the Graph API Explorer <https://developers.facebook.com/tools/explorer/>, generate a token with:
   `instagram_basic`, `instagram_manage_insights`, `pages_show_list`, `pages_read_engagement`, `business_management`.
4. Exchange for a long-lived (60-day) token:
   `https://graph.facebook.com/v21.0/oauth/access_token?grant_type=fb_exchange_token&client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=SHORT_TOKEN`
5. Find your IG Business Account ID:
   - `me/accounts?access_token=...` → Page ID
   - `PAGE_ID?fields=instagram_business_account&access_token=...` → IG User ID
6. Copy `.env.example` → `.env` and fill in `IG_GRAPH_TOKEN` and `IG_BUSINESS_ID`.

**Shortcut:** instead of doing 5–6 by hand, run:
```bash
python setup.py
```
Paste your short-lived token when prompted. It'll verify the token, find your IG Business Account ID automatically, optionally exchange for a 60-day token (if you paste your App ID + App Secret), and write `.env` for you.

Restart the app; it now uses the Graph API automatically.

## File layout

```
app.py             Flask app + routes
db.py              SQLite schema
scraper.py         Public scraper (instaloader)
graph_api.py       Meta Graph API path (used if .env is set)
analytics.py       Windowed follower deltas, engagement, recommendations
templates/         index.html
static/            styles.css, app.js
data/hub.sqlite3   Local database (gitignored)
```

## API endpoints (for your own tinkering)

- `POST /api/refresh`  — pull latest from IG and persist
- `GET  /api/summary?username=...`  — followers + 7/30/60/90-day windows + history
- `GET  /api/recent?username=...&limit=5`
- `GET  /api/insights?username=...&limit=50`

## Notes on the 7/30/60/90-day view

The follower windows compare the current snapshot to the earliest one older than N days. If you've only been running the app for 3 days, the 30-day number falls back to your earliest snapshot and is labeled **so far**. The longer you run it, the sharper the trends.

If you enable the Graph API, this repo will also start recording accurate follower deltas from Meta — those don't need a warm-up period.
