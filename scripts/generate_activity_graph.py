#!/usr/bin/env python3
"""Generate a self-hosted GitHub contribution activity chart."""
import json
import os
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "TomerGamerTV")
OUTPUT = Path("assets/github-activity.svg")
QUERY = """query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays { date contributionCount }
        }
      }
    }
  }
}"""


def get_contributions(username, token):
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required")
    req = Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": username}}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "github-profile-activity-chart",
        },
        method="POST",
    )
    with urlopen(req, timeout=30) as response:
        result = json.load(response)
    if result.get("errors"):
        raise RuntimeError(f"GitHub API error: {result['errors']}")
    user = result.get("data", {}).get("user")
    if user is None:
        raise RuntimeError(f"No GitHub user found: {username}")
    return {
        entry["date"]: int(entry["contributionCount"])
        for week in user["contributionsCollection"]["contributionCalendar"]["weeks"]
        for entry in week["contributionDays"]
    }


def render_svg(username, daily, today):
    dates = [today - timedelta(days=30 - i) for i in range(31)]
    counts = [max(0, daily.get(d.isoformat(), 0)) for d in dates]
    total = sum(counts)
    active = sum(n > 0 for n in counts)
    peak = max(counts)
    ceiling = max(5, ((peak + 4) // 5) * 5)
    left, right, top, bottom = 50, 885, 91, 213
    bar_width = 17
    gap = ((right - left) - len(counts) * bar_width) / (len(counts) - 1)
    name = escape(username)
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="260" viewBox="0 0 920 260" role="img" aria-labelledby="chart-title chart-desc">',
        f'<title id="chart-title">{name} GitHub contribution activity over the last 31 days</title>',
        f'<desc id="chart-desc">{total} contributions across {active} active days, through {today.isoformat()}.</desc>',
        '<rect width="920" height="260" rx="16" fill="#0d1117"/>',
        '<rect x="0.5" y="0.5" width="919" height="259" rx="15.5" fill="none" stroke="#30363d"/>',
        '<text x="34" y="43" font-family="Arial,sans-serif" font-size="19" font-weight="700" fill="#e6edf3">CONTRIBUTION ACTIVITY</text>',
        f'<text x="34" y="68" font-family="Arial,sans-serif" font-size="13" fill="#8b949e">Last 31 days · {dates[0].strftime("%b %d")} – {today.strftime("%b %d, %Y")}</text>',
        f'<text x="886" y="43" font-family="Arial,sans-serif" font-size="18" font-weight="700" fill="#3fb950" text-anchor="end">{total} contributions</text>',
        f'<text x="886" y="65" font-family="Arial,sans-serif" font-size="13" fill="#8b949e" text-anchor="end">{active} active days</text>',
    ]
    for fraction in (0, 0.5, 1):
        y = bottom - round((bottom - top) * fraction)
        n = round(ceiling * fraction)
        out.append(f'<line x1="{left-8}" x2="{right+8}" y1="{y}" y2="{y}" stroke="#21262d" stroke-width="1"/>')
        out.append(f'<text x="{left-16}" y="{y+4}" font-family="Arial,sans-serif" font-size="11" fill="#8b949e" text-anchor="end">{n}</text>')
    for i, (day, n) in enumerate(zip(dates, counts)):
        x = left + i * (bar_width + gap)
        height = max(3, round((bottom - top) * n / ceiling)) if n else 3
        color = "#3fb950" if n else "#30363d"
        out.append(f'<rect x="{x:.1f}" y="{bottom-height}" width="{bar_width}" height="{height}" rx="3" fill="{color}"/>')
        if i in (0, 7, 14, 21, 28):
            out.append(f'<text x="{x:.1f}" y="240" font-family="Arial,sans-serif" font-size="12" fill="#8b949e">{day.strftime("%b %d")}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    today = datetime.now(timezone.utc).date()
    daily = get_contributions(USERNAME, os.environ.get("GITHUB_TOKEN"))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(render_svg(USERNAME, daily, today), encoding="utf-8")
    print(f"Updated {OUTPUT}")


if __name__ == "__main__":
    main()
