---
name: weekly-status-report
description: 'Generates client-facing WEEKLY STATUS REPORTS as branded HTML email drafts. A one-time setup per client saves a profile (point of contact, internal CC, Power BI project). One weekly scheduled run then covers every configured client at once: it scans that week''s client meetings, reads the meeting recaps, pulls hours from PM Reports in Power BI, and prepares a draft email for the user to review and send. Use when the user says "weekly status report for [client]", "set up a weekly status report", "generate the weekly status for [client]", "send [client] their weekly update", "run the weekly client status", or "run the weekly status for all clients". Do NOT use for per-meeting recaps (use client-meeting-recap), internal-only meeting summaries (use meeting-intel), scheduling meetings (use schedule-meeting), or a personal daily overview (use daily-briefing).'
cowork:
  category: communication
  icon: MailTemplate
---

# Weekly Status Report

Produce a **client-facing weekly status report** for each configured client and prepare it as a clean, branded HTML email draft, grounded entirely in that week's meetings and correspondence, never invented.

This skill is **self-contained and portable**. It does not depend on any other skill and stores each user's settings in its own folder, so every teammate can set it up for their own clients.

**Everything is a draft.** This skill never sends email. It prepares drafts in the user's Outlook for them to read and send.

## When NOT to Use
- **A single meeting recap** → use `client-meeting-recap`.
- **Internal-only meetings** (all attendees share the firm domain) → use `meeting-intel`.
- **Scheduling / rescheduling** a meeting → use `schedule-meeting`.
- **A personal daily overview** of the user's own day → use `daily-briefing`.

---

## Two ways this runs

| Mode | Trigger | Scope |
|---|---|---|
| **Weekly batch** (the normal path) | One recurring scheduled task | Every client with a saved profile, in a single run |
| **On demand** | The user names a client | That one client |

There is **one** scheduled task, not one per client. The calendar is pulled once and filtered per client, so adding a client costs a filter, not a run.

---

## First-Run Setup (per client, one time)

Run setup when the user invokes the skill for a client with **no saved profile**, or when they say "set up", "reconfigure", or "change settings" for a client.

**Confirm every field. Never infer one silently.** Look things up first, then put **every field that will appear in the report** in front of the user to confirm or correct — the people on it as much as the recipients. This report goes out with the firm's name on it, so one extra question at setup is cheaper than a wrong name in front of a client. If a lookup finds no candidate for a field, still ask for it; do not leave it to be filled in later by inference, and do not draft while any field is unsure.

1. **Get the client name.** Take it from the request ("weekly status for **Acme**"). If absent, ask (`AskUserQuestion` with `options: []` for a free-text answer).
2. **Look up before asking.** Search recent calendar and email for that client to infer the **email domain**, the likely **point of contact**, and who from the firm is on the engagement (`SearchM365`, `ListMessages`, `SearchPeople`, `GetUserDetails`, `GetMyDetails`). Resolve, never guess or construct an address.
3. **Ask in one `AskUserQuestion` card** — one question per field below, recommended default first, and every option a real candidate you actually found. Where a lookup turned up no candidate, pass `options: []` so the user can type the answer. Never author an "Other" option; an empty options array is the free-text form.
   - **Point of contact** — the client recipients, all on the To: line. `multiSelect`; several client contacts is normal.
   - **Internal CC team** — who to copy. `multiSelect`.
   - **NetSuite project record address** — the project record's email dropbox, which files the sent report to that project record in NetSuite. It looks like `messages.1177491.57162282.2be6f36523@1177491.email.netsuite.com`. Pass `options: []` and have the user paste it from the NetSuite project record; never construct, correct, or infer one, and never resolve it with people tools. An empty answer means this project has no record address — save `""` so no later run asks again.
   - **Engagement lead / Lead Consultant** — the name that appears on the report's People row.
   - **Project Manager** — the PM on the People row.
   - **Account Manager** — the third name on the People row. Offer a single "this engagement has no standing account manager" choice so the user can decline it explicitly rather than it being quietly blank.
   - **Hours tiles** — *Show Est/Actual/% from PM Reports* (default) · *Leave hours off this client's report*.
   - **Outstanding Invoices** — *Leave it off* (default) · *Include open AR*.
   - **Scan client email too?** — *No, meetings only* (default) · *Yes, also scan email from this client*.

   Resolve every chosen person to a real address (recipients) or full display name (People row) before saving.
