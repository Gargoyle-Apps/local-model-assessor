---
name: skill-catalog-maintainer
description: "Audits and optimizes skills under .skills/_skills/ for overlap, routing, context cost, dependencies, and index drift; edits require dry-run and confirmation."
triggers:
  - skill inventory
  - catalog health
  - duplicate skill triggers
  - skill overlap
  - split this skill
  - skill catalog audit
  - reduce skill context
  - condense this skill
  - trim skill tokens
dependencies: []
version: "1.3.0"
---

# Skill Catalog Maintainer

Audit every skill in `.skills/_skills/`, cluster by routing intent, measure context cost, and report overlap, redundancy, or oversize skills. May optimize existing skills — dry-run and explicit confirmation required.

## Edit authority (the exception)

By default, skills describe workflows; they do not edit sibling skills. **This skill is the exception** for catalog upkeep — with guardrails.

**Permitted edits** (after confirmation):

- Other skills' `SKILL.md` — frontmatter (`description`, `triggers`, `dependencies`, `version`) and body
- Other skills' `references/` — add or edit gated prose extracted from `SKILL.md`; do not change scripts or assets
- `.skills/_index.md` and configured generated child indexes — only via `build-index.sh --write` after approved frontmatter or layout changes; preserve consumer-owned prose
- `.skills/_meta.yml` — only `index_layout` and `index_fallback` for an approved catalog migration; reuse existing prefix declarations and preserve other settings
- Root `AGENTS.md` — Skills / harness policy sections when catalog conventions change

**Required guardrails:**

1. **Dry-run first** — produce the report (steps 1–6) with a `### Planned edits` section: numbered bullets, fenced before/after per file. Do not write yet.
2. **Explicit confirmation** — wait for approval ("apply all", "apply 1 and 3", or revisions). Ambiguity means stop.
3. **Version bumps** — any non-typo skill edit bumps `version` in frontmatter; mention in `CHANGELOG.md` when cutting a kit release.
4. **Index sync** — run `.skills/_harness/build-index.sh --write` after frontmatter edits.
5. **Conditional companions** — at the apply-edits gate, load **skill-author** only when creating or restructuring a skill, and load **skill-reviewer** only when the approved diff changes a skill directory. Do not load either for report-only catalog audits.

**Refuse without maintainer action:** rename skill directories, delete skills, bulk retag more than ~3 skills in one pass.

## When to use

- Inventory or health check of the skill catalog
- Suspected duplicate triggers or redundant workflows
- Split candidates for oversized skills
- Direct, transitive, or native metadata context warnings
- Requests to condense an existing skill without changing behavior
- Governance housekeeping before a large refactor

## Steps

### 1. Enumerate skills

```bash
find .skills/_skills -name SKILL.md ! -path '*/_*/*'
```

Skip `_`-prefixed harness internals. Exclude `skill-template` from overlap analysis (starter artifact) but list it under authoring aids.

Confirm each directory `name` matches frontmatter `name`; flag drift. Run `.skills/_harness/check.sh` for index ↔ directory consistency.

### 2. Capture metadata and size

Per skill: `name`, `version`, `description`, `triggers`, direct bytes and lines, dependencies, and presence of `references/` / `scripts/` / `assets/`. Run `.skills/_harness/check.sh` to capture transitive-load, native-metadata, and index-size warnings.

### 3. Cluster by triggers

Build **trigger phrase → [skills]**. Flag phrases shared by two or more runtime skills. Note overly generic triggers that appear on many skills.

### 4. Cluster by intent

Derive a 5–8 word intent label from each `description`. Group skills with overlapping user outcomes. Classify: **complementary**, **redundant**, or **unclear boundary** (recommend boundary sentences in descriptions).

### 5. Context cost

| Band | `SKILL.md` lines | Guidance |
|------|------------------|----------|
| Comfortable | under ~180 | No action on length alone |
| Large | ~180–350 | Move prose to `references/` |
| Split candidate | over ~350 | Consider split or reference extraction |

If most prose already lives in `references/`, say so.

When a skill or dependency chain needs reduction, read [references/context-optimization.md](references/context-optimization.md). Preserve routing, behavior, safety gates, and exact commands; passing a size threshold alone is not success.

When navigation complaints, index warnings, new families, or catalog growth warrant investigation, load [references/index-assessment.md](references/index-assessment.md). Reuse this audit's inventory and measurements; keep the assessment read-only. Use [references/index-assessment-evals.json](references/index-assessment-evals.json) when evaluating its decisions. No fixed skill count or file size requires a split.

### 6. Deliver the report

Sections: **Trigger clusters**, **Intent collisions**, **Context cost / structure**, **Recommended next actions**. Include direct and transitive before/after metrics for optimization work. Include planned edits only when the user may want this skill to apply fixes. Optional eval cases: `references/trigger-evals.json`.

## What not to do

- No silent edits
- No rename or delete
- No loss of behavior, safety, or routing merely to meet a context budget
- No bulk caveman rewrite of skill bodies or references; reduce context through dependency pruning, gated extraction, and deduplication
- Don't dump every skill body into chat — summarize and link paths
