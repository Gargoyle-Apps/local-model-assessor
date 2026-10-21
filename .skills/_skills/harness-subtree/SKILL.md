---
name: harness-subtree
description: "Install or update the skills-harness kit in a consumer repo as a git subtree at .skills-harness/."
triggers:
  - deploy harness as subtree
  - install harness as subtree
  - vendor skills-harness
  - update vendored harness
  - subtree pull skills-harness
  - skills harness subtree
  - add skills-harness subtree
  - migrate manual install to subtree
  - convert harness install to subtree
dependencies: []
version: "1.7.0"
---

# Harness Subtree

## When to use this skill

Load when a consumer repository wants to **vendor the entire skills-harness kit** (instead of copying files by hand) so that updates can be pulled with `git subtree pull`. Also use when an existing subtree-vendored install needs to be updated to a newer kit version, or when converting a legacy file-copy install to subtree.

This skill is for the **consumer** (the repo *receiving* the kit). The upstream `skills-harness` repository itself never installs into itself.

**Do not load** when the repo has no `.skills-harness/` and the user only wants to upgrade a file-copy install or enable native IDE discovery — load **harness-upgrade** instead. If `.skills-harness/` already exists, stay on this skill.

## Why subtree

- **Reproducible installs.** The upstream tree (scripts, templates, bundled skills, `_rules.md`, `_meta.yml`, `CHANGELOG.md`) is fetched as a single commit; no manual file copying.
- **Traceable updates.** `git subtree pull` brings in upstream changes as a merge commit; the local `CHANGELOG.md` (inside the vendored tree) explains what changed.
- **No submodule footguns.** Subtree files live in the consumer's history, so clones, CI, and offline checkouts work without `git submodule update --init`.
- **Per-skill versioning matters.** Because the kit can be updated mid-project, the per-skill `version` field in each `SKILL.md` frontmatter is the contract: when a kit-bundled skill bumps, it shows up after `git subtree pull` and consumers can diff against the prior vendored snapshot.

## Layout

After install, the consumer repo looks like this:

```text
<consumer-repo>/
├── .skills-harness/        ← vendored kit (subtree, do not hand-edit)
│   ├── .skills/
│   │   ├── _harness/       ← scripts + templates + _rules.md
│   │   ├── _skills/        ← kit-bundled skills (skill-template, skill-author, ...)
│   │   ├── _index.md       ← upstream index (kit skills only)
│   │   └── _meta.yml       ← upstream kit_version
│   ├── AGENTS_skills.md    ← bootstrap (copied to root once during setup)
│   ├── README.md
│   ├── CHANGELOG.md        ← read this after every `git subtree pull`
│   └── ...
├── .skills/                ← consumer-owned runtime tree
│   ├── _harness            → symlink → ../.skills-harness/.skills/_harness
│   ├── _skills/
│   │   ├── skill-template  → symlink → ../../.skills-harness/.skills/_skills/skill-template
│   │   ├── skill-author    → symlink → ../../.skills-harness/.skills/_skills/skill-author
│   │   ├── harness-upgrade → symlink → ../../.skills-harness/.skills/_skills/harness-upgrade
│   │   ├── kit-release     → symlink → ../../.skills-harness/.skills/_skills/kit-release
│   │   ├── harness-subtree → symlink → ../../.skills-harness/.skills/_skills/harness-subtree
│   │   └── <prefix>-<your-skill>/   ← symlink → ../../<consumer_skills_dir>/<name> when declared; else real dir
│   ├── _index.md           ← consumer-owned: kit rows + your rows
│   └── _meta.yml           ← consumer-owned: pin to vendored kit_version
└── AGENTS.md               ← Single-Tool harness or Tool-Neutral policy; see AGENTS_skills.md
```

The split is deliberate: kit-owned files live under `.skills-harness/` (overwritten on every pull), while consumer-owned files live under `.skills/`. Symlinks bridge them so the standard runtime paths (`.skills/_harness/...`, `.skills/_skills/<name>/SKILL.md`) keep working without env-var gymnastics.

## Workflow index

Pick the path that matches the repo state. Load the reference file only when you reach that gate.

| Situation | Load |
|-----------|------|
| No `.skills-harness/` yet; first-time subtree install | `references/initial-install.md` |
| `.skills-harness/` exists; pull a newer kit | `references/update-vendored-kit.md` |
| `.skills/` from file-copy; want subtree vendoring | `references/migrate-manual-install.md` |
| Pin to a tag/SHA, directory-symlink quirks, `consumer_skills_dir:`, `--reconcile` | `references/pinning-and-gotchas.md` |

### 1. Initial install

When the consumer repo has **no** `.skills-harness/` directory and you are adding the kit for the first time via `git subtree add`, load `references/initial-install.md` and follow all eight steps (remote, subtree add, `.skills/` symlinks, seed index/meta, bootstrap, gitignore, `check.sh`).

### 2. Update vendored kit

When `.skills-harness/` already exists and the user wants to `git subtree pull` a newer upstream release, load `references/update-vendored-kit.md`. The flow is: pull → read `CHANGELOG.md` → dry-run `migrate-to-subtree.sh --skip-subtree --reconcile --symlink-consumer-skills` → apply (including declared native-target sync) → `check.sh`.

### 3. Migrate manual install to subtree

When the repo has a working `.skills/` tree from an older file-copy install (no `.skills-harness/`) and the user wants subtree-based updates without losing consumer skills, load `references/migrate-manual-install.md`. That reference covers:

- Bootstrapping `migrate-to-subtree.sh` on stale installs (tag-pinned curl URL)
- Fixing stale `repo_url` in `_meta.yml`
- Apply-mode changes, backups, drift handling (`--accept-upstream`, `--force`)
- Prefix/frontmatter audits and the full ten-step migration workflow

### 4. Pinning and troubleshooting

Load `references/pinning-and-gotchas.md` when:

- Vendoring a specific release tag or SHA instead of `main`
- Verifying directory symlinks (`check.sh` vs `readlink` on inner paths)
- Configuring `consumer_skills_dir:` shims
- Understanding what `--reconcile` preserves in `_index.md` / `_meta.yml`
- Diagnosing `SKILLS_CHECK_KIT_SURFACES` behaviour on consumer repos

## Quick commands

```bash
# First install (see references/initial-install.md for full setup)
git subtree add --prefix=.skills-harness skills-harness main --squash

# Update (see references/update-vendored-kit.md for reconcile)
git subtree pull --prefix=.skills-harness skills-harness main --squash

# Migrate audit (dry-run default)
.skills/_harness/migrate-to-subtree.sh

# Preview selecting a native target; repeat with --apply in the chosen migration flow
.skills/_harness/migrate-to-subtree.sh --native-target .agents/skills

# Validate any path
.skills/_harness/check.sh
```

## Trigger evals

Optional regression cases live in `references/trigger-evals.json` — subtree install/update/migrate queries vs **harness-upgrade** near-misses (file-copy upgrade, native discovery only).
