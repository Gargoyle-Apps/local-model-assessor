# Migrating an existing manual install to subtree

Use when a repo already has `.skills/` (installed by file-copy from an earlier kit version) and you want to switch to subtree-vendored updates **without losing consumer-authored skills, the index, or `_meta.yml`**.

The kit ships a helper: **`.skills/_harness/migrate-to-subtree.sh`**. It is **dry-run by default** — it inventories the repo, classifies each skill as kit-bundled vs. consumer-authored, and previews changes using available sources. Before the subtree is vendored, upstream contents are unavailable; a stale install may also lack the index generator. The preview reports these limits and continues with the remaining plans. Re-run with `--apply` to perform the changes.

## Bootstrapping the script on a stale install

Older harness installs (pre-0.6.0) don't ship `migrate-to-subtree.sh`. Pull it from upstream into the existing `.skills/_harness/` directory before running:

```bash
curl -sSLo .skills/_harness/migrate-to-subtree.sh \
  https://raw.githubusercontent.com/Gargoyle-Apps/skills-harness/v1.5.0/.skills/_harness/migrate-to-subtree.sh
chmod +x .skills/_harness/migrate-to-subtree.sh
```

The script's dirty-tree check ignores its own untracked file plus any `*.bak/` directories, so dropping it directly into `.skills/_harness/` and running from there is fine. Use `main` in the URL only for bleeding-edge testing; prefer a kit release tag (e.g. `v1.5.0`) for reproducible installs.

## Stale `repo_url` in `.skills/_meta.yml`

Legacy manual installs frequently carry an outdated upstream URL — typically a fork or pre-rename location that is no longer reachable (e.g. `gotalab/skills-harness`, which 404s). When migrating these repos to subtree, the script will **refuse** to vendor any URL that doesn't contain `Gargoyle-Apps/skills-harness`. **This is expected**, not a bug in the consumer's repo.

The standard fix when adopting the official upstream:

```bash
.skills/_harness/migrate-to-subtree.sh \
  --remote-url https://github.com/Gargoyle-Apps/skills-harness \
  --apply --reconcile --symlink-consumer-skills
```

`--reconcile` rewrites `.skills/_meta.yml` so `repo_url` and `kit_version` match the vendored subtree, so no manual edit is needed afterwards.

`--accept-derived-url` exists only for the rare case where a team **deliberately** maintains a private fork at the URL `_meta.yml` lists and wants to vendor that fork. **Do not use `--accept-derived-url` to silence the canonical check on a stale install** — the subtree add will fail if the URL is dead, or (worse) silently vendor the wrong tree.

## What it changes (apply mode)

