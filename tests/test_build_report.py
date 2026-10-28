"""Renderer tests. Run from the repo root:

    python -m unittest discover -s initiatives/status-report-automation/cowork-skill-v3/tests -v

Golden files pin the rendered HTML for the fixture reports, so any change to the
template or renderer shows up as a reviewed diff. All data is made up.
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

    def test_unread_hours_without_error_flag_fails_build(self):
        content = dict(MANAGED)
        del content["hours_as_of"]
        proc, _ = render(content)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("hours_error", proc.stderr)

    def test_unread_hours_with_error_flag_show_notice(self):
        content = dict(MANAGED, hours_error=True)
        del content["hours_as_of"]
        proc, html = render(content)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Power BI connection encountered an error", html)
        self.assertNotIn("Monthly Budget", html)
        self.assertNotIn("Hours as of", html)

    def test_show_hours_false_still_drops_tiles(self):
        proc, html = render(dict(MANAGED, month_hours_used="12.5", show_hours=False))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Monthly Budget", html)


class ThirdPersonVoice(unittest.TestCase):
    BASE = {"client": "Acme", "report_date": "October 9, 2026", "show_hours": False,
            "signature": {"name": "Dana Reed", "firm": "Eide Bailly"}}

    def test_first_person_fails_build(self):
        proc, _ = render(dict(self.BASE, work_completed=["We completed a production order demonstration."]))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("third person", proc.stderr)
        self.assertIn("work_completed[1]", proc.stderr)

    def test_second_person_fails_build(self):
        proc, _ = render(dict(self.BASE, summary="Please review your open items."))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("summary", proc.stderr)

    def test_contraction_and_checkpoint_fail_build(self):
        proc, _ = render(dict(self.BASE, next_checkpoint="We'll meet Wednesday"))
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("next_checkpoint", proc.stderr)

    def test_third_person_passes(self):
        proc, html = render(dict(
            self.BASE,
            work_completed=["A production order demonstration was completed."],
            action_items=[{"text": "Jake will send the item master template", "owner": "Jake"}]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("A production order demonstration was completed.", html)

    def test_us_abbreviation_and_phase_numeral_pass(self):
        proc, _ = render(dict(self.BASE, summary="US sales tax setup finished for Phase I."))
        self.assertEqual(proc.returncode, 0, proc.stderr)


STANDARD = {"client": "Acme", "report_date": "October 9, 2026", "show_hours": True,
            "est_hours": "120", "act_hours": "47.5", "pct_estimate": "40", "completion_short": "Dec 1",
            "summary": "Testing continued.", "signature": {"name": "Dana Reed", "firm": "Eide Bailly"}}
HOURS_KEYS = ("est_hours", "act_hours", "pct_estimate", "completion_short")
LOG_URL = "https://example.com/log"


def section(html, start):
    """From a section's marker up to the next section marker that survived rendering."""
    at = html.index(start)
    nxt = html.find("<!-- =====", at + len(start))
    return html[at:nxt if nxt != -1 else len(html)]


class ActionItemLogLink(unittest.TestCase):
    def test_link_sits_under_action_items_not_summary(self):
        proc, html = render(dict(STANDARD, action_item_log_url=LOG_URL,
                                 action_items=[{"text": "Jake will send the template", "owner": "Jake"}]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("See the full action item log here", html)
        self.assertNotIn("See more detail here", html)
        items = section(html, "SECTION: Open Action Items")
        self.assertIn(LOG_URL, items)
        summary = section(html, "PROJECT SUMMARY")
        self.assertNotIn(LOG_URL, summary)

    def test_link_alone_keeps_the_action_items_section(self):
        proc, html = render(dict(STANDARD, action_item_log_url=LOG_URL))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Open Action Items", html)
        self.assertIn(LOG_URL, html)

    def test_no_link_no_items_drops_the_section(self):
        proc, html = render(dict(STANDARD))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Open Action Items", html)


class PowerBIFailsafe(unittest.TestCase):
    def test_all_hours_blank_fails_build(self):
        content = {k: v for k, v in STANDARD.items() if k not in HOURS_KEYS}
        proc, _ = render(content)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("hours_error", proc.stderr)
        self.assertIn("Never set show_hours to false", proc.stderr)

    def test_show_hours_absent_is_treated_as_on(self):
        content = {k: v for k, v in STANDARD.items() if k not in HOURS_KEYS + ("show_hours",)}
        proc, _ = render(content)
        self.assertNotEqual(proc.returncode, 0)

    def test_partial_hours_still_render_with_dashes(self):
        content = dict(STANDARD)
        del content["completion_short"]
        proc, html = render(content)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn(">120</div>", html)
        self.assertIn("&mdash;", html)

    def test_hours_error_replaces_tiles_with_notice(self):
        content = {k: v for k, v in STANDARD.items() if k not in HOURS_KEYS}
        proc, html = render(dict(content, hours_error=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Remove before sending: Power BI connection error", html)
        self.assertIn("run the report again in Cowork", html)
        for gone in ("Est. Hours", "Actual Hours", "of Estimate"):
            self.assertNotIn(gone, html)
        self.assertIn("Lead Consultant", html)
        self.assertIn("WARNING", proc.stdout)

    def test_show_hours_false_ignores_error_flag(self):
        content = {k: v for k, v in STANDARD.items() if k not in HOURS_KEYS}
        proc, html = render(dict(content, show_hours=False, hours_error=True))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertNotIn("Power BI connection", html)
        self.assertNotIn("WARNING", proc.stdout)


if __name__ == "__main__":
    unittest.main()