4. **Pin the Power BI project.** Locate the firm's **PM Reports** model once, here at setup, with `SearchM365(sources=["powerbi"])`. Save the model id as `powerbi_report` and the row/project identifier this client's hours live under as `powerbi_project`. **Do not defer this to the weekly run.** If the project genuinely cannot be found, save `show_hours: false` and tell the user the hours tiles will be blank until it is set.
5. **Save the profile** to `clients/<client-slug>.md` (format below).
6. **Make sure the weekly task exists.** Call `GetScheduledPrompts`. If the batch task is already there, say so and change nothing. If not, create it (see *Scheduling*). One task total, for all clients.
7. **Confirm in plain language**: *"All set. Acme joins the Friday 9 AM run, and I'll have a draft waiting for your review, copying [CC team] and BCC'ing the NetSuite project record. You can also ask for it anytime with 'weekly status for Acme'."* Leave the NetSuite clause out when no record address was saved.

After setup, a report needs only the client name, or nothing at all on the batch run.

---

## Client Profiles

One file per client in this skill's `clients/` subfolder, so settings persist between runs. The folder is the skill's settings store and **ships empty**: profiles are each user's own and are not shared when the skill is. A teammate who installs this skill gets a blank `clients/` folder and runs their own setup.

```markdown
---
client: Acme Corporation
domain: acme.com             # the client's own email domain
additional_domains:          # optional; outside advisors or a second company domain.
  - acmeadvisors.com         # a meeting or email qualifies on ANY of the domains listed here
point_of_contact:            # one or several client recipients, all on the To: line
  - Jane Smith <jsmith@acme.com>
internal_cc:
  - Chris Lee <clee@eidebailly.com>
  - Pat Ray <pray@eidebailly.com>
# NetSuite project record dropbox - BCC'd on every draft so the sent report files
# itself to the project record. "" only when the user said this project has none:
netsuite_record_email: messages.1177491.57162282.2be6f36523@1177491.email.netsuite.com
# People row - all three are confirmed at setup, never inferred at run time:
lead_consultant: Dana Reed   # the engagement lead named on the report
project_manager: Chris Lee   # the PM named on the report
account_manager: Pat Ray     # third name on the People row; "" only when the user said there is none
powerbi_report: rpt_1        # PM Reports model id, pinned at setup
powerbi_project: ACME-2026   # the project/row this client's hours sit under
scan_email: false            # also scan email from this client's qualifying domains? meetings-only by default
# Section/field preferences:
include_invoices: false      # include the Outstanding Invoices section?
show_hours: true             # show the four stat tiles?
logo_url: ""                 # optional https-hosted logo; "" = built-in wordmark. NEVER a data: URI
---
Optional notes about this engagement.
```

**Qualifying domains.** `domain` plus every entry in the optional `additional_domains` list are this client's **qualifying domains**, and they are what meetings and email are filtered on. Add `additional_domains` when people outside the client's own domain genuinely belong to the engagement, such as the client's outside advisors or accountants, or a second company domain. Only the user adds it: setup does not ask, and you never infer one. A profile with no `additional_domains` key qualifies on `domain` alone, which is the normal case.

If a setting needs to change, the user says so and you edit the profile. Do not try to infer preferences from previously sent mail.

A profile saved before the People row was confirmed at setup may be missing `lead_consultant`, `project_manager`, or `account_manager`. When a run finds one missing, **ask for it once and write the answer back** — never render the report with an invented name or a silent blank where a person belongs. Older profiles spell the third name `sponsor`; the renderer still accepts that key, so rename it on the next edit rather than re-asking the user for a name they already gave.

The same applies to `netsuite_record_email` on a profile saved before that field existed: ask once, then write the answer back — including `""` when the user says there is none, so the question is never asked twice.

---

## Generating a Report

On the **batch run**, do step 1 once, then repeat steps 2 through 7 per client. On an **on-demand run**, do all of it for the one named client.

1. **Pull the week once.** Determine the window: the most recent **Monday through Friday** in the user's local time zone, or the current Mon–Fri for a scheduled Friday run. Call `ListCalendarView` **one time** for that window (`select` subject, start, end, organizer, attendees, isOnlineMeeting, onlineMeeting, isCancelled, showAs). Every client is filtered out of this one result.

2. **Load the client's profile.** If none exists, run *First-Run Setup* instead.

