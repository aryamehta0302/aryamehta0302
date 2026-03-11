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
BLOG_FEEDS = [feed.strip() for feed in os.getenv("BLOG_FEEDS", "").split(",") if feed.strip()]

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
    "Great ML systems are not just accurate, they are observable, reproducible, and maintainable.",
    "Speed in AI comes from clear abstractions, not chaos.",
    "A model in notebook is an idea. A model in production is engineering.",
    "Automation is a force multiplier for consistent engineering quality.",
    "The best developer branding is shipping useful things consistently.",
    "Reliable AI beats flashy demos every single time.",
    "Measure what matters: latency, quality, and user trust.",
]


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


def load_songs() -> List[str]:
    songs = []
    if SONG_FILE.exists():
        songs = [line.strip() for line in SONG_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    return songs or DEFAULT_SONGS


def choose_song_for_today(songs: List[str]) -> str:
    seed = int(dt.date.today().strftime("%Y%m%d"))
    random.seed(seed)
    return random.choice(songs)


def fetch_github_data() -> Dict:
    user = request_json(f"https://api.github.com/users/{USERNAME}")
    repos = request_json(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated"
    )
    events = request_json(f"https://api.github.com/users/{USERNAME}/events?per_page=30")

    total_stars = sum(repo.get("stargazers_count", 0) for repo in repos if not repo.get("fork", False))
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
    day_hash = hashlib.sha1(dt.date.today().isoformat().encode("utf-8")).hexdigest()
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
    repos_touched = set()

    for event in events:
        created_at = event.get("created_at")
        if not created_at:
            continue
        event_time = dt.datetime.strptime(created_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.UTC)
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
            title = (item.findtext("atom:title", default="Untitled", namespaces=ns) or "Untitled").strip()
            link_node = item.find("atom:link", ns)
            link = ""
            if link_node is not None:
                link = (link_node.attrib.get("href") or "").strip()
            if link:
                entries.append({"title": title, "link": link})

    return entries[:limit]


def generate_metrics_svg(public_repos: int, total_stars: int, followers: int, following: int):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    svg = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg width=\"900\" height=\"210\" viewBox=\"0 0 900 210\" xmlns=\"http://www.w3.org/2000/svg\">
  <defs>
    <linearGradient id=\"bg\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0%\" stop-color=\"#0f172a\"/>
      <stop offset=\"100%\" stop-color=\"#111827\"/>
    </linearGradient>
    <linearGradient id=\"accent\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"0\">
      <stop offset=\"0%\" stop-color=\"#06b6d4\"/>
      <stop offset=\"100%\" stop-color=\"#8b5cf6\"/>
    </linearGradient>
  </defs>

  <rect x=\"0\" y=\"0\" width=\"900\" height=\"210\" rx=\"18\" fill=\"url(#bg)\"/>
  <rect x=\"24\" y=\"20\" width=\"852\" height=\"6\" rx=\"3\" fill=\"url(#accent)\"/>

  <text x=\"34\" y=\"58\" fill=\"#e5e7eb\" font-size=\"24\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">Live Engineering Metrics</text>
  <text x=\"34\" y=\"82\" fill=\"#94a3b8\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Auto-updated via GitHub Actions + GitHub API</text>

  <text x=\"36\" y=\"130\" fill=\"#22d3ee\" font-size=\"18\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">{public_repos}</text>
  <text x=\"36\" y=\"152\" fill=\"#cbd5e1\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Public Repositories</text>

  <text x=\"250\" y=\"130\" fill=\"#a78bfa\" font-size=\"18\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">{total_stars}</text>
  <text x=\"250\" y=\"152\" fill=\"#cbd5e1\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Total Stars</text>

  <text x=\"420\" y=\"130\" fill=\"#22c55e\" font-size=\"18\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">{followers}</text>
  <text x=\"420\" y=\"152\" fill=\"#cbd5e1\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Followers</text>

  <text x=\"560\" y=\"130\" fill=\"#f59e0b\" font-size=\"18\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">{following}</text>
  <text x=\"560\" y=\"152\" fill=\"#cbd5e1\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Following</text>

    <text x=\"700\" y=\"130\" fill=\"#f472b6\" font-size=\"18\" font-family=\"Segoe UI, Arial\" font-weight=\"700\">{utc_now().strftime('%d %b %Y')}</text>
  <text x=\"700\" y=\"152\" fill=\"#cbd5e1\" font-size=\"13\" font-family=\"Segoe UI, Arial\">Last Refresh (UTC)</text>
</svg>
"""
    (ASSETS_DIR / "dynamic-metrics.svg").write_text(svg, encoding="utf-8")


def generate_activity_svg(events: List[Dict]):
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    lines = []
    for event in events[:4]:
        event_type = event.get("type", "Unknown")
        repo = event.get("repo", {}).get("name", "unknown/repo")
        lines.append(f"{event_type} • {repo}")

    while len(lines) < 4:
        lines.append("No recent public event found")

    safe_lines = [escape_xml(textwrap.shorten(line, width=65, placeholder="...")) for line in lines]

    svg = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<svg width=\"900\" height=\"220\" viewBox=\"0 0 900 220\" xmlns=\"http://www.w3.org/2000/svg\">
  <defs>
    <linearGradient id=\"bg\" x1=\"0\" y1=\"0\" x2=\"1\" y2=\"1\">
      <stop offset=\"0%\" stop-color=\"#020617\"/>
      <stop offset=\"100%\" stop-color=\"#111827\"/>
    </linearGradient>
  </defs>

  <rect x=\"0\" y=\"0\" width=\"900\" height=\"220\" rx=\"18\" fill=\"url(#bg)\"/>
  <text x=\"32\" y=\"44\" fill=\"#e2e8f0\" font-size=\"24\" font-family=\"Consolas, monospace\" font-weight=\"700\">Latest Public Activity</text>
  <text x=\"32\" y=\"68\" fill=\"#94a3b8\" font-size=\"13\" font-family=\"Consolas, monospace\">Live from GitHub Events API</text>

  <text x=\"34\" y=\"104\" fill=\"#22d3ee\" font-size=\"15\" font-family=\"Consolas, monospace\">1) {safe_lines[0]}</text>
  <text x=\"34\" y=\"132\" fill=\"#a78bfa\" font-size=\"15\" font-family=\"Consolas, monospace\">2) {safe_lines[1]}</text>
  <text x=\"34\" y=\"160\" fill=\"#34d399\" font-size=\"15\" font-family=\"Consolas, monospace\">3) {safe_lines[2]}</text>
  <text x=\"34\" y=\"188\" fill=\"#f472b6\" font-size=\"15\" font-family=\"Consolas, monospace\">4) {safe_lines[3]}</text>
</svg>
"""
    (ASSETS_DIR / "latest-activity.svg").write_text(svg, encoding="utf-8")


def update_readme(data: Dict):
    readme = README_PATH.read_text(encoding="utf-8")

    user = data["user"]
    repos = data["repos"]
    events = data["events"]
    total_stars = data["total_stars"]

    public_repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)

    metrics_block = "\n".join(
        [
            f"- 🚀 **Public repositories:** {public_repos}",
            f"- ⭐ **Total stars earned:** {total_stars}",
            f"- 👥 **Followers:** {followers}  |  **Following:** {following}",
            f"- 🕒 **Last refresh:** {utc_now().strftime('%d %b %Y, %H:%M UTC')}",
        ]
    )

    spotlight = pick_spotlight_repo(repos)
    if spotlight:
        repo_name = spotlight.get("name", "Unknown")
        repo_desc = spotlight.get("description") or "No description available."
        repo_desc = textwrap.shorten(repo_desc, width=140, placeholder="...")
        repo_lang = spotlight.get("language") or "Mixed"
        repo_url = spotlight.get("html_url", f"https://github.com/{USERNAME}")
        stars = spotlight.get("stargazers_count", 0)
        spotlight_block = (
            "### 🎲 Dynamic Project Spotlight\n"
            f"- **[{repo_name}]({repo_url})**\n"
            f"- **Stack:** {repo_lang}  |  **Stars:** {stars}\n"
            f"- **Summary:** {repo_desc}"
        )
    else:
        spotlight_block = "### 🎲 Dynamic Project Spotlight\n- No public repositories available yet."

    blog_entries = []
    for feed in BLOG_FEEDS[:3]:
        blog_entries.extend(parse_feed(feed, limit=2))

    if blog_entries:
        blog_block = "\n".join(
            [f"- 📝 [{entry['title']}]({entry['link']})" for entry in blog_entries[:3]]
        )
    else:
        latest_repos = repos[:3]
        if latest_repos:
            blog_block = "\n".join(
                [
                    f"- 🔭 [{repo.get('name', 'repo')}]({repo.get('html_url')}) — latest repo activity"
                    for repo in latest_repos
                ]
            )
        else:
            blog_block = "- No articles or repo updates available yet."

    quote = QUOTE_BANK[dt.date.today().toordinal() % len(QUOTE_BANK)]
    quote_block = f"> {quote}"

    weekly = summarize_week(events)
    weekly_block = "\n".join(
        [
            f"- ✅ Push events (7d): {weekly.get('PushEvent', 0)}",
            f"- 🔀 Pull request events (7d): {weekly.get('PullRequestEvent', 0)}",
            f"- 🐞 Issue events (7d): {weekly.get('IssuesEvent', 0)}",
            f"- 🧭 Repositories touched (7d): {weekly.get('repos_touched', 0)}",
        ]
    )

    songs = load_songs()
    song = choose_song_for_today(songs)
    SONG_FILE.write_text("\n".join(songs) + "\n", encoding="utf-8")

    readme = replace_between(readme, "<!-- DYNAMIC_METRICS_START -->", "<!-- DYNAMIC_METRICS_END -->", metrics_block)
    readme = replace_between(readme, "<!-- RANDOM_PROJECT_START -->", "<!-- RANDOM_PROJECT_END -->", spotlight_block)
    readme = replace_between(readme, "<!-- BLOG_POSTS_START -->", "<!-- BLOG_POSTS_END -->", blog_block)
    readme = replace_between(readme, "<!-- DAILY_QUOTE_START -->", "<!-- DAILY_QUOTE_END -->", quote_block)
    readme = replace_between(readme, "<!-- WEEKLY_SUMMARY_START -->", "<!-- WEEKLY_SUMMARY_END -->", weekly_block)

    if "<!-- RANDOM_SONG -->" in readme:
        marker = "<!-- RANDOM_SONG -->"
        marker_index = readme.find(marker)
        endline = readme.find("\n", marker_index)
        second_line_start = endline + 1
        second_line_end = readme.find("\n", second_line_start)
        if second_line_end == -1:
            second_line_end = len(readme)
        readme = (
            readme[:second_line_start]
            + f"🎧 **Now Playing:** {song}"
            + readme[second_line_end:]
        )

    README_PATH.write_text(readme, encoding="utf-8")
    generate_metrics_svg(public_repos, total_stars, followers, following)
    generate_activity_svg(events)


def main():
    data = fetch_github_data()
    update_readme(data)


if __name__ == "__main__":
    main()
