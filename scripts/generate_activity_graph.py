#!/usr/bin/env python3
"""Generate a self-hosted GitHub contribution activity chart."""
import json
import os
import re
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from urllib.request import Request, urlopen

USERNAME = os.environ.get("GITHUB_USERNAME", "TomerGamerTV")
OUTPUT_LIGHT = Path("assets/github-activity-light.svg")
OUTPUT_DARK = Path("assets/github-activity-dark.svg")
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


def _smooth_line(points):
    """Use monotone cubic interpolation: smooth without artificial spikes."""
    if not points:
        return ""
    if len(points) == 1:
        return f"M {points[0][0]:.2f} {points[0][1]:.2f}"
    dx = points[1][0] - points[0][0]
    secants = [(points[i+1][1] - points[i][1]) / dx for i in range(len(points)-1)]
    slopes = [secants[0]]
    for a, b in zip(secants, secants[1:]):
        slopes.append(0.0 if a * b <= 0 else 2 * a * b / (a + b))
    slopes.append(secants[-1])
    parts = [f"M {points[0][0]:.2f} {points[0][1]:.2f}"]
    for i in range(len(points)-1):
        x1, y1 = points[i]
        x2, y2 = points[i+1]
        step = (x2-x1) / 3
        parts.append(
            f"C {x1+step:.2f} {y1+step*slopes[i]:.2f}, "
            f"{x2-step:.2f} {y2-step*slopes[i+1]:.2f}, "
            f"{x2:.2f} {y2:.2f}"
        )
    return " ".join(parts)


def render_svg(username, daily, today, theme="light"):
    dates = [today - timedelta(days=30-i) for i in range(31)]
    counts = [max(0, int(daily.get(d.isoformat(), 0))) for d in dates]
    total = sum(counts)
    active = sum(n > 0 for n in counts)
    high = max(counts)
    ceiling = max(5, ((high + 4) // 5) * 5)

    x_left, x_right, y_top, y_bottom = 37, 856, 84, 226
    def xy(index, value):
        return (
            x_left + (x_right-x_left)*index/30,
            y_bottom - (y_bottom-y_top)*value/ceiling
        )
    points = [xy(i, n) for i, n in enumerate(counts)]
    line = _smooth_line(points)
    area = f"{line} L {x_right} {y_bottom} L {x_left} {y_bottom} Z"

    focus_i = max(range(31), key=lambda i: (counts[i], i))
    focus_x, focus_y = points[focus_i]
    focus_value = counts[focus_i]
    focus_date = dates[focus_i].strftime("%b %d, %Y")
    bubble_x = max(x_left, min(x_right-144, focus_x-72))
    bubble_y = max(62, focus_y-59)

    name = escape(username)
    out = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="920" height="288" viewBox="0 0 920 288" role="img" aria-labelledby="chart-title chart-desc">',
        f'<title id="chart-title">{name} GitHub contribution activity over the last 31 days</title>',
        f'<desc id="chart-desc">{total} contributions across {active} active days through {today.isoformat()}. Peak {focus_value} on {dates[focus_i].isoformat()}.</desc>',
        '<defs>',
        '<linearGradient id="activity-fill" x1="0" y1="0" x2="0" y2="1">',
        '<stop offset="0%" stop-color="#2da44e" stop-opacity=".22"/>',
        '<stop offset="100%" stop-color="#2da44e" stop-opacity=".015"/>',
        '</linearGradient>',
        '</defs>',
        '<rect x=".5" y=".5" width="919" height="287" rx="12" fill="#ffffff" stroke="#eaeef2"/>',
        f'<text x="35" y="31" font-family="Arial,sans-serif" font-size="19" font-weight="700" fill="#1f883d">{total:,} contributions</text>',
        f'<text x="35" y="51" font-family="Arial,sans-serif" font-size="12" fill="#8c959f">Last 31 days  ·  {dates[0].strftime("%b %d")} – {today.strftime("%b %d, %Y")}</text>',
        f'<text x="882" y="31" font-family="Arial,sans-serif" text-anchor="end" font-size="12" font-weight="600" fill="#57606a">{active} active days</text>',
    ]
    for fraction in (0, .5, 1):
        y = y_bottom - (y_bottom-y_top)*fraction
        value = round(ceiling * fraction)
        out.append(f'<line x1="{x_left}" y1="{y:.2f}" x2="{x_right}" y2="{y:.2f}" stroke="#eaeef2" stroke-width="1"/>')
        out.append(f'<text x="{x_right+15}" y="{y+4:.2f}" font-family="Arial,sans-serif" font-size="11" fill="#8c959f">{value}</text>')

    out.extend([
        f'<path d="{area}" fill="url(#activity-fill)"/>',
        f'<path d="{line}" fill="none" stroke="#2da44e" stroke-width="2.7" stroke-linecap="round" stroke-linejoin="round"/>',
        f'<line x1="{focus_x:.2f}" y1="{y_top}" x2="{focus_x:.2f}" y2="{y_bottom}" stroke="#1f883d" stroke-opacity=".30" stroke-width="1"/>',
        f'<circle cx="{focus_x:.2f}" cy="{focus_y:.2f}" r="5" fill="#ffffff" stroke="#1f883d" stroke-width="2.5"/>',
        f'<rect x="{bubble_x:.2f}" y="{bubble_y:.2f}" width="144" height="46" rx="8" fill="#ffffff" stroke="#d0d7de"/>',
        f'<text x="{bubble_x+10:.2f}" y="{bubble_y+18:.2f}" font-family="Arial,sans-serif" font-size="13" font-weight="700" fill="#1f883d">{focus_value} contributions</text>',
        f'<text x="{bubble_x+10:.2f}" y="{bubble_y+35:.2f}" font-family="Arial,sans-serif" font-size="11" fill="#8c959f">{focus_date}</text>',
    ])
    for i in (0, 6, 12, 18, 24, 30):
        x, _ = points[i]
        anchor = "start" if i == 0 else ("end" if i == 30 else "middle")
        out.append(
            f'<text x="{x:.2f}" y="263" text-anchor="{anchor}" font-family="Arial,sans-serif" font-size="11" fill="#8c959f">{dates[i].strftime("%b %d")}</text>'
        )
    out.append("</svg>")
    svg = "\n".join(out) + "\n"
    if theme == "dark":
        # Preserve layout and contribution values; switch only the palette.
        dark_palette = {
            "#ffffff": "#0d1117",
            "#eaeef2": "#30363d",
            "#1f883d": "#3fb950",
            "#8c959f": "#8b949e",
            "#57606a": "#8b949e",
            "#2da44e": "#3fb950",
            "#d0d7de": "#30363d",
        }
        svg = re.sub(
            r"#[0-9a-fA-F]{6}",
            lambda match: dark_palette.get(match.group(0).lower(), match.group(0)),
            svg,
        )
    elif theme != "light":
        raise ValueError(f"Unsupported color theme: {theme}")
    return svg

def main():
    today = datetime.now(timezone.utc).date()
    daily = get_contributions(USERNAME, os.environ.get("GITHUB_TOKEN"))
    OUTPUT_LIGHT.parent.mkdir(parents=True, exist_ok=True)
    for output, theme in ((OUTPUT_LIGHT, "light"), (OUTPUT_DARK, "dark")):
        output.write_text(render_svg(USERNAME, daily, today, theme=theme), encoding="utf-8")
        print(f"Updated {output}")


if __name__ == "__main__":
    main()
