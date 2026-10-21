---
name: skill-template
description: "Documents the canonical SKILL.md layout and refactor guide for converting rules or docs into skills. Load when the user needs format guidance, reformatting, or conversion — not when authoring a new skill from scratch."
triggers:
  - skill format
  - reformat skill
  - convert rule
  - skill layout
  - refactor to skill
dependencies: []
version: "1.5.0"
---

# Skill Template

Use this as a starting point for any new skill.
Copy this file to `.skills/_skills/<your-skill-name>/SKILL.md` and fill it in.
Pair with **skill-author** for registration, index sync, and review.

## When to use this skill

Load when the user needs the canonical skill layout, is creating a new skill, or is converting an existing rule or doc into the standard format.

## Skill directory layout

Every skill is a directory. `SKILL.md` is required; optional subfolders follow the [agentskills.io specification](https://agentskills.io/specification) for bundled resources (Level 3 — loaded only when referenced). Cursor and other IDEs may document the same layout ([Cursor skills docs](https://cursor.com/docs/skills) — optional).

```text
.skills/_skills/<name>/
├── SKILL.md          ← required: frontmatter + agent instructions
├── scripts/          ← optional: executable helpers the agent runs via shell
├── references/       ← optional: extra markdown/docs loaded on demand
└── assets/           ← optional: templates, schemas, images, data files
```

**Progressive disclosure:** keep `SKILL.md` focused. Move long reference material to `references/`, deterministic steps to `scripts/`, and static files to `assets/`. Reference them from `SKILL.md` with relative paths (e.g. `scripts/<name>.sh`, `references/<name>.md`). The agent (and native IDE discovery) loads these only when the task needs them — not at trigger time.

**Writing style:** use lite, direct agent prose with short, complete sentences. Keep `description` and `triggers` in natural user language for routing. Keep full grammar when actor, order, confirmation, causality, or safety could become ambiguous; do not use ultra-caveman shorthand as the body or reference style.

Do **not** place scripts or extra markdown loose at the skill root; `check.sh` warns on that layout.

## Instructions

1. Copy this file to `.skills/_skills/<name>/SKILL.md`.
2. Set `name` to match the directory name exactly — kebab-case, 1–64 characters, lowercase alphanumeric and hyphens only, no leading/trailing/consecutive hyphens ([agentskills.io](https://agentskills.io/specification) `name` rules).
3. Write a self-sufficient `description`, 1–1024 characters: what the skill does, when it loads, and relevant exclusions that distinguish nearby skills. Native hosts route from this text without harness-only fields or index notes ([agentskills.io](https://agentskills.io/specification) `description` rules).
4. List natural-language `triggers` users might say; keep their routing distinctions present in the description too. Prefix families are deployment/ownership conventions, not a mandatory family-first loading step.
5. Put only unconditional runtime companions in `dependencies`; load branch-specific companions from the body step that needs them.
6. Fill **When to use**, **Instructions**, and **Examples** for the agent.
7. If the skill needs bundled files, add `scripts/`, `references/`, and/or `assets/` and link to them from `SKILL.md` with relative paths. Optional trigger evals: `references/trigger-evals.json`.

## Optional portability fields

Use `compatibility` only for specific environment requirements (1–500 characters). Use `metadata` for optional string annotations. These fields travel with the skill; host support varies, so selection-critical requirements must also appear in `description`.

```yaml
compatibility: "Requires a consumer checkout containing mods.yaml and servers[]."
metadata:
  family: server
  revision: "1"
```

The zero-dependency validator supports single-line plain or quoted strings and flat block maps, or flow maps such as `metadata: {family: server}`. Quote text that YAML would treat as a number, boolean, or null. Use `metadata: {}` for an empty map. Multiline scalars, aliases, tags, nested collections, and complex escapes are not supported by the kit validator; use single-line strings with literal UTF-8 instead. Optional fields are preserved in frontmatter and do not add catalog columns. `metadata.family` is an annotation; `_meta.yml` prefix declarations control optional index grouping.

## Body scaffolds (copy into your skill)

Use these sections as needed — delete unused headings rather than leaving them empty:

```markdown
## When to use this skill

- Concrete trigger one.
- Concrete trigger two.

## Prerequisites

Skip if none.

## Instructions

1. First step.
2. Verification step.

## Examples

**Scenario name** — input / expected outcome.

## Failure modes

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
|         |              |     |

## What not to do

- Scope foot-gun specific to this skill.
```

## Examples

- "Add a skill for our deploy checklist" → use this template, then register via **skill-author** (`build-index.sh --write`).
- "Skill with a validation script" → put `scripts/<name>.sh` in the skill dir and tell the agent to run it from **Instructions**.

---

<!--
REFACTOR GUIDE

Use this section when converting an existing file (Cursor rule, plain markdown
instructions, AGENTS.md section, etc.) into a standard SKILL.md.

Steps:
1. Identify the core capability the existing file describes
2. Extract it into a new directory: .skills/_skills/<name>/SKILL.md
3. Add YAML frontmatter (name, description, triggers, dependencies, version)
4. Rewrite the body as lite, agent-facing instructions (not human docs); preserve full grammar for routing, order, confirmation, and safety
5. Run .skills/_harness/build-index.sh --write to regenerate .skills/_index.md
6. Remove or replace the original content with a one-liner pointing to the skill

Common sources to refactor:
- Cursor .mdc rules → extract procedural ones as skills, keep declarative ones as rules
- AGENTS.md sections → any multi-step workflow becomes a skill
- Inline comments or README instructions → if an agent needs to follow them, they're a skill

What stays in AGENTS.md / harness files (not skills):
- Project-level conventions (naming, structure)
- Always-on constraints
- Pointers to the index

What becomes a skill:
- Any multi-step workflow
- Domain-specific knowledge (how to use a particular tool or API)
- Anything the agent should only load when relevant
-->
