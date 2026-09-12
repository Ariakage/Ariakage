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
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
THEMES = {
    "light": dict(bg="#f6faff", border="#dce8f4", text="#233954", muted="#5d728a", blue="#2889ce", pink="#d96280", grid="#e3edf7", fill="#d4eaff"),
    "dark": dict(bg="#101b2a", border="#253b52", text="#e7f2ff", muted="#a0b5cc", blue="#82caff", pink="#f49bb2", grid="#24374b", fill="#193a55"),
}
LANG_COLORS = ["#69b8ef", "#ec9bb3", "#90cfc6", "#b8acf1", "#adbfd1"]


def fetch(url, *, json_response=True, payload=None):
    headers = {"User-Agent": "Ariakage-profile", "Accept": "application/vnd.github+json" if json_response else "text/html", "Accept-Language": "en-US"}
    if url.startswith("https://api.github.com/") and os.environ.get("GITHUB_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GITHUB_TOKEN"]
    if payload is not None:
        headers["Content-Type"] = "application/json"
    body_data = json.dumps(payload).encode() if payload is not None else None
    for attempt in range(3):
        try:
            with urlopen(Request(url, data=body_data, headers=headers), timeout=30) as response:
                body = response.read().decode("utf-8")
            return json.loads(body) if json_response else body
        except (HTTPError, URLError, TimeoutError) as error:
            if isinstance(error, HTTPError) and error.code not in (429, 500, 502, 503, 504):
                raise
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


def search_count(kind, query):
    """Never turn an incomplete search response into a published statistic."""
    for attempt in range(3):
        result = fetch(f"https://api.github.com/search/{kind}?" + urlencode({"q": query + " is:public", "per_page": 1}))
        if result.get("incomplete_results") is False:
            count = result["total_count"]
            if type(count) is not int or count < 0:
                raise ValueError("Invalid GitHub search count")
            return count
        if attempt < 2:
            time.sleep(2 ** attempt)
    raise ValueError("GitHub search returned incomplete results; keeping previous cards.")


def collect_collaboration(username, today, stars):
    if not os.environ.get("GITHUB_TOKEN"):
        raise ValueError("GITHUB_TOKEN is required for the contribution-rating GraphQL query. Offline rendering works without a token.")
    queries = {
        "commits": ("commits", f"author:{username}"),
        "prs": ("issues", f"author:{username} type:pr"),
        "prs_merged": ("issues", f"author:{username} type:pr is:merged"),
        "prs_open": ("issues", f"author:{username} type:pr is:open"),
        "issues": ("issues", f"author:{username} type:issue"),
    }
    # Keep search requests sequential to avoid GitHub's secondary rate limit.
    stats = {name: search_count(*query) for name, query in queries.items()}
    if stats["prs_merged"] + stats["prs_open"] > stats["prs"]:
        raise ValueError("PR counts changed during collection; keeping previous cards.")
    query = '''query($login:String!, $from:DateTime!, $after:String) {
      user(login:$login) {
        followers { totalCount }
        repositoriesContributedTo(first:1, privacy:PUBLIC,
          contributionTypes:[COMMIT, ISSUE, PULL_REQUEST, REPOSITORY]) { totalCount }
        contributionsCollection(from:$from) {
          pullRequestReviewContributions(first:100, after:$after) {
            nodes { repository { isPrivate } }
            pageInfo { hasNextPage endCursor }
          }
        }
      }
    }'''
    stats.update(stars=stars, reviews=0)
    after = None
    while True:
        result = fetch("https://api.github.com/graphql", payload={"query": query, "variables": {
            "login": username, "from": str(today - timedelta(days=364)) + "T00:00:00Z", "after": after,
        }})
        if result.get("errors") or not result.get("data", {}).get("user"):
            raise ValueError("GitHub GraphQL could not return complete contribution-rating data.")
        user = result["data"]["user"]
        stats["followers"] = user["followers"]["totalCount"]
        stats["contributed_repos"] = user["repositoriesContributedTo"]["totalCount"]
        reviews = user["contributionsCollection"]["pullRequestReviewContributions"]
        # Filtering also keeps local runs with a broad token strictly public.
        stats["reviews"] += sum(not item["repository"]["isPrivate"] for item in reviews["nodes"])
        if not reviews["pageInfo"]["hasNextPage"]:
            return stats
        cursor = reviews["pageInfo"]["endCursor"]
        if not cursor or cursor == after:
            raise ValueError("Invalid GitHub review pagination cursor")
        after = cursor


