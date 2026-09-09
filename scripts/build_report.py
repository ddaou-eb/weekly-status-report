#!/usr/bin/env python3
"""Render a Weekly Status Report email from a content JSON, using the bundled template.

v3 renderer. Same CLI and the same content.json schema as v2.

WHAT CHANGED IN v3, AND WHY
---------------------------
The draft's layout was collapsing in Outlook: the 600px white sheet lost its width
and background and ran the full width of the reading pane, the four stat tiles lost
their 25% columns, the bullet gutters collapsed, and the budget bar rendered as an
empty grey strip.

None of that was a design problem. The mail pipeline REWRITES the HTML on the way
into the draft, and it was silently deleting the markup that carried the layout:

  * Every presentational ATTRIBUTE is stripped: width=, height=, bgcolor=,
    cellpadding=, cellspacing=, border=, valign=, and align= on a <table>.
    (align= on a <td> is the one that survives - that is what centres the sheet.)

  * A handful of CSS properties are discarded: border-radius, max-width, overflow,
    mso-*, -webkit-*, -ms-*. Worse, when two of them appear together in one style
    attribute the sanitizer throws away the ENTIRE attribute. The sheet table
    carried "width:600px;max-width:600px;background-color:#FFFFFF;border-radius:14px;
    overflow:hidden;border:1px solid #E4E7EC;mso-table-lspace:0pt" and came back as
    style="" - which is precisely how a 600px branded sheet became an unstyled,
    full-width page.

So v3 keeps every layout value in inline CSS the sanitizer preserves, uses
border-collapse:collapse in place of the stripped cellspacing="0", and drops the
rounded corners and the budget bar. check_survivable() below enforces this on every
render so the regression cannot come back unnoticed.

Usage:
    python scripts/build_report.py <content.json> <output.html> [--wordmark]

Deterministic: the same content always yields identical HTML, so every report looks
the same. The template, logo, and all styling live in the skill - this script only
substitutes content into the placeholders and drops sections that have no content.

content.json schema (all keys optional unless noted):
{
  "client": "Acme Corporation",            # required
  "report_date": "July 24, 2026",          # required
  "logo_url": "https://...",                # optional https-hosted logo; omit -> text
                                            # wordmark. NEVER a data: URI (stripped by
                                            # the mail pipeline -> empty box)
  "est_hours": "120", "act_hours": "47.5", # from PM Reports (Power BI); omit -> shown as "-"
  "pct_estimate": "40%",                    # "% of Estimate" tile; a bare number is
                                            # accepted and normalized to "40%"
  "show_hours": true,                       # false -> drop the four stat tiles entirely
  "completion_short": "Sep 30",
  "completion_label": "Est. Go Live",       # 4th tile's caption; defaults to "Est. Go Live"
  "pm": "...", "lead_consultant": "...",
  "account_manager": "...",                 # 3rd People-row name ("sponsor" still accepted)
  "sponsor_label": "Account Manager",       # 3rd People-row caption
  "summary": "one or two sentences",
  "work_completed": ["...", "..."],         # empty/omitted -> section removed
  "next_steps": ["...", "..."],
  "decisions": ["..."],
  "action_items": [{"text": "...", "owner": "Name or TBD"}],   # max 5, <=20 words each
  "next_checkpoint": "Weekly status call, Wednesday Sept 2 at 11:00 AM ET",
                                            # renders as one bold line under the
                                            # action items; replaces the old
                                            # Next Steps section
  # "next_steps" is NO LONGER a section. It duplicated the action items one for
  # one, so an older content file's next_steps entries are folded into
  # action_items automatically (owner "TBD" when none was stated).
  "risks": [{"risk": "...", "mitigation": "..."}],   # or ["plain string", ...]
  "invoices": {                             # optional; omit to hide the section
     "rows": [{"invoice": "...", "date": "...", "days": "30", "amount": "$5,250.00"}],
     "total": "$10,500.00"
  },
  "signature": {"name": "...", "title": "...", "firm": "Eide Bailly",
                "email": "...", "phone": "..."}          # required
}
"""
import sys
import json
import pathlib
import re
from html import escape

