# STATE

What this project is and what to know before working on it. Not a session log.

## What it is
Python tools that read Notion facilitator-guide pages and use AI models to
suggest cultural adaptations, simplify reading level, and write evaluation
questions (see README.md). Last active development: August 2025.

## Gotchas
- `.claude/settings.local.json` was committed until 2026-11 and is now
  ignored. Claude Code's "Yes, and don't ask again" can save approved
  commands verbatim, secrets included, so keep it out of git. The committed
  versions held only harmless `mkdir`/`mv`/`cp` permissions.
- API keys belong in `.env` (template: `.envexample`), never in tracked files.
