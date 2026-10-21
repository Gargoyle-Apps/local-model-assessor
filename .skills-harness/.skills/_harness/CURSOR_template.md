<!-- SETUP — remove this entire section after setup is complete -->

## Setup instructions (Cursor)

1. Delete this SETUP section (from the opening comment through `<!-- END SETUP -->` inclusive).
2. Install the harness into root **`AGENTS.md`**:
   - **If `AGENTS.md` does not exist:** create it containing only the harness below (from `# Skills Harness` through the Rules bullets — no YAML frontmatter).
   - **If `AGENTS.md` already exists** with project content: **append** the harness under a new `## Skills Harness` heading. Do not replace existing project instructions.
3. **Native discovery:** run `.skills/_harness/link.sh .agents/skills` from the repo root. This records the target in `.skills/_meta.yml`; add `.agents/skills/` to `.gitignore` if not already present.
4. Delete **`AGENTS_skills.md`** from the repository root (the temporary bootstrap file).

**Verify:** `AGENTS.md` contains the Skills Harness section exactly once; no duplicate always-on copy exists in `.cursor/rules/skills-harness.mdc`; `.agents/skills/` contains symlinks to `.skills/_skills/`; this SETUP block is gone; `AGENTS_skills.md` is removed.

<!-- END SETUP -->

---

# Skills Harness (Cursor)

Skills are in `.skills/_skills/`. The index is at `.skills/_index.md`.

## Rules

- Prefer the host's native skill catalog. Route from each skill's `name` and `description`, then load the full `SKILL.md` only for a clear match.
- Keep descriptions self-sufficient: state what the skill does, when it loads, and relevant exclusions. Prefix families describe deployment and ownership; they are not a mandatory routing tier. Harness-only `triggers` and index notes must not carry essential scope missing from the description.
- Consult `.skills/_index.md` only when native discovery is unavailable, routing is ambiguous or missing, the host warns that skills were omitted, or the task concerns the catalog itself. Prefer a targeted search before reading the full index.
- Never load skills preemptively.
- For general repository or PR reviews, preserve the host's review workflow, full requested scope, and output format. Specialized review skills may contribute bounded checks of relevant files; their scope restrictions and report formats do not replace the parent review. Generic review commands alone do not request a specialized reviewer or terse style.
- After loading a skill, load only its unconditional `dependencies`; load conditional companion skills only when their documented branch is reached.
- **Skill frontmatter is authoritative for generated catalog rows.** When you create, rename, or delete a skill, regenerate the index with `build-index.sh --write` in the same operation. Preserve human-authored routing notes and never leave the catalog out of sync with `.skills/_skills/`.
- If `.skills/` is missing from the repo, warn the user and do not invent skill content.
- **Subtree-vendored installs:** if `.skills-harness/` exists at the repo root, the kit is vendored as a git subtree — treat files under `.skills-harness/` as upstream-owned (do not hand-edit; updates come via `git subtree pull`) and use the **harness-subtree** skill for install/update/reconcile work.
- **Temporary bootstrap only:** While `AGENTS_skills.md` exists at the repository root (skills-harness bootstrap not finished), do not create or refactor skills or change `.skills/_index.md` for new skills — complete the **Single-Tool** or **Tool-Neutral** setup in that file. Once it is removed, this rule does not apply. Tool-Neutral repos may record ongoing policy in root `AGENTS.md` instead.

<!-- END RULES -->