HERE = pathlib.Path(__file__).resolve().parent
SKILL = HERE.parent
TEMPLATE = SKILL / "templates" / "weekly-status-template.html"

DASH = "&mdash;"
PLACEHOLDER_RE = re.compile(r"\[\[[A-Z_]+\]\]")

DEFAULT_COMPLETION_LABEL = "Est. Go Live"
DEFAULT_SPONSOR_LABEL = "Account Manager"
DEFAULT_FIRM = "Eide Bailly"

# Layout lives in the style attribute, never in an HTML attribute: width=/valign= are
# stripped in transit (see the module docstring), which is what collapsed the bullet
# gutter and let the marker wrap under its own text.
BULLET = ('<tr><td style="width:18px;vertical-align:top;padding:0;font-size:15px;line-height:1.55;'
          'color:#43A862;font-weight:700;">&bull;</td>'
          '<td style="padding:0 0 8px;font-size:15px;line-height:1.55;color:#0E172D;">{txt}</td></tr>')
CHECK = ('<tr><td style="width:22px;vertical-align:top;padding:0;font-size:16px;line-height:1.5;'
         'color:#496180;">&#9744;</td>'
         '<td style="padding:0 0 8px;font-size:15px;line-height:1.5;color:#0E172D;">'
         '{txt} <span style="color:#6C7884;">(Owner: {owner})</span></td></tr>')

# Each optional block spans from its start anchor up to (not including) the next anchor.
SECTION_ANCHORS = {
    "work_completed": ("<!-- ===== SECTION: Work Completed ===== -->", "<!-- ===== SECTION: Decisions ===== -->"),
    "decisions": ("<!-- ===== SECTION: Decisions ===== -->", "<!-- ===== SECTION: Open Action Items ===== -->"),
    "action_items": ("<!-- ===== SECTION: Open Action Items ===== -->", "<!-- ===== RISK / MITIGATION ===== -->"),
    "risks": ("<!-- ===== RISK / MITIGATION ===== -->", "[[INVOICES_BLOCK]]"),
    "_stat_tiles": ("<!-- ===== STAT TILES ===== -->", "<!-- People row -->"),
}

# CSS the mail pipeline discards. Any two of these in one style attribute and the
# sanitizer drops the whole attribute, taking the surviving declarations with it.
BANNED_CSS = ("border-radius", "max-width", "overflow", "mso-", "-webkit-", "-ms-")

# ----------------------------------------------------------------------------
# BREVITY BUDGET (v4)
#
# The layout was always scannable; the CONTENT was not. A real report shipped
# with 21 bullets and a 60-word lead bullet, which no executive reads. These
# caps are enforced as BUILD ERRORS, not warnings: a cap that can be ignored is
# not a cap. When a build fails here the fix is to cut and tighten the copy,
# never to raise the number. Detail that gets cut is not lost - it lives in the
# working email threads, which is where it belongs.
MAX_ITEMS = {
    "work_completed": 3,
    "decisions": 3,
    "action_items": 5,
    "risks": 2,
}
MAX_BULLET_WORDS = 20      # one line, readable at a glance
MAX_SUMMARY_WORDS = 40     # two short sentences
MAX_RISK_WORDS = 30        # risk and mitigation are counted separately

