"""
Minimal dynamic profile updater.
Updates only the raw-metrics collapsible block in README.md.
Run by GitHub Actions every 12 hours.
"""

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"

USERNAME = os.getenv("PROFILE_USERNAME", "aryamehta0302")
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")


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


def replace_between(content: str, start_tag: str, end_tag: str, new_block: str) -> str:
    start = content.find(start_tag)
    end = content.find(end_tag)
    if start == -1 or end == -1 or end < start:
        return content
    start_idx = start + len(start_tag)
    return content[:start_idx] + "\n" + new_block.strip() + "\n" + content[end:]


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def fetch_github_data() -> dict:
    user = request_json(f"https://api.github.com/users/{USERNAME}")
    repos = request_json(
        f"https://api.github.com/users/{USERNAME}/repos?per_page=100&sort=updated"
    )
    total_stars = sum(
        repo.get("stargazers_count", 0)
        for repo in repos
        if not repo.get("fork", False)
    )
    return {"user": user, "total_stars": total_stars}


# ---------------------------------------------------------------------------
# README updater
# ---------------------------------------------------------------------------

def update_readme(data: dict):
    readme = README_PATH.read_text(encoding="utf-8")

    user = data["user"]
    total_stars = data["total_stars"]

    public_repos = user.get("public_repos", 0)
    followers = user.get("followers", 0)
    following = user.get("following", 0)

    metrics_block = "\n".join([
        f"- 🚀 **Public repositories:** {public_repos}",
        f"- ⭐ **Total stars earned:** {total_stars}",
        f"- 👥 **Followers:** {followers}  |  **Following:** {following}",
        f"- 🕒 **Last refresh:** {utc_now().strftime('%d %b %Y, %H:%M UTC')}",
    ])

    readme = replace_between(
        readme,
        "<!-- DYNAMIC_METRICS_START -->",
        "<!-- DYNAMIC_METRICS_END -->",
        metrics_block,
    )

    README_PATH.write_text(readme, encoding="utf-8")


def main():
    data = fetch_github_data()
    update_readme(data)


if __name__ == "__main__":
    main()