def calculate_rank(stats):
    """GitHub Readme Stats formula, include_all_commits=true (MIT).

    Port of anuraghazra/github-readme-stats src/calculateRank.js at
    54a7985aeefda00d5eadb55b80c17c7f976c37d2. See docs/GITHUB-README-STATS-LICENSE.
    This is a formula-derived indicator, not an observed global leaderboard.
    """
    exponential = [("commits", 1000, 2), ("prs", 50, 3), ("issues", 25, 1), ("reviews", 2, 1)]
    logarithmic = [("stars", 50, 4), ("followers", 10, 1)]
    weighted = sum(weight * (1 - 2 ** (-stats[key] / median)) for key, median, weight in exponential)
    weighted += sum(weight * (stats[key] / median) / (1 + stats[key] / median) for key, median, weight in logarithmic)
    percentile = 100 * (1 - weighted / 12)
    thresholds = [(1, "S"), (12.5, "A+"), (25, "A"), (37.5, "A-"), (50, "B+"), (62.5, "B"), (75, "B-"), (87.5, "C+"), (100, "C")]
    level = next(level for threshold, level in thresholds if percentile <= threshold)
    return {"level": level, "percentile": percentile, "score": 100 - percentile}


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
        "collaboration": collect_collaboration(username, today, sum(repo["stargazers_count"] for repo in repos)),
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


def rating(data, theme):
    p = THEMES[theme]
    stats = data["collaboration"]
    rank = calculate_rank(stats)
    body = text(28, 35, "03 / CONTRIBUTION RATING", size=11, color="muted", weight=600, extra='letter-spacing="1.6"')
    body += text(28, 60, "Every contribution leaves a mark.", size=13, color="muted")
    body += f'<circle cx="106" cy="151" r="57" fill="none" stroke="{p["grid"]}" stroke-width="8"/>'
    body += f'<circle cx="106" cy="151" r="57" pathLength="100" fill="none" stroke="{p["blue"]}" stroke-width="8" stroke-linecap="round" stroke-dasharray="{rank["score"]:.4f} 100" transform="rotate(-90 106 151)"/>'
    body += text(106, 150, rank["level"], size=43, weight=650, color="blue", extra='text-anchor="middle"')
    body += text(106, 174, "GRS RANK", size=10, color="muted", extra='text-anchor="middle" letter-spacing="1.3"')
    body += text(106, 233, f"{rank['score']:.1f} / 100", size=14, weight=600, color="pink", extra='text-anchor="middle"')
    for i, (key, label) in enumerate([("commits", "Commits · all time"), ("issues", "Issues opened · all time"), ("reviews", "PR reviews · past year"), ("contributed_repos", "Repos contributed · year"), ("stars", "Stars · all public repos"), ("followers", "Followers")]):
        y = 91 + i * 29
        body += text(190, y, label, size=11, color="muted")
        body += text(432, y, f"{stats[key]:,}", size=14, weight=600, extra='text-anchor="end"')
    body += text(28, 273, "GitHub Readme Stats formula · Public activity", size=10, color="muted")
    body += text(28, 291, "Formula-based indicator, not an official GitHub rating.", size=10, color="muted")
    desc = f"GitHub Readme Stats rank {rank['level']}; formula score {rank['score']:.1f} out of 100. " + "; ".join(f"{key}: {stats[key]}" for key in ("commits", "issues", "reviews", "contributed_repos", "stars", "followers"))
    return shell(460, 312, theme, "Ariakage's contribution rating", desc, body)


def pull_requests(data, theme):
    stats = data["collaboration"]
    merged_rate = stats["prs_merged"] / stats["prs"] if stats["prs"] else None
    rate_label = f"{merged_rate:.1%}" if merged_rate is not None else "—"
    body = text(28, 35, "04 / PULL REQUESTS", size=11, color="muted", weight=600, extra='letter-spacing="1.6"')
    body += '<circle cx="428" cy="30" r="4" class="blue signal"/>'
    for x, y, value, label, color in [(28, 103, f"{stats['prs']:,}", "PRs opened · all time", "blue"), (254, 103, f"{stats['prs_merged']:,}", "Merged · all time", "pink"), (28, 201, f"{stats['prs_open']:,}", "Currently open", "text"), (254, 201, rate_label, "Merged / all PRs", "text")]:
        body += text(x, y, value, size=38, weight=650, color=color)
        body += text(x, y + 26, label, size=11, color="muted")
    body += text(28, 273, "PRs I authored across public repositories.", size=11, color="muted")
    body += text(28, 291, f"UPDATED {data['updated']} UTC", size=9, color="muted", extra='letter-spacing=".8"')
    return shell(460, 312, theme, "Ariakage's pull requests", f"{stats['prs']} public authored PRs; {stats['prs_merged']} merged; {stats['prs_open']} open; merge rate {rate_label}.", body)


def activity(data, theme, mobile=False):
    p = THEMES[theme]
    width, left, right = (480, 40, 448) if mobile else (960, 62, 920)
    weeks = weekly_totals(data["days"])
    top = max(10, math.ceil(max(value for _, value in weeks) / 10) * 10)
    points = [(left + i * (right - left) / 11, 229 - value / top * 126) for i, (_, value) in enumerate(weeks)]
    path = "M " + " L ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    body = text(30, 36, "05 / THE RHYTHM OF BUILDING", size=12, color="muted", weight=600, extra='letter-spacing="1.6"')
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
        for name, build in [("overview", overview), ("languages", language_mix), ("rating", rating), ("pull-requests", pull_requests), ("activity", activity)]:
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
    print(f"Generated 12 cards for {data['username']} from public data dated {data['updated']}.")


if __name__ == "__main__":
    main()