# ----------------------------------------------------------------------------
# PLAIN-LANGUAGE LINT (v4)
#
# The reader is a controller or an owner, not a consultant. Part numbers, lot
# and heat identifiers, internal system object names and to-the-penny figures
# are working-thread detail that makes a status report unreadable. These are
# WARNINGS, not errors: the occasional identifier is legitimate, and a false
# positive must never block a client draft. Read them, then tighten the copy.
JARGON_ALLOW = {
    "BC", "PO", "POS", "AR", "AP", "GL", "ERP", "ACH", "PDF", "ETA", "EB",
    "US", "ID", "IT", "HR", "KPI", "SOW", "UAT", "QA", "CEO", "CFO", "AI",
    "EDI", "API", "CRM", "TBD", "OK", "GB", "MB", "TB", "ET", "CT", "PT", "AM", "PM",
}
# a token mixing letters and digits: 7.625LHCE, B7P, GLH-CUCS-20260131
MIXED_TOKEN_RE = re.compile(r"\b(?=[^\s]*[A-Za-z])(?=[^\s]*\d)[A-Za-z0-9]+(?:[.\-][A-Za-z0-9]+)*\b")
# a shouty acronym that is not on the allow list: CUCS, GLH, MEM
ACRONYM_RE = re.compile(r"\b[A-Z]{2,6}\b")
# money carried to the penny at thousands scale: $212,433.09
PENNY_MONEY_RE = re.compile(r"\$\d{1,3}(?:,\d{3})+\.\d{2}")

# Attributes the mail pipeline strips. <img> is exempt: width/height/border on an
# image survive the trip and are the documented way to size a remote logo.
BANNED_ATTRS = ("width", "height", "bgcolor", "cellpadding", "cellspacing", "valign", "border")
EXEMPT_TAGS = ("img", "meta", "link", "br")
TAG_RE = re.compile(r"<(?!!)([a-zA-Z][a-zA-Z0-9]*)((?:\"[^\"]*\"|'[^']*'|[^>\"'])*)>")
ATTR_RE = re.compile(r"([a-zA-Z_:][-a-zA-Z0-9_:.]*)\s*=\s*(?:\"([^\"]*)\"|'([^']*)'|([^\s>]+))")


def txt(value):
    """Escape a caller-supplied string for use as HTML element text.

    Content originates in meeting transcripts and client email, so it routinely
    contains '<', '>' and '&'. Without this, an angle-bracketed address such as
    '<first.last@example.com>' is parsed as an unknown tag and silently deleted
    from the sent email.
    """
    return escape(str(value), quote=False)


def attr(value):
    """Escape a caller-supplied string for use inside an HTML attribute."""
    return escape(str(value), quote=True)


def check_survivable(html):
    """Fail the build on markup the mail pipeline would rewrite.

    This is the guard rail for the defect v3 exists to fix. The failure it catches
    is invisible at render time - build_report.py writes a perfect-looking file, and
    the layout only falls apart later, inside the recipient's mail client, where no
    one is watching. Catching it here keeps it a build error instead of a client
    seeing an unstyled email.
    """
    problems = []

    for m in TAG_RE.finditer(html):
        tag, attrs = m.group(1).lower(), m.group(2)
        names = {}
        for a in ATTR_RE.finditer(attrs):
            value = a.group(2) or a.group(3) or a.group(4) or ""
            names[a.group(1).lower()] = value

        for prop in BANNED_CSS:
            if prop in names.get("style", "").lower():
                problems.append(
                    "<{}> style carries the banned property {!r}: the mail pipeline "
                    "discards it, and two banned properties in one style attribute "
                    "make it discard the WHOLE attribute - that is what erased the "
                    "600px sheet width.".format(tag, prop))

        if tag in EXEMPT_TAGS:
            continue
        for a in BANNED_ATTRS:
            if a in names:
                problems.append(
                    "<{}> carries the {}= attribute: presentational attributes are "
                    "stripped in transit. Put it in the inline style instead "
                    "(width:600px / width:25% / vertical-align:top / "
                    "border-collapse:collapse).".format(tag, a))
        if tag == "table" and "align" in names:
            problems.append("<table align=...> is stripped in transit; centre the "
                            "sheet with align= on the wrapping <td> instead.")

    if problems:
        sys.exit("ERROR: this template would not survive the mail pipeline:\n  - "
                 + "\n  - ".join(sorted(set(problems))))