3. **Filter to that client's meetings.** A meeting qualifies when **all** of these hold:
   - `isOnlineMeeting` is true, **and**
   - **at least one attendee's email domain is one of this client's qualifying domains** (`domain`, plus anything in `additional_domains`), **and**
   - it is not cancelled.

   An attendee on a qualifying domain is **required**. An internal call titled "Acme planning" with no attendee on any of those domains does **not** qualify, because that is the most likely way internal staffing or fee talk leaks into a client-facing email. Use the subject only to label meetings, never to qualify one.

   Cap at the **four** most recent qualifying meetings, and tell the user if you dropped any.

4. **Read the recap first, the transcript only if there is none.** For each qualifying meeting, in this order:
   - **Meeting recap or AI notes**, if the meeting has them. The default source, and enough on its own: it already carries the decisions, action items, and topics.
   - **Full transcript only when no recap exists**: `ListMeetingTranscripts(join_url=…)` then `GetMeetingTranscript(…)`. For a recurring series, pick the `transcript_id` whose `createdDateTime` is closest to that meeting's start.

   Never pull both for the same meeting.

5. **Client email, only if the profile opts in.** When `scan_email: true`, call `ListMessages` once, filtered to the client's qualifying domains for the week. Do not also call `SearchM365` for the same thing. When `scan_email: false`, skip this entirely.

6. **Pull project hours.** Read this client's **Estimated Hours**, **Actual / Billable Hours**, **% of Estimate**, and estimated completion date directly from the `powerbi_report` and `powerbi_project` saved on the profile. This is a direct read, not a search: the discovery happened at setup.

   If the profile has no `powerbi_report` yet (an older profile, or setup could not find it), do the discovery **once** with `SearchM365(sources=["powerbi"])`, then **write both ids back to the profile** so no later run repeats the search. If the read fails or the project is missing, **leave those fields blank** rather than guessing. Never fabricate hours.

7. **Extract, build, and draft.**
   - Extract progress, decisions, and action items, applying the **Client-Safety Rules** and the **Brevity and Plain Language** caps below. Consolidate topics that repeat across meetings. Next steps belong in the action items, each with an owner; the single forward-looking date goes in `next_checkpoint`.
   - Fill the People row from the profile's `lead_consultant`, `project_manager`, and `account_manager`. If any of the three is missing, **ask once** (`AskUserQuestion`) and write the answer back to the profile before drafting. Never invent a name here.
   - Write the facts to a content JSON (schema in *Branding & Formatting*) and run `python scripts/build_report.py <content.json> working/<client-slug>.html`. Do **not** hand-write or restyle the HTML.
   - `CreateDraftMessage` to the point of contact, CC the internal team, and **BCC the profile's `netsuite_record_email`** so the report files itself to the NetSuite project record when the user sends it. `CreateDraftMessage` supports `bcc`, so use BCC and the client never sees the address; fall back to the CC line only if a BCC cannot be set. Skip it entirely when the profile has none. `body_file_path` points at the rendered file. **Draft only. Never send.**
   - Subject line: **`Weekly Status Update | [Client] | [Report date]`**.

8. **No-meeting case.** If no meetings qualify for a client that week, **skip that client silently**. Do not draft, and do not draft an empty report. On the batch run, carry on to the next client.

9. **Close the batch** with one short message naming which clients have drafts waiting, which were skipped for having no meetings, and any client whose hours could not be read.

---

## Client-Safety Rules

The output is client-facing and must be safe to send directly to a client. Always:
- **Exclude** internal opinions, resourcing and staffing, internal fee or scope disputes, and any speculation. (An **Outstanding Invoices** summary of what the client already owes *is* client-facing and may be included when the profile opts in.)
- **Never invent information.** If something is unclear, omit it.
- If an action item's owner is not stated, write **`Owner: TBD`**.
- If a due date is not stated, **omit** it. Do not guess.
- **Consolidate** repeating topics across meetings.
- Prefer **fewer, clearer** items over exhaustive lists.

---

## Brevity and Plain Language

The reader is a controller or an owner, not a consultant, and is reading between meetings. A report that is defensible line by line and unreadable as a whole is a failed report. `build_report.py` **fails the build** rather than shipping one:

| Limit | Cap |
|---|---|
| Work Completed | 3 items |
| Decisions | 3 items |
| Open Action Items | 5 items |
| Risks | 2 items |
| Any bullet, action item, or the checkpoint line | **20 words** |
| Project Summary | 40 words (two short sentences) |
| Risk and mitigation, counted separately | 30 words each |

When a build fails on these, **cut and tighten the copy — never raise a cap.** Write to the cap from the start rather than drafting long and letting the renderer reject it. The detail you drop is not lost: it lives in the working email threads, which is where a client goes looking for it.

