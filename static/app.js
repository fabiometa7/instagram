const username = document.body.dataset.username;
const statusEl = document.getElementById("status");
const refreshBtn = document.getElementById("refreshBtn");

const charts = {};

function fmtNum(n) {
  if (n == null) return "—";
  if (Math.abs(n) >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (Math.abs(n) >= 1_000) return (n / 1_000).toFixed(1) + "k";
  return String(n);
}
function fmtDelta(n) {
  if (n == null) return { text: "—", cls: "flat" };
  if (n > 0) return { text: "+" + fmtNum(n), cls: "up" };
  if (n < 0) return { text: fmtNum(n), cls: "down" };
  return { text: "0", cls: "flat" };
}
function setStatus(text, kind) {
  statusEl.textContent = text;
  statusEl.className = "status " + (kind || "muted");
}

async function fetchJSON(url, options) {
  const r = await fetch(url, options);
  const data = await r.json();
  if (!r.ok || data.ok === false) {
    throw new Error(data.error || `HTTP ${r.status}`);
  }
  return data;
}

async function loadSummary() {
  const s = await fetchJSON(`/api/summary?username=${encodeURIComponent(username)}`);
  renderKPIs(s);
  renderFollowerChart(s.history);
  const hint = document.getElementById("snapHint");
  if (s.snapshots < 2) {
    hint.textContent = `${s.snapshots} snapshot${s.snapshots === 1 ? "" : "s"} recorded — hit Refresh over time to build history.`;
  } else {
    hint.textContent = `${s.snapshots} snapshots recorded.`;
  }
}

function renderKPIs(s) {
  const w = s.windows || {};
  const card = (label, value, delta, note) => {
    const d = fmtDelta(delta);
    return `
      <div class="card">
        <span class="label">${label}</span>
        <span class="value">${value}</span>
        <span class="delta ${d.cls}">${d.text}${note ? ` <span style="color:var(--muted)">· ${note}</span>` : ""}</span>
      </div>`;
  };
  const partial = (k) => (w[k] && !w[k].has_full_window ? "so far" : "");
  const el = document.getElementById("kpiCards");
  el.innerHTML =
    card("Followers", fmtNum(s.current_followers), null, `${s.snapshots} snap${s.snapshots === 1 ? "" : "s"}`) +
    card("7-day", w["7"] ? fmtDelta(w["7"].delta).text : "—", w["7"] && w["7"].delta, partial("7")) +
    card("30-day", w["30"] ? fmtDelta(w["30"].delta).text : "—", w["30"] && w["30"].delta, partial("30")) +
    card("60-day", w["60"] ? fmtDelta(w["60"].delta).text : "—", w["60"] && w["60"].delta, partial("60")) +
    card("90-day", w["90"] ? fmtDelta(w["90"].delta).text : "—", w["90"] && w["90"].delta, partial("90"));
}

function baseChartOpts() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { labels: { color: "#e6e8ee" } },
      tooltip: { backgroundColor: "#171a21", borderColor: "#262b36", borderWidth: 1 },
    },
    scales: {
      x: { ticks: { color: "#8b93a7" }, grid: { color: "#1e222b" } },
      y: { ticks: { color: "#8b93a7" }, grid: { color: "#1e222b" }, beginAtZero: true },
    },
  };
}

function replaceChart(key, config) {
  if (charts[key]) charts[key].destroy();
  const ctx = document.getElementById(key).getContext("2d");
  charts[key] = new Chart(ctx, config);
}

function renderFollowerChart(history) {
  const labels = history.map((h) => new Date(h.t).toLocaleString());
  const data = history.map((h) => h.followers);
  replaceChart("followerChart", {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Followers",
          data,
          borderColor: "#ff2d78",
          backgroundColor: "rgba(255,45,120,0.15)",
          tension: 0.25,
          fill: true,
          pointRadius: 3,
        },
      ],
    },
    options: baseChartOpts(),
  });
}

async function loadRecent() {
  const posts = await fetchJSON(`/api/recent?username=${encodeURIComponent(username)}&limit=5`);
  document.getElementById("recentList").innerHTML = renderPostList(posts);
}

function renderPostList(posts) {
  if (!posts.length) return `<div class="empty">No posts yet — hit Refresh.</div>`;
  return posts.map(postRow).join("");
}