def logo_block(logo_url):
    """Build the hero-band brand mark.

    THE REAL IMAGE IS ONLY REACHABLE VIA logo_url (https). Everything else
    falls back to wordmark_block(). Both other routes were tested and BOTH
    are dead ends on this tenant - do not spend time re-deriving them:

      data:  the mail pipeline strips a data: src on the way into the draft,
             leaving a 118x53 empty box. Rejected outright below.
      cid:   survives the pipeline, but nothing can BIND it. The binding call
             is POST /me/messages/{id}/attachments with isInline + contentId.
             Raw Graph POST is refused ("use the dedicated tool"), and the
             dedicated tools (AddDraftAttachments, UploadAttachment) expose
             neither field. Passing the attachment inline to POST /me/messages
             is refused the same way. A cid: src therefore renders as an empty
             box exactly like data: did.

    An https <img> does survive the pipeline intact, width/height attributes and
    all - that was re-confirmed against a live draft when v3 was written. So: set
    logo_url on the profile to an https-hosted PNG and the report carries the real
    mark. Otherwise the wordmark, which is honest, renders everywhere, and needs
    no fetch and no attachment.
    """
    if not logo_url:
        return wordmark_block()
    url = str(logo_url).strip()
    if url.lower().startswith("data:"):
        sys.exit(
            "ERROR: logo_url is a data: URI. The mail pipeline strips data: image "
            "sources, so the logo would render as an empty box. Use an https URL, "
            "or omit logo_url for the wordmark."
        )
    if url.lower().startswith("cid:"):
        sys.exit(
            "ERROR: logo_url is a cid: reference. Nothing available can bind an "
            "inline attachment (isInline/contentId), so it would render as an "
            "empty box. Use an https URL, or omit logo_url for the wordmark."
        )
    if not url.lower().startswith("https://"):
        sys.exit("ERROR: logo_url must be an https:// URL (got {!r}).".format(url))
    return (
        '<img src="{src}" width="118" height="53" alt="Eide Bailly" '
        'style="display:block;border:0;width:118px;height:53px;'
        "font-family:'Segoe UI',Arial,sans-serif;font-size:21px;font-weight:600;"
        'color:#FFFFFF;">'.format(src=attr(url))
    )


def wordmark_block():
    """Live-text brand mark - the default, because no attachment route works.

    Two things this gets right that a naive text swap does not:

    1. It occupies the SAME 53px the logo image did, so the navy hero band
       keeps its height and the "Weekly Status" tag opposite stays optically
       balanced. A bare text node collapses the band by ~19px and makes the
       header look squat.
    2. It carries NO rule of its own. The template already draws a full-width
       #6EDC82 divider at the foot of the hero band; a second short rule up
       here reads as a stray underline rather than a brand element.

    Letter-spacing is tightened slightly and the weight raised to 700 so the
    type reads as a mark rather than as a stray line of body copy.
    """
    return (
        '<table role="presentation" style="border-collapse:collapse;"><tbody>'
        '<tr><td style="height:53px;vertical-align:middle;padding:0;'
        'font-family:\'Segoe UI\',\'Segoe UI Semibold\',Arial,sans-serif;'
        'font-size:26px;line-height:53px;font-weight:700;letter-spacing:-0.01em;'
        'color:#FFFFFF;white-space:nowrap;">'
        'Eide&nbsp;Bailly</td></tr>'
        '</tbody></table>'
    )


def bullets(items):
    return "".join(BULLET.format(txt=txt(x)) for x in items)


def checks(items):
    return "".join(
        CHECK.format(txt=txt(i["text"]), owner=txt(i.get("owner") or "TBD"))
        for i in items
    )


def risks_html(items):
    parts = []
    for r in items:
        if isinstance(r, str):
            parts.append(txt(r))
        else:
            s = "<strong>{}</strong>".format(txt(r["risk"]))
            if r.get("mitigation"):
                s += ' <span style="color:#4A555F;">Mitigation: {}</span>'.format(txt(r["mitigation"]))
            parts.append(s)
    return "<br><br>".join(parts)