- Adds the upstream remote (`skills-harness` by default; URL pulled from `.skills/_meta.yml` `repo_url` or `--remote-url`).
- Runs `git subtree add --prefix=.skills-harness <remote> <ref> --squash` (one squash commit, fully reversible with `git revert`).
- For each **kit-owned** target:
  - `.skills/_harness/` is moved aside to `.skills/_harness.bak/` and replaced with a symlink into the subtree.
  - For each kit-bundled skill (`skill-template`, `skill-author`, `harness-upgrade`, `kit-release`, `harness-subtree`): if the local copy is **byte-identical** to upstream, it is moved to `<name>.bak/` and replaced with a symlink. If the local copy **differs** (you hand-edited it, or you're on an older kit version), the script **leaves the local copy in place** and prints the diff command. Two ways to accept upstream after review:
    - `--accept-upstream <name>[,<name>…] --apply` — surgical: backup-and-symlink only the listed skills.
    - `--force --apply` — sledgehammer: backup-and-symlink **every** drifted kit skill in one pass.

## What it never touches

- **Consumer-authored skills** (any directory under `.skills/_skills/` whose name is not in the kit-bundled set) — left exactly as they are.
- **Configured indexes and `.skills/_meta.yml`** — consumer-owned. By default the script prints a reconcile checklist instead of editing them. Pass **`--reconcile`** to regenerate all rows from installed local frontmatter and bump `kit_version`/`repo_url`; routing prose outside generated tables/blocks and other metadata fields stay intact. See `.skills/_harness/index-layout.md` for optional split indexes. Passing **`--native-target`** may add only the requested `native_targets` entry to `_meta.yml`.
- **Native discovery symlink directories** (`.agents/skills/`, `.claude/skills/`) unless `--native-target` is supplied or `native_targets:` is already declared. In those cases migration creates/syncs the declared targets without touching unrelated entries.

## What it audits (warns, never modifies)

- **Prefix convention** (per **skill-author**): for every consumer-authored skill, the script checks the name against the repo's allowed prefix set:
  - **Default (single-prefix repos):** the expected prefix is derived from the repo's root directory name (split on `-`/`_`, first letter of each segment, lowercased, append `-`). In a repo named `eng-package-management`, a skill called `deploy-checklist` triggers `→ suggested rename: epm-deploy-checklist`.
  - **Multi-prefix repos:** if `.skills/_meta.yml` declares a block `prefixes:` list, the script accepts **any** of those prefixes and ignores the auto-derived one. Use the block form supported by both migration auditing and split index generation:

    ```yaml
    prefixes:
      - bld-
      - bin-
    ```

    A violation message lists all declared prefixes so the user can pick the family the skill belongs to. Kit-bundled skills stay unprefixed in either mode.

  Renaming is a manual, deliberate step — the script never renames automatically because the index, frontmatter, and any cross-skill `dependencies` references all need to update together.
- **Frontmatter shape**: each consumer SKILL.md is checked for the five required fields (`name`, `description`, `triggers`, `dependencies`, `version`) and that `name` matches the directory. Missing fields are reported so you can patch them up against the current `skill-template`.

## Workflow

1. **Audit first** (no changes):

   ```bash
   .skills/_harness/migrate-to-subtree.sh
   ```

   Read the output. Note any kit skills flagged as drifted, and any consumer skills flagged for prefix or frontmatter issues.

2. **Decide on drifted kit skills.** For each drift report, run the suggested `diff -ru` command. If your edits should be upstreamed, contribute them and pull a new release later. If your edits are throwaway/local and you want the upstream version, plan to re-run with `--accept-upstream <name>` (per-skill) or `--force` (all drifted skills).

3. **Fix prefix and frontmatter issues** *before* the migration if possible — it keeps the index reconcile (step 6) cleaner. For each prefix warning:
   - `git mv .skills/_skills/<name> .skills/_skills/<prefix><name>`
   - Edit `<prefix><name>/SKILL.md` frontmatter: set `name: <prefix><name>`
   - Search for `dependencies:` mentions of the old name across `.skills/_skills/*/SKILL.md` and update them
   - Run `.skills/_harness/build-index.sh --write` to regenerate configured index rows from frontmatter (or defer to step 6 if the old install lacks the generator)
   - Run `.skills/_harness/check.sh` to confirm

4. **Apply** (clean working tree required; the script ignores its own untracked file and `*.bak/` dirs):

   ```bash
   .skills/_harness/migrate-to-subtree.sh --apply
   .skills/_harness/migrate-to-subtree.sh --apply --accept-upstream skill-author,skill-template
   .skills/_harness/migrate-to-subtree.sh --apply --force
   ```

   To collapse steps 6–7 (index generation and `_meta.yml` bump) into the same run, add `--reconcile`. To also generate `.skills/_skills/<name>/` shim symlinks when `consumer_skills_dir:` is declared, add `--symlink-consumer-skills`. Both support dry-run; preview first, noting any unavailable-source limitations, then re-run with `--apply`.

5. **Inspect the backups.** The script left `.skills/_harness.bak/` and any `.skills/_skills/<name>.bak/` directories so you can confirm nothing important was lost. Skill directories ending in `.bak` are excluded from catalog generation, validation, and native discovery. Once happy, `rm -rf` them in a follow-up commit (or keep them on a separate branch).

6. **Regenerate the configured catalog.** Run `.skills/_harness/build-index.sh` to preview changes, then rerun with `--write`. Installed local skill frontmatter supplies every row, including consumer skills and retained local kit overrides. The generator updates the root table for single layout or child tables and root links for split layout, preserving prose outside generated regions. `--reconcile` performs this step automatically; do not copy upstream index rows.

7. **Bump `.skills/_meta.yml`** `kit_version` to match `.skills-harness/.skills/_meta.yml` (or pin lower and document why).

8. **Create/sync native discovery.** Existing `native_targets:` declarations are preserved and synchronized automatically. For a legacy install with no declaration, add `--native-target .agents/skills` to the migration command, or call `link.sh` once (it records the path):

   ```bash
   .skills/_harness/link.sh .agents/skills    # or .claude/skills
   # or create/sync every declared native target and validate in one step:
   .skills/_harness/check.sh --link
   ```

9. **Validate:**

   ```bash
   .skills/_harness/check.sh
   ```

10. **Commit.** Two commits are usually clearest: the squashed `subtree add` commit (created by step 4) and a follow-up commit for the symlinks, index reconcile, `_meta.yml` bump, and `.bak` cleanup.

From this point on, updates are `git subtree pull` — load `references/update-vendored-kit.md`.
