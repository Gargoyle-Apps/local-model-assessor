# Pinning and gotchas

## Pinning to a specific kit version

To vendor a specific release instead of `main`:

```bash
git subtree add --prefix=.skills-harness skills-harness <tag-or-sha> --squash
# later
git subtree pull --prefix=.skills-harness skills-harness <new-tag-or-sha> --squash
```

Tags follow the kit's semver (see upstream `CHANGELOG.md` and `_meta.yml`).

## Notes and gotchas

- **Do not edit files inside `.skills-harness/`.** Local edits are silently overwritten on the next `git subtree pull`. Contribute changes upstream instead, or use the Tool-Neutral setup and override behaviour in your own consumer-owned skills.
- **Consumer skills live outside the subtree.** Bodies sit in real directories under `.skills/_skills/<prefix>-<name>/` (traditional layout) or under `consumer_skills_dir:` (e.g. `.cursor/skills/<name>/`) with `.skills/_skills/<name>/` as a directory symlink shim. Apply the prefix convention from `skill-author`.
- **Directory symlinks — inner files look like plain files (gh issue #5).** Kit skills and `consumer_skills_dir` shims link the **directory** `_skills/<name>/`, not individual files. `SKILL.md` inside therefore shows as a regular file (`-rw-r--r--`); `readlink` on it is empty and `test -L` is false even when fully in sync. To verify wiring, run **`check.sh`** (prints `directory symlink → <target> ✓` per entry) or `readlink .skills/_skills/<name>` on the **directory** itself — not on inner paths.
- **`AGENTS_skills.md` is ephemeral.** It is copied from `.skills-harness/AGENTS_skills.md` only during bootstrap and removed afterwards. It will reappear in `.skills-harness/` after each pull — that's fine; do not copy it back to root unless you are re-bootstrapping.
- **`check.sh` works through symlinks.** No env-var overrides are needed for the symlinked layout above. Use `SKILLS_*` env vars only if you choose a non-symlink layout (e.g. running scripts directly out of `.skills-harness/`).
- **Kit-bundled skill IDs stay unprefixed** (`skill-author`, `harness-upgrade`, etc.). Your own skills are prefixed per `skill-author`'s naming convention. The two coexist in `.skills/_index.md`.
- **Per-skill `version` is the consumer's contract** with kit skills. When `git subtree pull` brings in a skill bump, treat it like any vendored dependency upgrade: read the changelog, run `check.sh`, and smoke-test the affected skill.
- **`check.sh` is symlink-safe (0.6.0+).** Path resolution uses the script's invocation path with `pwd -L`, so running `.skills/_harness/check.sh` after migration correctly inspects the consumer's `_skills/` and `_index.md` rather than the subtree's. No wrapper script needed.
- **`skill-conflicts.sh` uses the same symlink-safe resolution (gh issue #14).** Running `.skills/_harness/skill-conflicts.sh` scans the consumer's full `_skills/` set (kit + consumer-authored skills), not only the vendored kit under `.skills-harness/`.
- **Consumer/kit role is auto-detected (0.6.0+).** `check.sh` skips the kit-surface assertions (CHANGELOG/README/AGENTS_skills.md kit-version markers) automatically when `.skills-harness/` exists at the repo root or `.skills/_meta.yml` declares `role: consumer`. Set `SKILLS_CHECK_KIT_SURFACES=1` to force the kit-author checks anyway, or `SKILLS_CHECK_KIT_SURFACES=0` to suppress them on a non-subtree consumer install.
- **`consumer_skills_dir:` schema (optional).** If real skill bodies live outside `.skills/_skills/` (for example a Cursor-style repo that keeps them under `.cursor/skills/<name>/`), record the path in `.skills/_meta.yml`:

  ```yaml
  consumer_skills_dir: .cursor/skills
  ```

  Then `migrate-to-subtree.sh --symlink-consumer-skills [--apply]` generates the `.skills/_skills/<name> → ../../<consumer_skills_dir>/<name>` shims with correct relative depth. Idempotent. Refuses to clobber real directories at the link path (warns and skips). Skips entries without a `SKILL.md` and any name that collides with a kit skill. (0.6.1+)
- **`--reconcile` uses local frontmatter.** Regenerates all configured index rows with `build-index.sh`, after skill shims are refreshed; bumps only `kit_version`/`repo_url` metadata from the subtree. Consumer routing prose outside generated tables/blocks and other metadata fields are preserved. Edit row wording in `SKILL.md`, never copy upstream index rows. Use after every `git subtree pull`; combine with `--symlink-consumer-skills` for a single-command update. See `.skills/_harness/index-layout.md` for optional split configuration and safe migration.