def signature_html(sig):
    sig = sig or {}
    out = ['<div style="font-weight:700;color:#0E172D;">{}</div>'.format(txt(sig.get("name", "")))]
    if sig.get("title"):
        out.append('<div style="color:#4A555F;font-size:14px;">{}</div>'.format(txt(sig["title"])))
    # Firm line carries no legal suffix: a status email is body copy, not a
    # signatory document. "Eide Bailly Advisory LLC" belongs only on SOWs,
    # sign-offs and invoices; "Eide Bailly LLP" is audit & attest only.
    out.append('<div style="color:#4A555F;font-size:14px;">{}</div>'.format(txt(sig.get("firm") or DEFAULT_FIRM)))
    contact = []
    if sig.get("email"):
        contact.append('<a href="mailto:{href}" style="color:#43A862;text-decoration:none;">{shown}</a>'.format(
            href=attr(sig["email"]), shown=txt(sig["email"])))
    if sig.get("phone"):
        sep = ' <span style="color:#C4CDD6;">&middot;</span> ' if contact else ''
        contact.append(sep + '<span style="color:#4A555F;">{}</span>'.format(txt(sig["phone"])))
    if contact:
        out.append('<div style="font-size:14px;padding-top:2px;">{}</div>'.format("".join(contact)))
    return "\n        ".join(out)


def invoices_html(inv):
    if not inv or not inv.get("rows"):
        return ""
    rows = list(inv["rows"])
    body = []
    for idx, r in enumerate(rows):
        last = (idx == len(rows) - 1) and not inv.get("total")
        b = "" if last else "border-bottom:1px solid #EEF1F4;"
        body.append(
            '<tr>'
            '<td style="padding:10px 12px;font-size:14px;color:#0E172D;{b}">{invoice}</td>'
            '<td style="padding:10px 12px;font-size:14px;color:#4A555F;{b}">{date}</td>'
            '<td align="center" style="padding:10px 12px;font-size:14px;color:#4A555F;{b}">{days}</td>'
            '<td align="right" style="padding:10px 12px;font-size:14px;color:#0E172D;font-weight:700;{b}">{amount}</td>'
            '</tr>'.format(b=b, invoice=txt(r["invoice"]), date=txt(r["date"]),
                           days=txt(r["days"]), amount=txt(r["amount"])))
    if inv.get("total"):
        body.append(
            '<tr><td colspan="3" style="background-color:#F6F6F6;padding:10px 12px;font-size:13px;'
            'font-weight:700;color:#0E172D;border-top:1px solid #E4E7EC;">Total Due</td>'
            '<td align="right" style="background-color:#F6F6F6;padding:10px 12px;font-size:14px;'
            'font-weight:700;color:#0E172D;border-top:1px solid #E4E7EC;">{}</td></tr>'.format(txt(inv["total"])))
    return (
        '  <tr>\n  <td style="padding:26px 36px 0;">\n'
        '    <table role="presentation" style="border-collapse:collapse;"><tbody><tr><td '
        'style="padding:0;font-family:\'Segoe UI\',Arial,sans-serif;font-size:12px;font-weight:600;letter-spacing:0.1em;'
        'text-transform:uppercase;color:#0E172D;">Outstanding Invoices</td></tr>\n'
        '    <tr><td style="padding:7px 0 0;"><div style="width:40px;height:3px;background-color:#6EDC82;'
        'font-size:0;line-height:0;">&nbsp;</div></td></tr></tbody></table>\n'
        '    <p style="margin:12px 0 0;font-family:Calibri,\'Segoe UI\',Arial,sans-serif;font-size:13px;'
        'line-height:1.55;color:#C0392B;"><strong>Please note:</strong> all due '
        'payments must be current in order to complete the Go-Live phase of Eide Bailly projects.</p>\n'
        '    <p style="margin:10px 0 16px;font-family:Calibri,\'Segoe UI\',Arial,sans-serif;font-size:13px;'
        'line-height:1.55;color:#4A555F;">The table below lists open invoices for '
        'this project. Invoices 30 days past due accrue a 1.0% late fee. For a statement or copies, contact '
        '<a href="mailto:admintechconsulting@eidebailly.com" style="color:#43A862;text-decoration:underline;">'
        'admintechconsulting@eidebailly.com</a>. Pay via ACH/check or use Online Bill Pay at '
        '<a href="http://www.eidebailly.com/PayBill" style="color:#43A862;text-decoration:underline;">'
        'eidebailly.com/PayBill</a>.</p>\n'
        '    <table role="presentation" style="width:100%;border:1px solid #E4E7EC;border-collapse:collapse;'
        'font-family:Calibri,\'Segoe UI\',Arial,sans-serif;">\n'
        '      <tbody><tr>\n'
        '        <td style="background-color:#0E172D;padding:9px 12px;font-size:11px;font-weight:600;'
        'letter-spacing:0.04em;text-transform:uppercase;color:#FFFFFF;">Invoice</td>\n'
        '        <td style="background-color:#0E172D;padding:9px 12px;font-size:11px;font-weight:600;'
        'letter-spacing:0.04em;text-transform:uppercase;color:#FFFFFF;">Date</td>\n'
        '        <td align="center" style="background-color:#0E172D;padding:9px 12px;font-size:11px;'
        'font-weight:600;letter-spacing:0.04em;text-transform:uppercase;color:#FFFFFF;">Days Open</td>\n'
        '        <td align="right" style="background-color:#0E172D;padding:9px 12px;font-size:11px;'
        'font-weight:600;letter-spacing:0.04em;text-transform:uppercase;color:#FFFFFF;">Amount Due</td>\n'
        '      </tr>\n      ' + "\n      ".join(body) + '\n      </tbody>\n    </table>\n  </td>\n  </tr>')


