# Updating the vendored kit

Use after `.skills-harness/` already exists (subtree-vendored consumer repo).

## Steps

1. **Pull upstream** (from the repo root, on a clean working tree):

   ```bash
   git fetch skills-harness
   git subtree pull --prefix=.skills-harness skills-harness main --squash
   ```

   This creates a merge commit. Resolve conflicts only inside `.skills-harness/` — never hand-edit subtree files outside of conflict resolution.

2. **Read `.skills-harness/CHANGELOG.md`** for the diff between your previous vendored version and the new one. Pay attention to bumped per-skill `version` fields, new bundled skills, and any removed/renamed bundled skills.

3. **Run reconcile + symlink refresh in a single dry-run** to preview everything `--apply` would change:

   ```bash
   .skills/_harness/migrate-to-subtree.sh \
     --skip-subtree --reconcile --symlink-consumer-skills
   ```

   `--skip-subtree` tells the script the kit is already vendored and to act in update-mode. The dry-run prints planned changes to configured indexes, `.skills/_meta.yml`, and any new symlinks for consumer skills under `consumer_skills_dir:`.

4. **Apply:**

   ```bash
   .skills/_harness/migrate-to-subtree.sh \
     --skip-subtree --reconcile --symlink-consumer-skills --apply
   ```

   What this does:
   - **`--reconcile`** regenerates every configured index from installed local `SKILL.md` frontmatter after refreshing skill shims, using the same ordering and wording as `build-index.sh`. Edit consumer row wording in frontmatter; upstream index rows are never copied. Root routing prose and child prose outside generated markers are preserved. Bumps only `kit_version` and `repo_url` in `.skills/_meta.yml`; other fields remain unchanged. No extra generation pass is needed. See `.skills/_harness/index-layout.md` for optional split configuration and ownership. Dry-run includes rows from planned kit and consumer shim additions without modifying the working tree.
   - **`--symlink-consumer-skills`** (only if `consumer_skills_dir:` is declared in `_meta.yml`) walks that directory, ignores entries without a `SKILL.md` and ignores anything whose name collides with a kit skill, and creates `.skills/_skills/<name> → ../../<consumer_skills_dir>/<name>` symlinks for the rest. Pre-existing real directories are never clobbered (the script warns and skips). Idempotent.

5. **Confirm native discovery.** Migration now creates/syncs every target declared under `native_targets:` in `.skills/_meta.yml`. If this consumer predates that field, select a target during migration with `--native-target .agents/skills` (or `.claude/skills`). You can also repair all declared targets directly:

   ```bash
   .skills/_harness/check.sh --link
   ```

   `link.sh` auto-prunes dangling symlinks left by removed kit skills, and `check.sh --link` invokes it for every declared target.

6. **Validate:**

   ```bash
   .skills/_harness/check.sh
   ```

The pre-0.6.1 manual reconcile (hand-merging the index, hand-bumping `_meta.yml`, hand-creating consumer-skill shims with the right relative depth) is no longer needed. If you prefer that flow anyway, omit `--reconcile` and `--symlink-consumer-skills` and the script will print the manual checklist instead.