**Lead every bullet with the outcome, not the mechanism.** Write *"Check migration fixed — 58 checks move to the correct account this week"*, not *"Diagnosed the migrated check import: 58 checks were posted against the main account rather than the sweep account, and because Business Central will not reverse an entry tied to a check ledger entry…"*. Same fact, a quarter of the words, and the reader has the point by the fourth one.

**Write so a non-technical reader gets it first time.** No part, lot, or heat identifiers; no internal system or entity names; no figures carried to the penny — round them (*about $212K*, not *$212,433.09*). The renderer prints `STYLE:` warnings when it spots these. Those are warnings, not errors, because the odd identifier is genuinely necessary and a false positive must never block a client draft — read them and tighten the copy.
- **Domain scoping.** Only include content tied to this client's qualifying domains. Never let one client's material reach another's report, which matters more on a batch run where several clients are in flight at once.
- Ground every line in a recap, transcript, note, or email. If the source is ambiguous, summarize conservatively or leave it out.

---

## Output Format (v4 "Dashboard" layout)

A navy hero header, a row of KPI stat tiles, and airy overline sections. In order:

**Hero header (navy)** — logo plus "Weekly Status" tag; the eyebrow "Project Status Update"; the **[Client Name]** reversed out in white; and the report date.

**Stat tiles** (four) — **Est. Hours**, **Actual Hours**, **% of Estimate** (navy tile, green number), **Est. Go Live** (short form, e.g. "Aug 3"). The first three come from PM Reports; a tile shows a dash when the data is unavailable. There is no budget bar: a percentage-width fill bar cannot survive the mail pipeline (see *What the mail pipeline does to this HTML*), and the **% of Estimate** tile already carries the number.

**People row** — Project Manager, Lead Consultant, Account Manager, each taken from the profile where it was confirmed at setup.

**Project Summary** — one or two sentences on the week's focus.

Then these overline sections, skipping any with nothing explicit to report:
- **Work Completed** — up to **3** accomplishments (green bullets).
- **Decisions** — up to **3**; explicit decisions only.
- **Open Action Items** — up to **5**, `☐ [item] (Owner: [Name or TBD])`, then one bold **Next checkpoint:** line drawn from `next_checkpoint`.

  **This is also where next steps go.** There is no separate Next Steps section. It duplicated this list one for one — the same four commitments appeared in both on a real report — so the two were merged into a single owned list. A `next_steps` array in an older content file is folded in here automatically, with owner `TBD` where none was stated.

**Risk / Mitigation** — a highlighted card; 0 to 2 explicitly stated risks, each with a mitigation if known.

**Outstanding Invoices** (only when the profile opts in) — open AR for the project: *Invoice, Date, Days Open, Amount Due* plus a **Total Due** row, with the standard late-fee and Online Bill Pay note. Populate from billing or AR data. Never invent invoice figures.

Close with **Regards,** and the sender's signature block; the firm line is plain **Eide Bailly**, with no legal suffix (see *Firm name* under Branding & Formatting).

---

## Branding & Formatting (deterministic renderer)

The look is fixed and produced the **same way every time** by the bundled renderer. Never hand-write or restyle the email HTML.

**How to render:** write the facts to a content JSON, then run `python scripts/build_report.py <content.json> working/<client-slug>.html`. The script loads `templates/weekly-status-template.html`, places the logo, formats bullets, checkboxes and invoices, escapes the text, drops empty sections, and exits with an error if any placeholder is left unfilled. Pass the file to `CreateDraftMessage` as `body_file_path`.

Add `--wordmark` to force the text mark even when `logo_url` is set — it previews what a recipient blocking remote images will see.

