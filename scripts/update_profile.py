import datetime as dt
import hashlib
import json
import os
import random
import textwrap
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
ASSETS_DIR = ROOT / "assests"
SONG_FILE = ROOT / "random_song.txt"

USERNAME = os.getenv("PROFILE_USERNAME", "aryamehta0302")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
BLOG_FEEDS = [
    feed.strip()
    for feed in os.getenv("BLOG_FEEDS", "").split(",")
    if feed.strip()
]

DEFAULT_SONGS = [
    "https://youtu.be/dQw4w9WgXcQ",
    "https://youtu.be/C0DPdy98e4c",
    "https://youtu.be/oygrmJFKYZY",
    "https://youtu.be/2vjPBrBU-TM",
    "https://youtu.be/kXYiU_JCYtU",
    "https://youtu.be/fLexgOxsZu0",
    "https://youtu.be/09R8_2nJtjg",
]

QUOTE_BANK = [
    "Great ML systems are not just accurate — they are observable, reproducible, and maintainable.",
    "Speed in AI comes from clear abstractions, not chaos.",
    "A model in a notebook is an idea. A model in production is engineering.",
    "Automation is a force multiplier for consistent engineering quality.",
    "The best developer branding is shipping useful things consistently.",
    "Reliable AI beats flashy demos every single time.",
    "Measure what matters: latency, quality, and user trust.",
    "The gap between prototype and production is where real engineering lives.",
    "Write code that your future self will thank you for.",
    "Every commit is a small promise to your project's future.",
    "Ship fast, but ship with tests. Move fast, but leave docs behind.",
    "Good APIs are built by engineers who use their own APIs.",
    "The best architectures emerge from simplicity, not complexity.",
    "Debug with data, not assumptions. Optimize with metrics, not intuition.",
]

