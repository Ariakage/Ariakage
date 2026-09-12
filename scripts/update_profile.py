#!/usr/bin/env python3
"""Build self-hosted profile cards from public GitHub data; Python stdlib only."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from html import escape
from html.parser import HTMLParser
import json
import math
import os
from pathlib import Path
import re
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
THEMES = {
    "light": dict(bg="#f6faff", border="#dce8f4", text="#233954", muted="#5d728a", blue="#2889ce", pink="#d96280", grid="#e3edf7", fill="#d4eaff"),
    "dark": dict(bg="#101b2a", border="#253b52", text="#e7f2ff", muted="#a0b5cc", blue="#82caff", pink="#f49bb2", grid="#24374b", fill="#193a55"),
}
LANG_COLORS = ["#69b8ef", "#ec9bb3", "#90cfc6", "#b8acf1", "#adbfd1"]


def fetch(url, *, json_response=True):
    headers = {"User-Agent": "Ariakage-profile", "Accept": "application/vnd.github+json" if json_response else "text/html", "Accept-Language": "en-US"}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    for attempt in range(3):
        try:
            with urlopen(Request(url, headers=headers), timeout=30) as response:
                body = response.read().decode("utf-8")
            return json.loads(body) if json_response else body
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


class ContributionParser(HTMLParser):
    """Read dates and exact counts from GitHub's public, unauthenticated calendar."""

    def __init__(self):
        super().__init__()
        self.cells = {}
        self.counts = {}
        self.tooltip = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get("data-date") and attrs.get("id"):
            self.cells[attrs["id"]] = attrs["data-date"]
        if tag == "tool-tip":
            self.tooltip = attrs.get("for")
            self.parts = []

    def handle_data(self, data):
        if self.tooltip:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "tool-tip" and self.tooltip:
            match = re.match(r"(No|[\d,]+) contributions? on ", "".join(self.parts).strip())
            if match:
                self.counts[self.tooltip] = 0 if match[1] == "No" else int(match[1].replace(",", ""))
            self.tooltip = None

    def calendar(self, end):
        start = end - timedelta(days=364)
        days = sorted([
            {"date": day, "count": self.counts[key]}
            for key, day in self.cells.items()
            if start.isoformat() <= day <= end.isoformat() and key in self.counts
        ], key=lambda day: day["date"])
        expected = [(start + timedelta(days=i)).isoformat() for i in range(365)]
        if [day["date"] for day in days] != expected:
            raise ValueError("Public calendar is incomplete or GitHub markup changed; keeping the last successful cards.")
        return days


def collect(username, today):
    repos = []
    page = 1
    while True:
        batch = fetch(f"https://api.github.com/users/{username}/repos?type=owner&per_page=100&page={page}")
        repos.extend(repo for repo in batch if not repo["private"])
        if len(batch) < 100:
            break
        page += 1
    originals = [repo for repo in repos if not repo["fork"]]
    languages = Counter()
    with ThreadPoolExecutor(max_workers=4) as pool:
        for sizes in pool.map(lambda repo: fetch(repo["languages_url"]), originals):
            languages.update(sizes)
    parser = ContributionParser()
    # No authorization header or cookies are sent to this public page.
    # Date query parameters select a calendar year on GitHub, not a rolling range.
    parser.feed(fetch(f"https://github.com/users/{username}/contributions", json_response=False))
    return {
        "username": username,
        "updated": today.isoformat(),
        "public_repos": len(repos),
        "stars": sum(repo["stargazers_count"] for repo in originals),
        "languages": dict(languages.most_common()),
        "days": parser.calendar(today),
    }


def text(x, y, value, *, size=14, color="text", weight=400, extra=""):
    return f'<text x="{x}" y="{y}" class="{color}" font-size="{size}" font-weight="{weight}" {extra}>{escape(str(value))}</text>'