function postRow(p) {
  const date = new Date(p.posted_at).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
  const cap = (p.caption || "").replace(/\s+/g, " ").trim() || "(no caption)";
  const views = p.video_views != null ? `<span>👁 ${fmtNum(p.video_views)}</span>` : "";
  return `
    <div class="post">
      <div class="type-badge ${p.media_type}">${p.media_type}</div>
      <div class="meta">
        <span class="caption">${escapeHtml(cap.slice(0, 120))}</span>
        <div class="row">
          <span>${date}</span>
          <span>❤ ${fmtNum(p.likes)}</span>
          <span>💬 ${fmtNum(p.comments)}</span>
          ${views}
          <a class="open" href="${p.url}" target="_blank" rel="noopener">Open</a>
        </div>
      </div>
      <div class="stats">
        <div class="er">${p.engagement_rate}%</div>
        <div class="lbl">engagement</div>
      </div>
    </div>`;
}

async function loadInsights() {
  const i = await fetchJSON(`/api/insights?username=${encodeURIComponent(username)}&limit=50`);
  renderRecs(i.recommendations);
  renderMediaChart(i.by_media_type);
  renderDayChart(i.by_day);
  renderHourChart(i.by_hour);
  renderHashtags(i.top_hashtags);
  document.getElementById("topPosts").innerHTML = renderPostList(i.top_posts);
}

function renderRecs(recs) {
  if (!recs || !recs.length) {
    document.getElementById("recs").innerHTML = `<li class="empty">No recommendations yet.</li>`;
    return;
  }
  const md = (s) => s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  document.getElementById("recs").innerHTML = recs.map((r) => `<li>${md(escapeHtml(r)).replace(/&lt;strong&gt;/g, "<strong>").replace(/&lt;\/strong&gt;/g, "</strong>")}</li>`).join("");
}

function renderMediaChart(rows) {
  replaceChart("mediaChart", {
    type: "bar",
    data: {
      labels: rows.map((r) => `${r.media_type} (${r.count})`),
      datasets: [
        {
          label: "Avg engagement rate %",
          data: rows.map((r) => r.avg_engagement_rate),
          backgroundColor: ["#ff2d78", "#7c5cff", "#2ecc71", "#f7b731"],
        },
      ],
    },
    options: baseChartOpts(),
  });
}

function renderDayChart(rows) {
  replaceChart("dayChart", {
    type: "bar",
    data: {
      labels: rows.map((r) => r.day),
      datasets: [
        {
          label: "Avg engagement rate %",
          data: rows.map((r) => r.avg_engagement_rate),
          backgroundColor: "#7c5cff",
        },
      ],
    },
    options: baseChartOpts(),
  });
}

function renderHourChart(rows) {
  replaceChart("hourChart", {
    type: "bar",
    data: {
      labels: rows.map((r) => String(r.hour).padStart(2, "0")),
      datasets: [
        {
          label: "Avg engagement rate %",
          data: rows.map((r) => r.avg_engagement_rate),
          backgroundColor: "#ff2d78",
        },
      ],
    },
    options: baseChartOpts(),
  });
}

function renderHashtags(tags) {
  if (!tags.length) {
    document.getElementById("hashtags").innerHTML = `<div class="empty">Need at least 2 uses of a hashtag to rank it.</div>`;
    return;
  }
  document.getElementById("hashtags").innerHTML = tags
    .map(
      (t) => `<span class="tag">#${escapeHtml(t.hashtag)} <span class="er">${t.avg_engagement_rate}%</span> <span style="color:var(--muted)">× ${t.uses}</span></span>`
    )
    .join("");
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadRecent(), loadInsights()]);
}

refreshBtn.addEventListener("click", async () => {
  refreshBtn.disabled = true;
  setStatus("fetching from Instagram…");
  try {
    const r = await fetchJSON("/api/refresh", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, max_posts: 50 }),
    });
    setStatus(`saved ${r.posts_saved} posts`, "ok");
    await refreshAll();
  } catch (e) {
    setStatus("error: " + e.message, "err");
  } finally {
    refreshBtn.disabled = false;
  }
});

refreshAll().catch((e) => setStatus("load error: " + e.message, "err"));