def drop_between(html, start, end):
    """Remove html[start:end). Both anchors are template constants, so a miss means
    the template was edited incompatibly - fail loudly instead of silently leaving
    an empty section heading in a client-facing email."""
    i = html.find(start)
    j = html.find(end)
    if i == -1 or j == -1:
        missing = start if i == -1 else end
        sys.exit("ERROR: template anchor not found: {!r}. The template and this "
                 "renderer are out of sync.".format(missing))
    if j <= i:
        sys.exit("ERROR: template anchors out of order: {!r} does not precede {!r}.".format(start, end))
    return html[:i] + html[j:]


def normalize_pct(value):
    """The "% of Estimate" tile reads as a percentage, so "74" and "74%" must both
    render as "74%". Accept either form, always emit "NN%"."""
    s = str(value).strip()
    if not s:
        return ""
    if s.endswith("%"):
        return s
    if re.fullmatch(r"\d+(\.\d+)?", s):
        return s + "%"
    return s


def word_count(value):
    return len(str(value).split())


def fold_next_steps(content):
    """Merge a legacy "next_steps" list into "action_items".

    Next Steps and Open Action Items were two sections holding one idea. A real
    report listed "void the checks", "re-import them", "record the process
    videos" and "provide the per-unit costs" in BOTH - the duplication was
    structural, not an authoring slip, so the template now carries a single
    owned list and this folds any older content forward rather than breaking it.

    Accepts plain strings or {"text": ..., "owner": ...}. A bare string has no
    stated owner, so it becomes "TBD" - the same rule the skill applies to an
    action item whose owner was never named out loud.
    """
    steps = content.pop("next_steps", None)
    if not steps:
        return
    merged = list(content.get("action_items") or [])
    for s in steps:
        merged.append(s if isinstance(s, dict) else {"text": s, "owner": "TBD"})
    content["action_items"] = merged
    print('NOTE: "next_steps" was folded into "action_items" - the template now '
          "carries one owned list. Put next steps there directly.")