**content.json schema** (all keys optional except `client`, `report_date`, `signature`):
```json
{
  "client": "Acme Corporation", "report_date": "July 24, 2026",
  "logo_url": "",
  "est_hours": "120", "act_hours": "47.5", "pct_estimate": "40%",
  "completion_short": "Aug 3", "completion_label": "Est. Go Live",
  "show_hours": true,
  "pm": "…", "lead_consultant": "…", "account_manager": "…", "sponsor_label": "Account Manager",
  "summary": "one or two sentences",
  "work_completed": ["…"], "decisions": ["…"],
  "action_items": [{"text": "…", "owner": "Name or TBD"}],
  "next_checkpoint": "Weekly status call, Wednesday September 2 at 11:00 AM ET",
  "risks": [{"risk": "…", "mitigation": "…"}],
  "invoices": {"rows": [{"invoice": "…", "date": "…", "days": "30", "amount": "$5,250.00"}], "total": "$10,500.00"},
  "signature": {"name": "…", "title": "…", "firm": "Eide Bailly", "email": "…", "phone": "…"}
}
```
- `pct_estimate` takes either `"40%"` or `"40"`; the renderer normalizes it to `"40%"`.
- `completion_label` and `sponsor_label` are the two captions that change by engagement type. They default to **Est. Go Live** and **Account Manager**; set them only when a project genuinely uses different words (e.g. `"Est. Completion"`, `"Project Sponsor"`).
- `account_manager` is the third People-row name. The legacy key `sponsor` is still read, so profiles written before the relabel keep working.
- Omit any hours value you could not read and the tile shows a dash. Omit or empty any content list to drop that whole section. Omit `invoices` to hide that section.
- `next_checkpoint` renders as one bold line under the action items. Omit it and the line disappears; the action-items block still renders for the checkpoint alone if there are no open items.
- `next_steps` is retired. It is still accepted and folded into `action_items` so older content files keep working, but write next steps straight into `action_items` with an owner.
- Never fabricate figures. Leave a value out rather than guessing.
- `logo_url` is optional and must be `https://`. Omit it and the renderer draws the text wordmark; `data:` and `cid:` are both rejected outright (see *The brand mark* — neither can render).
- `signature.firm` is plain **`"Eide Bailly"`** — never a legal suffix. See *Firm name* below.

**Firm name — no legal suffix on this report.** Under the firm's alternative practice structure, a weekly status email is body copy, not a signatory document, so it never names a legal entity. `signature.firm` is plain **"Eide Bailly"** and the footer band reads *Eide Bailly · Technology Consulting*. The formal entity for advisory / Technology Consulting work, **Eide Bailly Advisory LLC**, belongs only on documents with signatory lines — SOWs, sign-offs, engagement letters, invoices. **Eide Bailly LLP** is the CPA / audit & attest entity and must not appear on this report, including on runs with the **Outstanding Invoices** section on: that section summarizes invoices, it is not the invoice document. Never add a suffix a profile did not supply, and never reintroduce "Eide Bailly LLP" into the template, the renderer, or a profile.

**Design reference (baked into the template, do not restyle):** 600px table-based, Navy `#0E172D` hero and footer, green accents `#6EDC82` and `#43A862`, Stone White `#F6F6F6` tiles and cards, amber `#E6A23C` risk accent, Segoe UI headings and Calibri body, **square corners throughout**. To change the look for **all** clients, edit the template and the renderer, never the per-run output.

---

## What the mail pipeline does to this HTML

**Read this before touching the template.** The draft pipeline rewrites the HTML on the way into Outlook. It once silently destroyed the layout — the 600px white sheet lost its width and background and ran the full width of the reading pane, the four stat tiles lost their 25% columns, the bullet gutters collapsed, and the budget bar became an empty grey strip. Nothing was wrong with the design; the markup carrying it was being deleted in transit.

Two rules. Break either and the email looks fine in the rendered file and wrong in the recipient's inbox:

1. **Never carry layout in an HTML attribute.** `width=`, `height=`, `bgcolor=`, `cellpadding=`, `cellspacing=`, `border=`, `valign=`, and `align=` on a `<table>` are all stripped. Put every one of them in the inline `style` instead — `width:600px`, `width:25%`, `width:18px`, `background-color:`, `vertical-align:top`. Use `border-collapse:collapse` in place of the stripped `cellspacing="0"`.
   - Two exceptions that do survive: **`align=` on a `<td>`** (that is what centres the sheet), and **`width`/`height`/`border` on an `<img>`**.
2. **Never use `border-radius`, `max-width`, `overflow`, `mso-*`, or `-webkit-`/`-ms-` properties.** Each is discarded on its own, and **two of them in the same `style` attribute make the sanitizer throw away the entire attribute**, taking every valid declaration with it. That is the exact mechanism that erased the sheet's width and background: `width:600px;max-width:600px;background-color:#FFFFFF;border-radius:14px;overflow:hidden;border:1px solid #E4E7EC;mso-table-lspace:0pt` arrived as `style=""`. Square corners are the design, not a compromise.

`build_report.py` enforces both rules on every render (`check_survivable`) and fails the build rather than shipping a report that will fall apart in transit. If it stops you, fix the markup — do not weaken the check.