def shell(width, height, theme, title, description, body):
    p = THEMES[theme]
    css = "".join(f".{key}{{fill:{value}}}" for key, value in p.items())
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title description">
<title id="title">{escape(title)}</title><desc id="description">{escape(description)}</desc>
<style>text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif}}{css}
.signal{{animation:breathe 3.6s ease-in-out infinite}}@keyframes breathe{{50%{{opacity:.3}}}}
.trace{{stroke-dasharray:28 972;animation:travel 10s linear infinite}}@keyframes travel{{to{{stroke-dashoffset:-1000}}}}
@media(prefers-reduced-motion:reduce){{.signal,.trace{{animation:none}}.trace{{display:none}}}}
</style><rect x=".5" y=".5" width="{width - 1}" height="{height - 1}" rx="18" fill="{p['bg']}" stroke="{p['border']}"/>{body}</svg>\n'''


def overview(data, theme):
    total = sum(day["count"] for day in data["days"])
    active = sum(day["count"] > 0 for day in data["days"])
    body = text(28, 35, "01 / GITHUB AT A GLANCE", size=11, color="muted", weight=600, extra='letter-spacing="1.6"')
    body += '<circle cx="428" cy="30" r="4" class="blue signal"/>'
    for x, y, value, label, color in [(28, 96, total, "Contributions · past 365 days", "blue"), (254, 96, active, "Days creating · past 365 days", "pink"), (28, 188, data["public_repos"], "Public repositories", "text"), (254, 188, data["stars"], "Stars · original public repos", "text")]:
        body += text(x, y, f"{value:,}", size=40, weight=650, color=color)
        body += text(x, y + 25, label, size=11, color="muted")
    body += text(28, 249, f"PUBLIC PROFILE / UPDATED {data['updated']} UTC", size=9, color="muted", extra='letter-spacing=".8"')
    return shell(460, 270, theme, "Ariakage's GitHub overview", f"{total} contributions and {active} active days over the past 365 days; {data['public_repos']} public repositories; {data['stars']} stars on original public repositories.", body)


def language_mix(data, theme):
    entries = sorted(data["languages"].items(), key=lambda item: (-item[1], item[0]))
    total = sum(size for _, size in entries)
    entries = entries[:4] + ([("Other", sum(size for _, size in entries[4:]))] if len(entries) > 4 else [])
    body = text(28, 35, "02 / LANGUAGE PALETTE", size=11, color="muted", weight=600, extra='letter-spacing="1.6"')
    body += text(28, 62, "A little of everything I build with.", size=13, color="muted")
    left = 28
    for i, (name, size) in enumerate(entries):
        width = size / total * 404 if total else 0
        body += f'<rect x="{left:.2f}" y="83" width="{width:.2f}" height="12" fill="{LANG_COLORS[i]}"/>'
        left += width
        col, row = i % 2, i // 2
        x, y = 28 + col * 216, 129 + row * 33
        body += f'<circle cx="{x + 4}" cy="{y - 4}" r="4" fill="{LANG_COLORS[i]}"/>'
        body += text(x + 16, y, name, size=12)
        body += text(x + 188, y, f"{size / total:.1%}", size=11, color="muted", extra='text-anchor="end"')
    if not total:
        body += text(28, 130, "No public language data yet.", color="muted")
    body += text(28, 227, "By code bytes in original public repositories.", size=11, color="muted")
    body += text(28, 247, "A snapshot of code, not a measure of proficiency.", size=10, color="muted")
    return shell(460, 270, theme, "Languages in Ariakage's public repositories", "; ".join(f"{name}: {size / total:.1%}" for name, size in entries) if total else "No language data", body)


def weekly_totals(days):
    weeks = {}
    for item in days:
        day = date.fromisoformat(item["date"])
        monday = day - timedelta(days=day.weekday())
        weeks[monday.isoformat()] = weeks.get(monday.isoformat(), 0) + item["count"]
    return list(sorted(weeks.items()))[-12:]


def activity(data, theme, mobile=False):
    p = THEMES[theme]
    width, left, right = (480, 40, 448) if mobile else (960, 62, 920)
    weeks = weekly_totals(data["days"])
    top = max(10, math.ceil(max(value for _, value in weeks) / 10) * 10)
    points = [(left + i * (right - left) / 11, 229 - value / top * 126) for i, (_, value) in enumerate(weeks)]
    path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    body = text(30, 36, "03 / THE RHYTHM OF BUILDING", size=12, color="muted", weight=600, extra='letter-spacing="1.6"')
    body += text(30, 65, "Small steps, a growing constellation.", size=19, weight=600)
    if not mobile:
        body += text(930, 36, "LAST 12 WEEKS", size=11, color="blue", extra='text-anchor="end" letter-spacing="1"')
    for fraction in (0, .5, 1):
        y = 229 - fraction * 126
        body += f'<path d="M{left} {y}H{right}" stroke="{p["grid"]}" stroke-dasharray="3 6"/>'
        body += text(left - 12, y + 4, f"{top * fraction:g}", size=10, color="muted", extra='text-anchor="end"')
    body += f'<path d="{path} L{right},229 L{left},229 Z" fill="{p["fill"]}" opacity=".6"/>'
    body += f'<path d="{path}" fill="none" stroke="{p["blue"]}" stroke-width="2.5" stroke-linejoin="round"/>'
    body += f'<path class="trace" d="{path}" pathLength="1000" fill="none" stroke="{p["pink"]}" stroke-width="3.5" stroke-linecap="round"/>'
    for (day, value), (x, y) in zip(weeks, points):
        body += f'<circle cx="{x}" cy="{y}" r="3.5" fill="{p["bg"]}" stroke="{p["blue"]}" stroke-width="2"><title>{day}: {value} contributions</title></circle>'
        body += text(x, 252, day[5:].replace("-", "/"), size=10, color="muted", extra='text-anchor="middle"')
    body += text(30, 282, "Contributions per week · Monday start · Current week is partial", size=10 if mobile else 11, color="muted")
    if mobile:
        body += text(30, 301, f"LAST 12 WEEKS / UPDATED {data['updated']} UTC", size=9, color="muted")
    else:
        body += text(930, 286, f"UPDATED {data['updated']} UTC", size=10, color="muted", extra='text-anchor="end"')
    return shell(width, 320 if mobile else 310, theme, "Ariakage's weekly contribution activity", "; ".join(f"Week of {day}: {value}" for day, value in weeks), body)


def render(data, output):
    cards = {}
    for theme in THEMES:
        for name, build in [("overview", overview), ("languages", language_mix), ("activity", activity)]:
            svg = build(data, theme)
            ET.fromstring(svg)  # Validate every image before replacing any existing output.
            cards[f"{name}-{theme}.svg"] = svg
        svg = activity(data, theme, mobile=True)
        ET.fromstring(svg)
        cards[f"activity-mobile-{theme}.svg"] = svg
    output.mkdir(parents=True, exist_ok=True)
    for name, svg in cards.items():
        temporary = output / (name + ".tmp")
        temporary.write_text(svg, encoding="utf-8")
        temporary.replace(output / name)
    (output / "profile-data.json").write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--username", default="Ariakage")
    parser.add_argument("--from-json", type=Path, help="Render a saved public-data snapshot without network access")
    parser.add_argument("--output", type=Path, default=ROOT / "assets/generated")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?", args.username):
        parser.error("Invalid GitHub username")
    data = json.loads(args.from_json.read_text()) if args.from_json else collect(args.username, datetime.now(timezone.utc).date())
    render(data, args.output)
    print(f"Generated 8 cards for {data['username']} from public data dated {data['updated']}.")


if __name__ == "__main__":
    main()