def enforce_brevity(content):
    """Fail the build when the report is too long or too dense to be read.

    Deliberately an error. The whole failure mode this guards against is a
    report that is individually defensible line by line and unreadable as a
    whole, which no warning ever stops.
    """
    problems = []

    for key, cap in MAX_ITEMS.items():
        items = content.get(key) or []
        if len(items) > cap:
            problems.append(
                "{} has {} entries; the cap is {}. Cut or merge - do not raise "
                "the cap.".format(key, len(items), cap))

    def too_long(label, value, cap):
        n = word_count(value)
        if n > cap:
            problems.append(
                '{} runs {} words; the cap is {}. Lead with the outcome and '
                'drop the mechanism: "{}"'.format(
                    label, n, cap, " ".join(str(value).split()[:8]) + "..."))

    if content.get("summary"):
        too_long("summary", content["summary"], MAX_SUMMARY_WORDS)

    for key in ("work_completed", "decisions"):
        for i, b in enumerate(content.get(key) or [], 1):
            too_long("{}[{}]".format(key, i), b, MAX_BULLET_WORDS)

    for i, a in enumerate(content.get("action_items") or [], 1):
        too_long("action_items[{}]".format(i), a.get("text", ""), MAX_BULLET_WORDS)

    for i, r in enumerate(content.get("risks") or [], 1):
        if isinstance(r, str):
            too_long("risks[{}]".format(i), r, MAX_RISK_WORDS)
        else:
            too_long("risks[{}].risk".format(i), r.get("risk", ""), MAX_RISK_WORDS)
            if r.get("mitigation"):
                too_long("risks[{}].mitigation".format(i), r["mitigation"], MAX_RISK_WORDS)

    if content.get("next_checkpoint"):
        too_long("next_checkpoint", content["next_checkpoint"], MAX_BULLET_WORDS)

    if problems:
        sys.exit("ERROR: this report is too long to be read:\n  - "
                 + "\n  - ".join(problems))


def plain_language_warnings(content):
    """Warn on copy the client will not parse. Never blocks the build.

    Scans body copy only. The invoice table is exempt by design: an invoice
    number IS an identifier and a payable amount SHOULD carry its cents.
    """
    notes = []

    def scan(label, value):
        s = str(value)
        for token in sorted(set(MIXED_TOKEN_RE.findall(s))):
            if token.upper() in JARGON_ALLOW or re.fullmatch(r"\d+[a-z]{2}", token):
                continue
            notes.append('{}: "{}" reads as a part/lot identifier. Describe it '
                         "in words instead.".format(label, token))
        for token in sorted(set(ACRONYM_RE.findall(s))):
            if token in JARGON_ALLOW:
                continue
            notes.append('{}: "{}" is an internal name the client may not know. '
                         "Spell it out or drop it.".format(label, token))
        for amount in sorted(set(PENNY_MONEY_RE.findall(s))):
            notes.append('{}: "{}" is precise to the penny. Round it '
                         "(about $212K reads better than $212,433.09).".format(label, amount))

    if content.get("summary"):
        scan("summary", content["summary"])
    for key in ("work_completed", "decisions"):
        for i, b in enumerate(content.get(key) or [], 1):
            scan("{}[{}]".format(key, i), b)
    for i, a in enumerate(content.get("action_items") or [], 1):
        scan("action_items[{}]".format(i), a.get("text", ""))
    for i, r in enumerate(content.get("risks") or [], 1):
        scan("risks[{}]".format(i), r if isinstance(r, str) else
             " ".join(filter(None, [r.get("risk"), r.get("mitigation")])))

    for n in notes:
        print("STYLE: " + n)


def next_checkpoint_html(value):
    """The one line that survived the Next Steps section."""
    if not value:
        return ""
    return ('\n    <p style="margin:14px 0 0;font-family:Calibri,\'Segoe UI\',Arial,sans-serif;'
            'font-size:15px;line-height:1.5;color:#0E172D;">'
            '<strong>Next checkpoint:</strong> {}</p>'.format(txt(value)))