**Verifying a template change end to end.** The rendered file is not evidence; only the stored draft is. Create a throwaway draft with `CreateDraftMessage`, read the body back with `QueryGraph` on `/me/messages/{id}?$select=body`, and confirm no `style=""` appears and the sheet still says `width:600px`. Then delete the test draft.

**The brand mark.** The hero band shows the real Eide Bailly logo **only when the profile sets `logo_url`** to an https-hosted copy. With no `logo_url` it draws a live-text wordmark. That is not a stylistic preference — it is the only route that works, and the two alternatives were tested to destruction on this tenant:

- **`data:` — stripped.** `<img src="data:image/png;base64,…">` arrives in the draft with no `src` at all and shows a 118×53 empty box. The renderer rejects a `data:` `logo_url` outright.
- **`cid:` — survives, but cannot be bound.** A `cid:` src passes through the pipeline intact, so it looks promising. Binding it needs `POST /me/messages/{id}/attachments` with `isInline: true` and a `contentId`. **Raw Graph POST is refused** — the platform forces the dedicated tool for any path that has one — and the dedicated tools (`AddDraftAttachments`, `UploadAttachment`) expose neither field. Passing the attachment inline to `POST /me/messages` is refused the same way. An unbound `cid:` renders as an empty box exactly like `data:` did. The renderer rejects a `cid:` `logo_url` too, so nobody re-derives this.
- **`https:` — works.** Host the PNG at a public https URL and set `logo_url`. An `<img>` with an https `src` passes through the pipeline intact, `width`/`height` attributes and all — re-confirmed against a live draft. The `alt` text is styled white/semibold so a recipient who blocks remote images sees clean type rather than a broken box.

An email hand-composed in Outlook can carry the mark as a `cid:` inline attachment, because Outlook binds the content-id itself at compose time. That is not a route this skill can take: the binding call is unavailable here (above), so `https` or the wordmark are the only two options for a generated draft.

**The wordmark is a real fallback, not a placeholder — keep it well-made.** It is sized to the logo's **53px** so the navy hero band keeps its height (a bare text node collapses it ~19px and makes the header squat, unbalancing the "Weekly Status" tag opposite). It carries **no rule of its own**, because the template already draws the full-width `#6EDC82` divider at the foot of the hero — a second short rule there reads as a stray underline. Run with `--wordmark` to force it even when `logo_url` is set, which previews what an images-blocked recipient sees.

---

## Voice

Write as the **sender** (resolve their name with `GetMyDetails` for the sign-off). Professional, warm, concise, collaborative. Use "we" and "you", plain language, short sentences. No jargon, no buzzwords, no hype. The client is the focus.

---

## Scheduling

**One task, not one per client.** Create it with `SetupScheduledPrompt` the first time any client is configured, weekly on **Friday at 9:00 AM** local unless the user asks for another time.

- Make the task description self-contained: it should say to run the weekly status report for **every client with a saved profile**, per this skill, preparing a draft for each.
- Do not name clients in the schedule. The run reads them from the `clients/` folder, so adding a client never means touching the task.
- Before creating one, call `GetScheduledPrompts` and check it does not already exist. Two batch tasks would produce two sets of drafts.
- To change or pause it, `GetScheduledPrompts` then `EditScheduledPrompt`.

Scheduled runs are safe unattended because the skill only ever drafts.

---

## Guardrails
- **Draft only.** This skill has no send path. Prepare the email; the user sends it.
- **Ground everything** in retrieved recaps, transcripts, notes, and email. Never fabricate progress, decisions, owners, or dates.
- **Client-appropriate only.** Apply the Client-Safety Rules to every line.
- **Domain scoping.** Only content tied to this client's qualifying domains. An extra domain widens one client's report, never the boundary between clients: never leak another client's material.
- **Resolve recipients** with people tools. If a name has multiple matches, confirm before saving.
- **The NetSuite record address is a machine dropbox, not a person.** BCC it (CC only if a BCC cannot be set), never put it on the To: line, and never look it up with people tools. Copy it verbatim from the project record — a mistyped address silently files nothing.
- **Confirm, don't infer.** Every field that reaches the report — recipients, CC, and the People row — is confirmed with the user at setup. If a value is missing or uncertain at run time, ask once and write it back to the profile rather than guessing or shipping a blank.
- **Retrieve once.** One calendar pull per run, one source per meeting, one email query when enabled. Retrieval is what this costs to run.
- **Portable.** Keep settings in `clients/`, and keep the skill free of personal data and of references to other skills, so it can be deployed across the team.
