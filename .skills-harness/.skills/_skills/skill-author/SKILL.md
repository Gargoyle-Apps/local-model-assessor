---
name: skill-author
description: "Creates and registers new harness skills. Load when the user asks to write, author, add, or register a skill."
triggers:
  - write a skill
  - new skill
  - register a skill
dependencies: []
version: "2.2.0"
---

# Skill Author

## Prerequisites

1. If root `AGENTS_skills.md` exists, stop until its Single-Tool or Tool-Neutral bootstrap is complete and the file is removed. Exception: upstream `skills-harness` maintainers keep that canonical template and may proceed for explicitly requested kit work.
2. Otherwise, check root `AGENTS.md`, `README`, and `CONTRIBUTING` for project-specific skill-authoring gates. A missing `AGENTS_skills.md` is normal after bootstrap.

## Instructions

1. Choose the name:
   - In the upstream `skills-harness` repo, keep kit skill names unprefixed.
   - In a consumer repo, prefix the name using `.skills/_meta.yml` or the repo directory name.
   - Read [references/naming.md](references/naming.md) when deriving, choosing, or validating a prefix. Do not rename existing unprefixed skills unless asked.
2. Create `.skills/_skills/<name>/` and copy `.skills/_skills/skill-template/SKILL.md` into it. Load `skill-template` only when canonical layout or refactor guidance beyond that scaffold is needed.
3. Fill in frontmatter. `name` must exactly match the directory; keep `description` within 1–1024 characters and include what the skill does, when it loads, and relevant near-miss exclusions. For optional `compatibility` and `metadata`, follow **skill-template** when those fields are needed.
4. Write imperative, agent-facing instructions in lite, direct prose. Keep one default per concept and include a brief reason only when it changes behavior.
5. Add natural-language `triggers` that repeat intent already expressed by the description. Test a realistic positive phrase and a near miss against the description alone; if routing is unclear, fix the description and retest. Prefixes and fallback-index notes cannot supply missing native routing scope.
6. List only unconditional runtime companions in `dependencies`; load branch-specific companions in the relevant body step. Use `dependencies: []` when none. Avoid cycles.
7. Put bundled files in the standard subdirectories and link every file from `SKILL.md`:
   - `scripts/` for executable helpers
   - `references/` for on-demand guidance
   - `assets/` for templates, schemas, images, or data
8. Run `.skills/_harness/build-index.sh --write`; never hand-edit `.skills/_index.md`.
9. Run `.skills/_harness/check.sh --link`, then `.skills/_harness/check.sh`.
10. For a new or substantially changed skill, load `skill-reviewer` after drafting and address its findings before merge. Request human review when required by project policy.

## Content checks

### Frontmatter

- Use third person in `description`; avoid “I” and “you can use this.”
- State what the skill does and when it should load; be explicit enough to avoid under-triggering.
- Include a meaningful exclusion where a neighboring skill could be confused with this one; do not add boilerplate exclusions. Prefix families express ownership and deployment, not an extra discovery tier.
- Optional `compatibility` records environment requirements; `metadata` holds string annotations such as `family`. Repeat selection-critical requirements in `description`, because hosts may not expose optional fields during discovery.
- Use phrases users naturally say as triggers, not broad single words or internal jargon.
- Set `version`; make `dependencies` explicit.
- Optional trigger cases live in [references/trigger-evals.json](references/trigger-evals.json).

### Body

Order content for an agent that just loaded it:

1. When to use it, including meaningful anti-triggers.
2. Ordered instructions, with links to bundled resources at the step that needs them.
3. Examples only when they remove ambiguity.
4. Failure handling and verification.
5. Rare edge cases or notes.

Keep `SKILL.md` lean. Move optional detail to a reference and gate its load. Do not split one coherent workflow into extra skills merely to shorten the body.

Use short, complete sentences. Drop filler and hedging, but keep articles, conjunctions, explicit actors, and step order when they preserve meaning. Keep `description` and `triggers` in natural user language; do not compress routing metadata into caveman shorthand.

Do not use dropped grammar, invented abbreviations, or arrows as substitutes for causality when they could obscure who acts, what happens first, or whether a step is a confirmation versus an instruction. Write the normal sentence for safety-sensitive or ambiguous steps, then resume lite prose.

### Safety and reuse

- Never include secrets, tokens, or customer data.
- Reference an existing workflow instead of duplicating it.
- Keep design tokens in root `DESIGN.md`, not a skill.
- Require `skill-reviewer` for bundled scripts or instructions that use the shell or network.

## Rename or delete

- Rename the directory and frontmatter `name` together.
- Delete the directory when removing a skill.
- Then regenerate the index and run both checks.

If a dependency cycle is found, load each member once in alphabetical order, report the cycle, and fix the dependency graph.