def main():
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 2 or flags - {"--wordmark"}:
        sys.exit("Usage: python scripts/build_report.py <content.json> <output.html> [--wordmark]")
    content = json.loads(pathlib.Path(args[0]).read_text(encoding="utf-8"))

    fold_next_steps(content)
    enforce_brevity(content)
    plain_language_warnings(content)

    html = TEMPLATE.read_text(encoding="utf-8")
    html = html.split("</html>", 1)[0] + "</html>"  # drop trailing maintainer note

    # --wordmark forces the text mark even when logo_url is set (useful to
    # preview what a recipient blocking remote images will see).
    logo = wordmark_block() if "--wordmark" in flags else logo_block(content.get("logo_url"))
    pct = normalize_pct(content.get("pct_estimate", ""))

    # remove optional sections with no content
    for key in ["work_completed", "decisions", "action_items", "risks"]:
        # the checkpoint line lives inside the action-items block, so that block
        # survives an empty list whenever a checkpoint still needs somewhere to sit
        if key == "action_items" and content.get("next_checkpoint"):
            continue
        if not content.get(key):
            html = drop_between(html, *SECTION_ANCHORS[key])
    if content.get("show_hours") is False:
        html = drop_between(html, *SECTION_ANCHORS["_stat_tiles"])

    sig = content.get("signature") or {}

    # Plain-text values are escaped, then fall back to the dash glyph when blank.
    # An empty string counts as blank: an absent value and an explicit "" should
    # both show the placeholder, not an empty tile.
    repl = {
        "[[LOGO_BLOCK]]": logo,
        "[[CLIENT]]": txt(content.get("client", "")),
        "[[REPORT_DATE]]": txt(content.get("report_date", "")),
        "[[EST_HOURS]]": txt(content.get("est_hours") or "") or DASH,
        "[[ACT_HOURS]]": txt(content.get("act_hours") or "") or DASH,
        "[[PCT_ESTIMATE]]": txt(pct) or DASH,
        "[[COMPLETION_SHORT]]": txt(content.get("completion_short") or "") or DASH,
        "[[COMPLETION_LABEL]]": txt(content.get("completion_label") or DEFAULT_COMPLETION_LABEL),
        "[[PM]]": txt(content.get("pm", "")),
        "[[LEAD_CONSULTANT]]": txt(content.get("lead_consultant", "")),
        # "sponsor" is the legacy key; profiles written before the People row was
        # relabelled still use it, so both are accepted.
        "[[SPONSOR]]": txt(content.get("account_manager") or content.get("sponsor") or ""),
        "[[SPONSOR_LABEL]]": txt(content.get("sponsor_label") or DEFAULT_SPONSOR_LABEL),
        "[[SUMMARY]]": txt(content.get("summary", "")),
        "[[FOOTER_FIRM]]": txt(sig.get("firm") or DEFAULT_FIRM),
        # these are already-assembled HTML fragments, not raw text
        "[[WORK_COMPLETED]]": bullets(content.get("work_completed", [])),
        "[[DECISIONS]]": bullets(content.get("decisions", [])),
        "[[ACTION_ITEMS]]": checks(content.get("action_items", [])),
        "[[NEXT_CHECKPOINT]]": next_checkpoint_html(content.get("next_checkpoint")),
        "[[RISKS]]": risks_html(content.get("risks", [])),
        "[[INVOICES_BLOCK]]": invoices_html(content.get("invoices")),
        "[[SIGNATURE]]": signature_html(sig),
    }
    for key, value in repl.items():
        html = html.replace(key, value)

    # Catch ANY remaining [[TOKEN]], including one added to the template but never
    # wired into repl. The previous check only re-tested repl's own keys, so it
    # could never fail, and a new template placeholder shipped to the client as
    # literal text.
    left = sorted(set(PLACEHOLDER_RE.findall(html)))
    if left:
        sys.exit("ERROR: unfilled placeholders remain: " + ", ".join(left))

    check_survivable(html)

    pathlib.Path(args[1]).write_text(html, encoding="utf-8")
    print("wrote", args[1], "(" + str(len(html)) + " bytes)")
    if "<img" not in html:
        print("NOTE: rendered with the text wordmark. Set logo_url (https) on the "
              "profile to carry the real logo image.")


if __name__ == "__main__":
    main()
