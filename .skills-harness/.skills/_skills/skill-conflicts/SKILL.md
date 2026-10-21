---
name: skill-conflicts
description: "Detect conflicts between repo-managed skills and same-named skills/slash-commands in the user's IDE config."
triggers:
  - detect skill conflicts
  - skill conflict
  - conflicting skills
  - skill name collision
  - check skill conflicts
  - does my config conflict with repo skills
dependencies: []
version: "1.2.1"
---

# Skill Conflicts

## When to use this skill

Load when the user asks whether a skill managed by **this repo** (`.skills/_skills/<name>/`) collides with something in their **IDE user config** — for example after deploying **caveman** to user-level config, after adding a repo skill whose name might already exist at the user level, or when a `/name` invocation behaves unexpectedly.

## What counts as a conflict

The repo inventory excludes internal directories beginning with `_` and migration backups ending in `.bak`.

Skills in this repo are discovered alongside user-level config: skills in `~/.cursor/skills/`, `~/.claude/skills/`, Codex's current `$HOME/.agents/skills/`, and the legacy `~/.codex/skills/` path during migration, plus slash-commands / prompts in `~/.cursor/commands/`, `~/.claude/commands/`, `~/.codex/prompts/`. A collision on the same **name** is a problem only when the definitions differ:

| Situation | Verdict |
|---|---|
| User-config entry is a symlink resolving **into this repo** | **OK** — same skill, deployed from here (e.g. via the **caveman** deploy helper) |
| User-config entry is an independent copy with an **identical** `SKILL.md` | **WARN** — drift risk; prefer a symlink so edits stay in sync |
| User-config entry has a **different** `SKILL.md` (or none) | **CONFLICT** — ambiguous which definition wins; it shadows the repo skill |
| A `~/.<tool>/commands/<name>.md` exists for a repo skill name | **CONFLICT** — the command and the skill share the same `/name` in the slash menu |

## Instructions

1. Run the bundled scanner from the repo root:

```bash
.skills/_harness/skill-conflicts.sh
```

   It enumerates repo-managed skills (dirs under `.skills/_skills/`, skipping `_`-prefixed helpers) and checks each name against the user config locations for Cursor, Claude Code, and Codex. Exit code is `1` when at least one CONFLICT is found, `0` otherwise. Override any scan location with `CURSOR_SKILLS_DIR`, `CLAUDE_SKILLS_DIR`, `CODEX_SKILLS_DIR`, `CODEX_LEGACY_SKILLS_DIR`, `CURSOR_COMMANDS_DIR`, `CLAUDE_COMMANDS_DIR`, `CODEX_PROMPTS_DIR`. Continue is rules-only (no SKILL.md discovery), so it has nothing that shadows a repo skill by name and is not scanned.

2. Report the findings to the user grouped by verdict (CONFLICT first, then WARN, then OK counts). Do not auto-delete anything in the user's config.

3. Resolve, in order of preference:
   - **Managed intent** (they want this repo's version everywhere): replace the divergent user-config entry with a symlink into the repo — for the caveman trio, use the deploy helper documented in **caveman** (see that skill's Notes); otherwise `ln -s` the repo skill dir into the config location.
   - **Independent intent** (the user-config skill is deliberately different): rename one of them so the names no longer collide (apply the prefix convention from **skill-author** to the repo-side name if it is consumer-authored).
   - **Command vs skill**: rename the command file or the skill so they no longer share `/name`.

## Notes

- Detection is best-effort and limited to the scanned locations. Tools with other user-config paths won't be covered unless you pass them via the env overrides above.
- **Subtree installs:** path resolution uses `pwd -L` (same as `check.sh`), so the default scan covers the consumer's `.skills/_skills/` (kit + consumer-authored skills), not only the vendored kit under `.skills-harness/`. Override with `SKILLS_HARNESS_DIR` or `SKILLS_DIR` only for non-standard layouts.
- This scans **user/config-level** collisions only. In-repo index/directory consistency is validated separately by `.skills/_harness/check.sh`.
- Trigger eval cases: `references/trigger-evals.json` (IDE/config collision detection vs **skill-author** / **skill-reviewer** near-misses).
