"""Renderer tests. Run from the repo root:

    python -m unittest discover -s initiatives/status-report-automation/cowork-skill-v3/tests -v

Golden files were rendered by the renderer before managed services was added, so
the golden tests prove non-managed reports are unchanged. All data is made up.
"""
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parent
FIXTURES = HERE / "fixtures"
SCRIPT = HERE.parent / "scripts" / "build_report.py"

MANAGED = {
    "client": "Contoso Landscaping",
    "report_date": "October 9, 2026",
    "managed_services": True,
    "monthly_budget_hours": "30",
    "hours_as_of": "October 9, 2026",
    "pm": "Chris Lee",
    "lead_consultant": "Dana Reed",
    "account_manager": "Pat Ray",
    "summary": "Two backlog items closed this week.",
    "signature": {"name": "Dana Reed", "firm": "Eide Bailly"},
}


def render(content, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        src = pathlib.Path(tmp) / "content.json"
        out = pathlib.Path(tmp) / "out.html"
        src.write_text(json.dumps(content), encoding="utf-8")
        proc = subprocess.run([sys.executable, str(SCRIPT), str(src), str(out), *flags],
                              capture_output=True, text=True)
        html = out.read_text(encoding="utf-8") if out.exists() else ""
        return proc, html


class GoldenOutput(unittest.TestCase):
    CASES = [
        ("full.json", "full.golden.html", ()),
        ("full.json", "full-wordmark.golden.html", ("--wordmark",)),
        ("minimal.json", "minimal.golden.html", ()),
        ("no-hours.json", "no-hours.golden.html", ()),
    ]

    def test_existing_reports_unchanged(self):
        for src, golden, flags in self.CASES:
            with self.subTest(src=src, flags=flags):
                content = json.loads((FIXTURES / src).read_text(encoding="utf-8"))
                proc, html = render(content, *flags)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                expected = (FIXTURES / golden).read_bytes().replace(b"\r\n", b"\n")
                self.assertEqual(html.encode("utf-8"), expected)


class ManagedServicesTiles(unittest.TestCase):
    def test_under_budget(self):
        proc, html = render(dict(MANAGED, month_hours_used="12.5"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        for label in ("Monthly Budget", "Used This Month", "Remaining"):
            self.assertIn(label, html)
        self.assertIn(">30</div>", html)
        self.assertIn(">12.5</div>", html)
        self.assertIn(">17.5</div>", html)
        self.assertNotIn("#C0392B", html)
        for gone in ("Est. Hours", "Actual Hours", "of Estimate", "Est. Go Live"):
            self.assertNotIn(gone, html)

    def test_over_budget_turns_red(self):
        proc, html = render(dict(MANAGED, month_hours_used="34.25"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('color:#C0392B;line-height:1;">34.25</div>', html)
        self.assertIn(">0</div>", html)

    def test_exactly_on_budget_is_not_red(self):
        proc, html = render(dict(MANAGED, month_hours_used="30"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("#C0392B", html)

    def test_as_of_date_shown(self):
        proc, html = render(dict(MANAGED, month_hours_used="12.5"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Hours as of October 9, 2026", html)

    def test_missing_as_of_fails_build(self):
        content = dict(MANAGED, month_hours_used="12.5")
        del content["hours_as_of"]
        proc, _ = render(content)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("hours_as_of", proc.stderr)

    def test_unread_hours_show_dashes(self):
        content = dict(MANAGED)
        del content["hours_as_of"]
        proc, html = render(content)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Used This Month", html)
        self.assertIn("&mdash;", html)
        self.assertNotIn("Hours as of", html)

    def test_show_hours_false_still_drops_tiles(self):
        proc, html = render(dict(MANAGED, month_hours_used="12.5", show_hours=False))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Monthly Budget", html)


if __name__ == "__main__":
    unittest.main()
