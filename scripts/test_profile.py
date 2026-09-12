"""Boundary checks for public data and GitHub-compatible deliverables."""

from datetime import date, timedelta
import json
from pathlib import Path
import re
import tempfile
import unittest
import xml.etree.ElementTree as ET

from update_profile import ContributionParser, ROOT, render, weekly_totals


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
        data = {"username": "Ariakage", "updated": str(end), "public_repos": 0, "stars": 0, "languages": {}, "days": [{"date": str(end - timedelta(days=364-i)), "count": 0} for i in range(365)]}
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            for languages in ({}, {"C++ & <XML>": 100, "Python": 200}):
                data["languages"] = languages
                render(data, output)
                cards = list(output.glob("*.svg"))
                self.assertEqual(len(cards), 8)
                for card in cards:
                    svg = card.read_text()
                    ET.fromstring(svg)
                    self.assertNotIn("nan", svg.lower())
                    self.assertIn("prefers-reduced-motion", svg)

    def test_readme_local_links_and_images_exist(self):
        for name in ("README.md", "README_ZH_HANS.md"):
            source = (ROOT / name).read_text()
            refs = re.findall(r'(?:src|srcset|href)="(\./[^"#]+)"|\]\((\./[^)#]+)\)', source)
            for html, markdown in refs:
                self.assertTrue((ROOT / (html or markdown)).is_file(), f"{name}: missing {html or markdown}")

    def test_checked_in_images_are_self_contained_and_parseable(self):
        files = list((ROOT / "assets/generated").glob("*.svg"))
        self.assertEqual(len(files), 10)
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
