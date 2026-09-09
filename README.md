# weekly-status-report

A Microsoft Copilot Cowork skill that drafts the weekly client status report. It scans the week's client meetings, pulls hours from Power BI (PM Reports), and prepares a branded HTML email draft in Outlook for the PM to review and send. It never sends email on its own.

## Install

1. Download this repo as a zip (Code → Download ZIP on GitHub), or clone it.
2. In Copilot Cowork, upload the folder as a new skill named `weekly-status-report`.
3. Run it for a client for the first time; it will walk you through one-time setup (point of contact, internal CC, Power BI project) and save your own profile under `clients/`.

Your client profiles never leave your own copy: the `clients/` folder ships empty and is gitignored, so nothing you configure gets shared back here.

## What's in this repo

- `SKILL.md` — the skill's instructions
- `scripts/build_report.py` — the HTML renderer
- `templates/weekly-status-template.html` — the branded email template
- `assets/eb-logo.png` — Eide Bailly logo used in the report
- `clients/` — where your own client profiles get saved (empty here on purpose)

## Updates

This repo is maintained by [Daniel Daou](mailto:ddaou@eidebailly.com). Pull the latest whenever there's a new version.