LEVEL_TITLES = [
    "Newbie",
    "Apprentice",
    "Developer",
    "Engineer",
    "Senior Engineer",
    "Architect",
    "Principal",
    "Distinguished",
    "Fellow",
    "Legend",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def utc_now() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


def request_json(url: str):
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-readme-automation")
    if GITHUB_TOKEN:
        req.add_header("Authorization", f"Bearer {GITHUB_TOKEN}")
    with urllib.request.urlopen(req, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str) -> str:
    req = urllib.request.Request(url)
    req.add_header("User-Agent", "profile-readme-automation")
    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read().decode("utf-8", errors="ignore")


def escape_xml(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )


def replace_between(content: str, start_tag: str, end_tag: str, new_block: str) -> str:
    start = content.find(start_tag)
    end = content.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return content
    start_idx = start + len(start_tag)
    return content[:start_idx] + "\n" + new_block.strip() + "\n" + content[end:]


# ---------------------------------------------------------------------------
# Song helpers
# ---------------------------------------------------------------------------

def load_songs() -> List[str]:
    songs = []
    if SONG_FILE.exists():
        songs = [
            line.strip()
            for line in SONG_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    return songs or DEFAULT_SONGS


def choose_song_for_today(songs: List[str]) -> str:
    seed = int(dt.date.today().strftime("%Y%m%d"))
    random.seed(seed)
    return random.choice(songs)


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def fetch_github_data() -> Dict:
    user = request_json(f"https://api.github.com/users/{USERNAME}")
    repos = request_json(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated"
    )
    events = request_json(
        f"https://api.github.com/users/{USERNAME}/events?per_page=30"
    )
    total_stars = sum(
        repo.get("stargazers_count", 0)
        for repo in repos
        if not repo.get("fork", False)
    )
    non_fork_repos = [repo for repo in repos if not repo.get("fork", False)]
    return {
        "user": user,
        "repos": non_fork_repos,
        "events": events,
        "total_stars": total_stars,
    }


def pick_spotlight_repo(repos: List[Dict]) -> Dict:
    if not repos:
        return {}
    day_hash = hashlib.sha1(
        dt.date.today().isoformat().encode("utf-8")
    ).hexdigest()
    idx = int(day_hash[:8], 16) % len(repos)
    return repos[idx]


def summarize_week(events: List[Dict]) -> Dict[str, int]:
    week_ago = utc_now() - dt.timedelta(days=7)
    counters = {
        "PushEvent": 0,
        "PullRequestEvent": 0,
        "IssuesEvent": 0,
        "WatchEvent": 0,
        "CreateEvent": 0,
    }
    repos_touched: set = set()
    for event in events:
        created_at = event.get("created_at")
        if not created_at:
            continue
        event_time = dt.datetime.strptime(
            created_at, "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.UTC)
        if event_time < week_ago:
            continue
        event_type = event.get("type", "")
        if event_type in counters:
            counters[event_type] += 1
        repo_name = event.get("repo", {}).get("name")
        if repo_name:
            repos_touched.add(repo_name)
    counters["repos_touched"] = len(repos_touched)
    return counters


def parse_feed(url: str, limit: int = 3) -> List[Dict[str, str]]:
    try:
        xml_text = request_text(url)
    except Exception:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    entries: List[Dict[str, str]] = []
    for item in root.findall(".//item")[:limit]:
        title = (item.findtext("title") or "Untitled").strip()
        link = (item.findtext("link") or "").strip()
        if link:
            entries.append({"title": title, "link": link})
    if not entries:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        for item in root.findall(".//atom:entry", ns)[:limit]:
            title = (
                item.findtext("atom:title", default="Untitled", namespaces=ns)
                or "Untitled"
            ).strip()
            link_node = item.find("atom:link", ns)
            link = ""
            if link_node is not None:
                link = (link_node.attrib.get("href") or "").strip()
            if link:
                entries.append({"title": title, "link": link})
    return entries[:limit]


# ---------------------------------------------------------------------------
# XP / Level system
# ---------------------------------------------------------------------------

def calculate_xp(public_repos: int, total_stars: int, followers: int):
    raw_xp = public_repos * 10 + total_stars * 50 + followers * 20
    level = 1
    xp_remaining = raw_xp
    while xp_remaining >= level * 100:
        xp_remaining -= level * 100
        level += 1
    xp_for_next = level * 100
    progress = min(100, int((xp_remaining / max(xp_for_next, 1)) * 100))
    title = LEVEL_TITLES[min(level - 1, len(LEVEL_TITLES) - 1)]
    return level, xp_remaining, xp_for_next, progress, raw_xp, title


# ---------------------------------------------------------------------------
# SVG generators
# ---------------------------------------------------------------------------

def generate_dev_level_svg(
    public_repos: int, total_stars: int, followers: int
):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    level, xp_rem, xp_next, pct, total_xp, title = calculate_xp(
        public_repos, total_stars, followers
    )
    bar_max = 832
    bar_fill = max(8, int(bar_max * pct / 100))

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="170" viewBox="0 0 900 170" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="lvlbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#1e1b4b"/>
    </linearGradient>
    <linearGradient id="xpbar" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="900" height="170" rx="18" fill="url(#lvlbg)"/>

  <text x="34" y="42" fill="#e5e7eb" font-size="22" font-family="Segoe UI, Arial" font-weight="700">🎮  Developer Level {level}  —  {escape_xml(title)}</text>
  <text x="34" y="66" fill="#94a3b8" font-size="13" font-family="Segoe UI, Arial">XP: {xp_rem} / {xp_next}  •  {pct}% to Level {level + 1}</text>

  <rect x="34" y="84" width="{bar_max}" height="24" rx="12" fill="#1e293b"/>
  <rect x="34" y="84" width="{bar_fill}" height="24" rx="12" fill="url(#xpbar)"/>

  <text x="{34 + bar_max // 2}" y="101" fill="#ffffff" font-size="12" font-family="Segoe UI, Arial" font-weight="700" text-anchor="middle">{pct}%</text>

  <text x="34" y="140" fill="#22d3ee" font-size="12" font-family="Segoe UI, Arial">📦 {public_repos} repos × 10 xp</text>
  <text x="250" y="140" fill="#a78bfa" font-size="12" font-family="Segoe UI, Arial">⭐ {total_stars} stars × 50 xp</text>
  <text x="460" y="140" fill="#22c55e" font-size="12" font-family="Segoe UI, Arial">👥 {followers} followers × 20 xp</text>
  <text x="700" y="140" fill="#f59e0b" font-size="12" font-family="Segoe UI, Arial">🔥 Total: {total_xp} xp</text>
</svg>
"""
    (ASSETS_DIR / "dev-level.svg").write_text(svg, encoding="utf-8")


def generate_metrics_svg(
    public_repos: int, total_stars: int, followers: int, following: int
):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    now = utc_now().strftime("%d %b %Y")

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="200" viewBox="0 0 900 200" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="mbg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0f172a"/>
      <stop offset="100%" stop-color="#111827"/>
    </linearGradient>
    <linearGradient id="maccent" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0%" stop-color="#06b6d4"/>
      <stop offset="100%" stop-color="#8b5cf6"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="900" height="200" rx="18" fill="url(#mbg)"/>
  <rect x="24" y="16" width="852" height="5" rx="3" fill="url(#maccent)"/>

  <text x="34" y="52" fill="#e5e7eb" font-size="22" font-family="Segoe UI, Arial" font-weight="700">📡  Live Engineering Metrics</text>
  <text x="34" y="74" fill="#64748b" font-size="12" font-family="Segoe UI, Arial">Auto-updated via GitHub Actions + GitHub API</text>

  <text x="60" y="120" fill="#22d3ee" font-size="28" font-family="Segoe UI, Arial" font-weight="800">{public_repos}</text>
  <text x="60" y="142" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">Repositories</text>

  <text x="240" y="120" fill="#a78bfa" font-size="28" font-family="Segoe UI, Arial" font-weight="800">{total_stars}</text>
  <text x="240" y="142" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">Total Stars</text>

  <text x="400" y="120" fill="#22c55e" font-size="28" font-family="Segoe UI, Arial" font-weight="800">{followers}</text>
  <text x="400" y="142" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">Followers</text>

  <text x="540" y="120" fill="#f59e0b" font-size="28" font-family="Segoe UI, Arial" font-weight="800">{following}</text>
  <text x="540" y="142" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">Following</text>

  <text x="700" y="120" fill="#f472b6" font-size="16" font-family="Segoe UI, Arial" font-weight="700">{now}</text>
  <text x="700" y="142" fill="#94a3b8" font-size="12" font-family="Segoe UI, Arial">Last Refresh (UTC)</text>
</svg>
"""
    (ASSETS_DIR / "dynamic-metrics.svg").write_text(svg, encoding="utf-8")


def generate_activity_svg(events: List[Dict]):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for event in events[:5]:
        etype = event.get("type", "Unknown")
        repo = event.get("repo", {}).get("name", "unknown/repo")
        lines.append(f"{etype} → {repo}")
    while len(lines) < 5:
        lines.append("—")

    safe = [
        escape_xml(textwrap.shorten(l, width=62, placeholder="..."))
        for l in lines
    ]
    colors = ["#22d3ee", "#a78bfa", "#34d399", "#f472b6", "#f59e0b"]
    event_rows = "\n".join(
        f'  <text x="34" y="{120 + i * 28}" fill="{colors[i]}" '
        f'font-size="14" font-family="Consolas, monospace">'
        f"  {i + 1})  {safe[i]}</text>"
        for i in range(5)
    )

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg width="900" height="280" viewBox="0 0 900 280" xmlns="http://www.w3.org/2000/svg">
  <defs>
    <linearGradient id="abg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#020617"/>
      <stop offset="100%" stop-color="#0f172a"/>
    </linearGradient>
  </defs>

  <rect x="0" y="0" width="900" height="280" rx="18" fill="url(#abg)"/>

  <!-- Terminal chrome -->
  <circle cx="26" cy="20" r="6" fill="#ff5f56"/>
  <circle cx="46" cy="20" r="6" fill="#ffbd2e"/>
  <circle cx="66" cy="20" r="6" fill="#27c93f"/>
  <text x="110" y="24" fill="#6b7280" font-size="12" font-family="Consolas, monospace">arya@dev: ~/github — activity-log</text>

  <line x1="14" y1="38" x2="886" y2="38" stroke="#1e293b" stroke-width="1"/>

  <text x="34" y="64" fill="#e2e8f0" font-size="20" font-family="Consolas, monospace" font-weight="700">$  Latest Public Activity</text>
  <text x="34" y="86" fill="#64748b" font-size="12" font-family="Consolas, monospace">Live from GitHub Events API  •  auto-refreshed</text>

{event_rows}
</svg>
"""
    (ASSETS_DIR / "latest-activity.svg").write_text(svg, encoding="utf-8")


# ---------------------------------------------------------------------------
# README updater
# ---------------------------------------------------------------------------

def update_readme(data: Dict):
    readme = README_PATH.read_text(encoding="utf-8")

    user = data["user"]
    repos = data["repos"]
    events = data["events"]
    total_stars = data["total_stars"]

    public_repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)

    # --- Dynamic metrics text ---
    metrics_block = "\n".join([
        f"- 🚀 **Public repositories:** {public_repos}",
        f"- ⭐ **Total stars earned:** {total_stars}",
        f"- 👥 **Followers:** {followers}  |  **Following:** {following}",
        f"- 🕒 **Last refresh:** {utc_now().strftime('%d %b %Y, %H:%M UTC')}",
    ])

    # --- Project spotlight ---
    spotlight = pick_spotlight_repo(repos)
    if spotlight:
        name = spotlight.get("name", "Unknown")
        desc = spotlight.get("description") or "No description available."
        desc = textwrap.shorten(desc, width=140, placeholder="...")
        lang = spotlight.get("language") or "Mixed"
        url = spotlight.get("html_url", f"https://github.com/{USERNAME}")
        stars = spotlight.get("stargazers_count", 0)
        spotlight_block = (
            "### 🎲 Dynamic Project Spotlight\n"
            f"- **[{name}]({url})**\n"
            f"- **Stack:** {lang}  |  **Stars:** {stars}\n"
            f"- **Summary:** {desc}"
        )
    else:
        spotlight_block = (
            "### 🎲 Dynamic Project Spotlight\n"
            "- No public repositories available yet."
        )

    # --- Blog / latest repos ---
    blog_entries: List[Dict[str, str]] = []
    for feed in BLOG_FEEDS[:3]:
        blog_entries.extend(parse_feed(feed, limit=2))

    if blog_entries:
        blog_block = "\n".join(
            f"- 📝 [{e['title']}]({e['link']})" for e in blog_entries[:3]
        )
    else:
        latest = repos[:3]
        if latest:
            blog_block = "\n".join(
                f"- 🔭 [{r.get('name', 'repo')}]({r.get('html_url')}) — latest repo activity"
                for r in latest
            )
        else:
            blog_block = "- No articles or repo updates available yet."

    # --- Daily quote ---
    quote = QUOTE_BANK[dt.date.today().toordinal() % len(QUOTE_BANK)]
    quote_block = f"> _{quote}_"

    # --- Weekly summary ---
    weekly = summarize_week(events)
    weekly_block = "\n".join([
        f"- ✅ Push events (7d): **{weekly.get('PushEvent', 0)}**",
        f"- 🔀 Pull request events (7d): **{weekly.get('PullRequestEvent', 0)}**",
        f"- 🐞 Issue events (7d): **{weekly.get('IssuesEvent', 0)}**",
        f"- 🧭 Repositories touched (7d): **{weekly.get('repos_touched', 0)}**",
    ])

    # --- Song ---
    songs = load_songs()
    song = choose_song_for_today(songs)
    SONG_FILE.write_text("\n".join(songs) + "\n", encoding="utf-8")

    # --- Patch README ---
    readme = replace_between(
        readme,
        "<!-- DYNAMIC_METRICS_START -->",
        "<!-- DYNAMIC_METRICS_END -->",
        metrics_block,
    )
    readme = replace_between(
        readme,
        "<!-- RANDOM_PROJECT_START -->",
        "<!-- RANDOM_PROJECT_END -->",
        spotlight_block,
    )
    readme = replace_between(
        readme,
        "<!-- BLOG_POSTS_START -->",
        "<!-- BLOG_POSTS_END -->",
        blog_block,
    )
    readme = replace_between(
        readme,
        "<!-- DAILY_QUOTE_START -->",
        "<!-- DAILY_QUOTE_END -->",
        quote_block,
    )
    readme = replace_between(
        readme,
        "<!-- WEEKLY_SUMMARY_START -->",
        "<!-- WEEKLY_SUMMARY_END -->",
        weekly_block,
    )

    # --- Song line ---
    if "<!-- RANDOM_SONG -->" in readme:
        marker = "<!-- RANDOM_SONG -->"
        idx = readme.find(marker)
        eol = readme.find("\n", idx)
        next_start = eol + 1
        next_end = readme.find("\n", next_start)
        if next_end == -1:
            next_end = len(readme)
        readme = (
            readme[:next_start]
            + f"\U0001f3a7 **Now Playing:** {song}"
            + readme[next_end:]
        )

    README_PATH.write_text(readme, encoding="utf-8")

    # --- Generate SVG assets ---
    generate_dev_level_svg(public_repos, total_stars, followers)
    generate_metrics_svg(public_repos, total_stars, followers, following)
    generate_activity_svg(events)


def main():
    data = fetch_github_data()
    update_readme(data)


if __name__ == "__main__":
    main()
