"""Boundary checks for public data and GitHub-compatible deliverables."""

from datetime import date, timedelta
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from update_profile import ContributionParser, ROOT, calculate_rank, collect_collaboration, render, search_count, weekly_totals


def empty_collaboration():
    return dict.fromkeys(("commits", "prs", "prs_merged", "prs_open", "issues", "reviews", "stars", "followers", "contributed_repos"), 0)


class RatingTests(unittest.TestCase):
    def test_original_algorithm_zero_and_median_reference_points(self):
        self.assertEqual(calculate_rank(empty_collaboration()), {"level": "C", "percentile": 100, "score": 0})
        result = calculate_rank(dict(commits=1000, prs=50, issues=25, reviews=2, stars=50, followers=10))
        self.assertEqual(result, {"level": "B+", "percentile": 50, "score": 50})

    @patch("update_profile.time.sleep")
    @patch("update_profile.fetch", return_value={"incomplete_results": True, "total_count": 5})
    def test_incomplete_search_never_becomes_a_rating(self, fetch_mock, sleep_mock):
        with self.assertRaises(ValueError):
            search_count("issues", "author:Ariakage type:pr")
        self.assertEqual(fetch_mock.call_count, 3)

    @patch.dict("os.environ", {"GITHUB_TOKEN": "test-token"})
    @patch("update_profile.search_count", return_value=0)
    def test_reviews_paginate_and_exclude_private_repositories(self, count_mock):
        def page(private_flags, has_next, cursor):
            return {"data": {"user": {"followers": {"totalCount": 5}, "repositoriesContributedTo": {"totalCount": 12}, "contributionsCollection": {"pullRequestReviewContributions": {"nodes": [{"repository": {"isPrivate": flag}} for flag in private_flags], "pageInfo": {"hasNextPage": has_next, "endCursor": cursor}}}}}}
        with patch("update_profile.fetch", side_effect=[page([False, True], True, "next"), page([False], False, None)]) as fetch_mock:
            result = collect_collaboration("Ariakage", date(2026, 9, 12), 20)
        self.assertEqual(result["reviews"], 2)
        self.assertEqual(result["contributed_repos"], 12)
        self.assertEqual(fetch_mock.call_args.kwargs["payload"]["variables"]["after"], "next")


class CalendarTests(unittest.TestCase):
    def test_exact_counts_and_dates_across_year_boundary(self):
        end = date(2026, 1, 15)
        parser = ContributionParser()
        for i in reversed(range(365)):
            day = end - timedelta(days=i)
            count = "1,234 contributions" if i == 0 else "No contributions"
            parser.feed(f'<td id="day-{i}" data-date="{day}" data-level="0"></td><tool-tip for="day-{i}">{count} on January 15th.</tool-tip>')
        days = parser.calendar(end)
        self.assertEqual(len(days), 365)
        self.assertEqual(days[0]["date"], "2025-01-16")
        self.assertEqual(days[-1], {"date": "2026-01-15", "count": 1234})

    def test_missing_calendar_fails_instead_of_fabricating_zeroes(self):
        with self.assertRaises(ValueError):
            ContributionParser().calendar(date(2026, 1, 15))

    def test_weekly_boundary_keeps_partial_current_week(self):
        days = [{"date": "2026-01-04", "count": 5}, {"date": "2026-01-05", "count": 2}, {"date": "2026-01-06", "count": 3}]
        self.assertEqual(weekly_totals(days), [("2025-12-29", 5), ("2026-01-05", 5)])


class OutputTests(unittest.TestCase):
    def test_zero_activity_and_special_characters_produce_valid_svg(self):
        end = date(2026, 1, 15)
        data = {"username": "Ariakage", "updated": str(end), "public_repos": 0, "stars": 0, "collaboration": empty_collaboration(), "languages": {}, "days": [{"date": str(end - timedelta(days=364-i)), "count": 0} for i in range(365)]}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for languages in ({}, {"C++ & <XML>": 100, "Python": 200}):
                data["languages"] = languages
                render(data, output)
                cards = list(output.glob("*.svg"))
                self.assertEqual(len(cards), 12)
                for card in cards:
                    svg = card.read_text()
                    ET.fromstring(svg)
                    self.assertNotIn("nan", svg.lower())
                    self.assertIn("prefers-reduced-motion", svg)
                self.assertIn("merge rate —", (output / "pull-requests-light.svg").read_text())

    def test_readme_local_links_and_images_exist(self):
        for name in ("README.md", "README_ZH_HANS.md"):
            source = (ROOT / name).read_text()
            refs = re.findall(r'(?:src|srcset|href)="(\./[^"#]+)"|\]\((\./[^)#]+)\)', source)
            for html, markdown in refs:
                self.assertTrue((ROOT / (html or markdown)).is_file(), f"{name}: missing {html or markdown}")

    def test_checked_in_images_are_self_contained_and_parseable(self):
        files = list((ROOT / "assets/generated").glob("*.svg"))
        self.assertEqual(len(files), 14)
        for path in files:
            svg = path.read_text()
            ET.fromstring(svg)
            self.assertNotIn("<script", svg)
            self.assertNotIn("<foreignObject", svg)
            self.assertNotRegex(svg, r'(?:href|src)=[\"\']https?://')
            self.assertIn("prefers-reduced-motion", svg)

    def test_saved_calendar_is_contiguous_and_nonnegative(self):
        data = json.loads((ROOT / "assets/generated/profile-data.json").read_text())
        self.assertEqual(len(data["days"]), 365)
        end = date.fromisoformat(data["updated"])
        for i, day in enumerate(data["days"]):
            self.assertEqual(day["date"], str(end - timedelta(days=364-i)))
            self.assertGreaterEqual(day["count"], 0)


if __name__ == "__main__":
    unittest.main()
