# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.7.0] - 2026-10-20

### Fixed

- **Catalog generation and reconciliation ([#21](https://github.com/Gargoyle-Apps/skills-harness/issues/21)).** Generate catalog rows from installed skill frontmatter in both workflows, validate stale/duplicate/missing rows, and diagnose unsupported legacy multi-table layouts instead of silently preserving duplicates. Keep consumer routing prose outside generated regions.
- **Caveman uninstall ([#19](https://github.com/Gargoyle-Apps/skills-harness/issues/19), `caveman` v1.3.3).** Remove managed absolute and relative symlinks after source skill removal or rename without deleting real files, directories, or foreign checkout links.
- **Migration and backup handling.** Remove former kit shims only when their exact target proves ownership; exclude `.bak` and internal directories throughout migration, validation, native discovery, and conflict scanning (`skill-conflicts` v1.2.1). Repair previously exposed managed backup links while preserving backup contents and foreign entries. Legacy dry-runs continue when the generator is unavailable and report unavailable upstream sources explicitly.
- **Generator configuration and diagnostics.** Accept inline YAML comments in supported index configuration, reject malformed split-prefix lists and inconsistent hyphenated names, preserve logical consumer paths under Bash physical mode, and refuse ambiguous dangling child indexes without deleting them. Quiet validation suppresses success output while retaining warnings and failure diffs.
- **Optional-field indentation.** Diagnose misplaced `compatibility` and `metadata` keys after required scalar/list fields while preserving nested extension data and multiline scalar content; the bounded helper does not claim whole-document YAML validation.

### Added

- **Opt-in generated sub-indexes ([#21](https://github.com/Gargoyle-Apps/skills-harness/issues/21)).** Preserve the default single catalog; explicit split configuration adds a root directory of links and generated family indexes with a fallback group, dry-run diffs, ownership checks, and cross-index validation.
- **Optional portability fields ([#17](https://github.com/Gargoyle-Apps/skills-harness/issues/17)).** Document and validate `compatibility` and flat string-to-string `metadata` when present, including `metadata.family` as an annotation rather than a routing gate. The zero-dependency validator diagnoses unsupported YAML forms.
- **Catalog structure assessment ([#23](https://github.com/Gargoyle-Apps/skills-harness/issues/23), `skill-catalog-maintainer` v1.3.0).** Conditionally load an evidence-based reference for routing misses, whole-index reads, and independent family growth; reuse audit evidence, retain read-only assessment and explicit migration approval, and keep one index when a split is unsupported by evidence. Downstream consumer counts are not this kit's baseline or automatic split thresholds.
- **Regression coverage.** Add generated-index, optional-frontmatter, dangling-link uninstall, migration-review, and pipeline-review fixtures to the Bash 3.2 smoke suite.

### Changed

- **Portable routing contract ([#17](https://github.com/Gargoyle-Apps/skills-harness/issues/17)).** `skill-author` v2.2.0, `skill-template` v1.5.0, README, and canonical rules require self-sufficient descriptions with relevant near-miss exclusions. Prefix families describe ownership/deployment; harness triggers cannot carry essential scope absent from descriptions. All ten templates now identify frontmatter as authoritative for generated rows.
- **Discovery-cost review ([#22](https://github.com/Gargoyle-Apps/skills-harness/issues/22), `skill-reviewer` v1.3.0).** Separate native discovery, activation, and fallback costs; require concrete shortening proposals with character counts and preserved positive/near-miss routing. Include safe-shortening, justified-length, and rejected-compression examples without weakening existing safety or over-compression checks.
- **Scoped review routing.** `skill-reviewer` v1.3.0 handles direct skill reviews or assigned skill-specific passes, preserving a parent repository review's scope, schema, and verdict. `caveman-review` v1.1.0 requires a requested terse style and no longer claims generic review phrases or `/review`. Canonical rules and all templates preserve host-led `/review` and `/codereview` workflows; skill-only reports no longer produce a repository approval footer.
- **Consumer update guidance.** `harness-subtree` v1.7.0 and `harness-upgrade` v1.3.0 use local-frontmatter catalog generation for single and split layouts instead of copying upstream rows.

## [1.6.0] - 2026-08-17

### Fixed

- **`skill-conflicts.sh` — symlink-safe `SKILLS_DIR` (gh issue [#14](https://github.com/Gargoyle-Apps/skills-harness/issues/14)).** Path resolution now uses `${BASH_SOURCE[0]}` + `pwd -L` and honors `SKILLS_HARNESS_DIR`, matching `check.sh`. Default invocation on subtree-vendored consumer repos scans the full `.skills/_skills/` set (kit + consumer-authored skills) instead of only `.skills-harness/.skills/_skills/`.
- **`sync.sh` rules-boundary handling.** Rules synchronization now keys off `<!-- END RULES -->` after the selected `## Rules` section, so an earlier `<!-- END SETUP -->` marker cannot be mistaken for a post-rules appendix and duplicated into templates.

### Added

- **`skill-talker` (v1.0.0)** — read-only skill interrogation and goal-to-skill mapping from native metadata and the harness index, with bounded document inspection and explicit opt-in handoffs to actionable skills.
- **`toon-export` (v1.1.1)** — universal TOON encode/validate skill with JSON-hub ingest (YAML/CSV adapters in one skill, no per-format siblings); `@toon-format/cli` encode, strict-decode gate, `scripts/validate-toon.sh`, `scripts/encode-from-json.sh`, `scripts/csv-to-json.sh`.
- **Level 3 skill resources** — `skill-template` / `skill-author` document `scripts/`, `references/`, `assets/`; `check.sh` validates layout and path references; `caveman` deploy helper moved to `scripts/deploy.sh`.
- **`skill-reviewer` (v1.0.0)** — quality and security rubric for skill changes (`references/` bundle: quality, security, plugin, output format, examples, threat model).
- **`skill-author` (v2.0.0)** — merged authoring quality guidance (description, body structure, writing style, trigger smoke-test).
- **`skill-template` (v1.3.1)** — optional body scaffolds; points to **skill-author** for registration.
- **`skill-catalog-maintainer` (v1.0.0)** — catalog audit, overlap detection, guarded edit authority.
- **`skill-import` / `skill-export` (v1.0.1)** — vendored skill pull and target-only publish with optional `upstream:` lineage.
- **Persisted native discovery targets.** `.skills/_meta.yml` now declares `native_targets`; `link.sh` records selections, `check.sh --link` creates/repairs them, and subtree migration preserves and syncs them or accepts repeatable `--native-target` values.
- **Context-health validation and smoke coverage.** `check.sh` now validates Agent Skills name/description shape and warns on missing/cyclic dependencies, transitive dependency-body cost, native metadata budget, index growth, and large skill bodies. `.skills/_harness/tests/smoke.sh` covers native-target repair, Cursor single-surface setup, and current/legacy Codex user-skill paths.

### Changed

- **Skill authoring prose contract ([#18](https://github.com/Gargoyle-Apps/skills-harness/issues/18)).** The README and `skill-author` v2.1.0 / `skill-template` v1.4.0 now set lite, direct prose as the skill-body default while preserving natural-language routing and explicit safety/order. `skill-reviewer` v1.1.0 flags harmful over-compression, `skill-catalog-maintainer` v1.2.1 rejects bulk caveman rewrites as context optimization, and `caveman` v1.3.2 clarifies that reply compression is not catalog policy.
- **Native-first routing.** Canonical rules and all ten templates now route from native `name` + `description` metadata and consult `.skills/_index.md` only as a targeted fallback for unavailable, ambiguous, omitted-skill, or catalog-maintenance cases. Conditional companion skills load only when their branch is reached.
- **Cursor setup uses one shared always-on surface.** `CURSOR_template.md` installs the shared harness in root `AGENTS.md` and no longer duplicates it in an `alwaysApply: true` `.cursor/rules/skills-harness.mdc` file.
- **Current Codex user-skill path.** `caveman` v1.3.1 deploys Codex skills to `$HOME/.agents/skills` and removes managed legacy entries during uninstall; `skill-conflicts` v1.2.0 scans that path plus legacy `~/.codex/skills` with a migration warning.
- **Conditional catalog companions.** `skill-catalog-maintainer` v1.1.0 removes its eager `skill-author` dependency and loads author/reviewer companions only at the apply-edits gate. Related workflow docs were updated in `skill-author` v2.0.2, `harness-upgrade` v1.2.0, and `harness-subtree` v1.6.0.
- **Lean skill loading.** `skill-author` v2.0.3, `skill-import` v1.0.1, and `skill-export` v1.0.1 now load branch-specific companions only when needed; `skill-author` and `toon-export` v1.1.1 move optional detail to gated references and trim routing metadata.
- **Skill context optimization.** `skill-catalog-maintainer` v1.2.0 now audits direct, transitive, and native-metadata cost and applies a gated behavior-preserving compaction workflow; `skill-template` v1.3.1 makes conditional dependency loading explicit.

### Removed

- **`design-md-coord`** — not bundled in wide release; retained on the `design-md-coord` branch for optional vendoring.

## [1.5.0] - 2026-07-03

### Added

- **`caveman/deploy.sh --print` (skill v1.2.0)** — user-level activation via copy/paste for globals that can't be scripted (e.g. Cursor's Settings → Rules → User Rules). Writes nothing: `stdout` is the paste-ready activation block, `stderr` says where to paste it. `target` is optional and only tailors the paste hint (`cursor`/`claude`/`codex`/`continue`, else generic), leaving the door open for any IDE with a "User Rules" / "Custom Instructions" box. Honors `--level`.

### Fixed

- **Harness shell safety and docs drift ([#6](https://github.com/Gargoyle-Apps/skills-harness/issues/6)–[#11](https://github.com/Gargoyle-Apps/skills-harness/issues/11)).** Hardened `build-index.sh`, `check.sh`, `link.sh`, `sync.sh`, `migrate-to-subtree.sh`, and `caveman/deploy.sh` for bash 3.2, destructive-op edge cases, and symlink topology. `build-index.sh` is idempotent with corrected `SKILL.md` frontmatter parsing; `check.sh` no longer crashes on bash 3.2 and reports dangling native-discovery symlinks; `link.sh` prune/`--clean` removes broken symlinks; `sync.sh --write` no longer wipes Rules blocks; `caveman/deploy.sh` avoids unsafe `rm -rf` / `sed`-to-EOF patterns on user skill dirs; `migrate-to-subtree.sh` closes subtree-migration safety gaps. Docs: restore missing `## [x.y.z]` headings for tagged releases in CHANGELOG, fix broken `v1.0.0` pin example, retarget Cursor Single-Tool setup to `.mdc` rules (`CURSOR_template.md`).

## [1.4.1] - 2026-06-30

### Changed

- Trimmed every skill `description` ~10-20% (kept match keywords) to shrink the recurring `_index.md` cost agents load per task.
- `build-index.sh`: replaced the per-line `sed -n Np` table-end scan (O(n²) subprocess spawns) with a single `awk` pass. Output byte-identical; trailing prose still preserved.

## [1.4.0] - 2026-06-30

### Changed

- **`caveman/deploy.sh` v1.1.0 — added `codex` and `continue` targets** alongside `cursor`/`claude`:
  - **`codex`** — symlinks the trio into `~/.codex/skills/` (override `CODEX_SKILLS_DIR`); `--always-on` appends a marker block to the global `~/.codex/AGENTS.md` (override `CODEX_AGENTS_FILE`).
  - **`continue`** — rules-only (Continue has no `SKILL.md` discovery): writes `~/.continue/rules/caveman.md` (override `CONTINUE_RULES_DIR`) with `alwaysApply: true` under `--always-on`, else `alwaysApply: false` (pulled in by description). `--copy` is a no-op here.
  - Fixed `--level` warning gating and a `CONTINUE_RULES_DIR` override that was being pre-cleared.
- **`skill-conflicts` v1.1.0** — scanner now also checks `~/.codex/skills/` and `~/.codex/prompts/` (`/name` collisions). Continue is rules-only and intentionally not scanned. New env overrides `CODEX_SKILLS_DIR`, `CODEX_PROMPTS_DIR`.

## [1.3.0] - 2026-06-30

### Added

- **`skill-conflicts` skill v1.0.0 + `.skills/_harness/skill-conflicts.sh`.** Detects collisions between repo-managed skills (`.skills/_skills/<name>`) and same-named skills or slash-commands in the user's IDE config (`~/.cursor/skills`, `~/.claude/skills`, `~/.cursor/commands`, `~/.claude/commands`; overridable via env). Classifies each hit: symlink-into-repo → OK (managed), identical independent copy → WARN (drift risk), divergent definition or command/skill name clash → CONFLICT (exit 1). Read-only; never mutates user config.

### Changed

- **Renamed the two install shapes from "Path A / Path B" to function-based names:** **Single-Tool** (Single-Tool Harness — installs one tool's runtime harness in the repo) and **Tool-Neutral** (Tool-Neutral Skills — portable skills only, no tool harness committed). Updated `AGENTS_skills.md` (headings keep a "formerly Path A/B" alias), the canonical Rules bullet in `_rules.md` and all 10 `*_template.md` files (kept in sync), `README.md` (new "Install shapes: Single-Tool vs Tool-Neutral" section with comparison table), **`skill-author` v1.5.4**, **`harness-subtree` v1.5.3**, and **`harness-upgrade` v1.1.2**.

## [1.2.0] - 2026-06-30

### Added

- **Caveman skill trio (bundled).** New kit-bundled skills vendored from [JuliusBrussee/caveman](https://github.com/JuliusBrussee/caveman) (MIT, prompt content only — no upstream installer, hooks, npm, or statusline machinery):
  - **`caveman` v1.0.0** — ultra-compressed communication mode (~75% output-token reduction) with `lite` / `full` / `ultra` / `wenyan-lite` / `wenyan-full` / `wenyan-ultra` intensity levels and built-in Auto-Clarity for security/destructive/ambiguous cases.
  - **`caveman-commit` v1.0.0** — terse Conventional Commits messages (subject ≤50 chars, why over what).
  - **`caveman-review` v1.0.0** — one-line PR review comments with optional severity prefixes.
- **`caveman/deploy.sh`** — zero-dependency helper to deploy the trio to an IDE config location (`cursor` → `~/.cursor/skills/`, `claude` → `~/.claude/skills/`) via symlink or `--copy`. `--always-on` writes the config-level activation the IDE injects each turn (Cursor per-project `.cursor/rules/caveman.mdc`; Claude Code global `~/.claude/CLAUDE.md`), mirroring caveman's own `caveman-activate.md` rule body. Supports `--level`, `--uninstall [DIR]`, and `--dry-run`.

### Fixed

- **`check.sh` — consumer-skill directory symlink topology** is now diagnosable when the kit is subtree-vendored or `consumer_skills_dir` is declared ([#5](https://github.com/Gargoyle-Apps/skills-harness/issues/5)).

## [1.1.2] - 2026-05-18

### Added

- **`check.sh` — native discovery completeness.** When `.agents/skills/` or `.claude/skills/` exist, validates that every harness skill under `_skills/` has a symlink with the correct relative target; reports missing, wrong-target, and dangling symlinks.
- **`check.sh --link` / `SKILLS_AUTO_LINK=1`:** runs `link.sh` on each existing native discovery directory (idempotent), then validates. Does not create native dirs that were never set up.

### Changed

- **`harness-subtree` v1.5.2** — migration validate step documents `check.sh --link` as an alternative to manual `link.sh`.
- **`harness-upgrade` v1.1.1** — documents `check.sh --link` / completeness validation in the 0.4.0 changes table.
- **`skill-author` v1.5.3** — step 8 mentions `check.sh --link` for syncing native discovery dirs.

### Fixed

- **Kit semver matches release tags.** `kit_version`, CHANGELOG, README, and `AGENTS_skills.md` now align with git tag **`v1.1.2`**. Earlier **`v1.1.1`** / **`v1.1.2`** tags pointed at the 1.0.1 tree without matching `_meta.yml`; **`v1.1.2`** now points at this release. Prefer **`v1.1.2`** over **`v1.0.2`** (short-lived tag on the same commit before renumbering).

## [1.0.1] - 2026-05-02

Discoverability fix for [issue #4](https://github.com/Gargoyle-Apps/skills-harness/issues/4): legacy manual installs whose `.skills/_meta.yml` `repo_url` points at an old fork (e.g. `gotalab/skills-harness`, which now 404s) hit the canonical-URL guard during migration, and the previous error didn't make clear that **`--remote-url https://github.com/Gargoyle-Apps/skills-harness`** is the **normal** fix when adopting the official upstream — not an exotic override.

### Changed

- **`migrate-to-subtree.sh` — clearer canonical-URL error.** The refusal message now (a) frames the situation as the **expected** legacy-install path, (b) shows the full canonical-upstream invocation including `--reconcile --symlink-consumer-skills`, (c) notes that `--reconcile` will rewrite `_meta.yml` to the canonical `repo_url`/`kit_version` after apply (so no manual edit is needed), and (d) explicitly warns that `--accept-derived-url` is **unsafe** when the listed URL is dead or stale and should only be used for deliberately maintained private forks.
- **`harness-subtree` v1.5.1** — "Stale `repo_url` in `.skills/_meta.yml`" section rewritten with the canonical-upstream command block, the `--reconcile` rewrite guarantee, and the same `--accept-derived-url` safety note.

## [1.0.0] - 2026-05-02

First **stable** kit release for multi-repo deployment. Intended behaviour matches **0.6.1**; the major version marks production readiness of the subtree workflow (`migrate-to-subtree.sh`, `--skip-subtree`, `--reconcile`, `--symlink-consumer-skills`), optional `prefixes:` / `consumer_skills_dir:` in `.skills/_meta.yml`, symlink-safe `check.sh`, consumer/kit role autodetection, and the upgrade/migration skills — after validation beyond the initial test consumers.

### Changed

- **Pinning examples** in **README** and **harness-subtree** now cite `v1.0.1` for reproducible curl/bootstrap and subtree pulls.
- **`harness-subtree` v1.5.0** — frontmatter bump; bootstrap/curl examples aligned with the `v1.0.1` tag.
- **`skill-author` v1.5.2** — example `_meta.yml` snippet: `kit_version` set to `1.0.0`.

## [0.6.1] - 2026-05-02

Closes the two follow-ups from [issue #3](https://github.com/Gargoyle-Apps/skills-harness/issues/3) (originally deferred from 0.6.0). Verified end-to-end against the same consumer (`Minecraft Minder`) that produced the original report; ImpureCrumpet flagged `--symlink-consumer-skills` as the single biggest UX win in the validation comment.

### Added

- **`migrate-to-subtree.sh --reconcile`** — automates the previously-manual post-`git subtree pull` reconcile. Drops every existing kit-skill row from `.skills/_index.md` and re-inserts upstream's rows for those names; bumps `kit_version` and `repo_url` in `.skills/_meta.yml` to match the subtree. Consumer rows, intro text, table comments, and other `_meta.yml` fields (`role`, `prefixes`, `consumer_skills_dir`, custom keys) are preserved verbatim. Idempotent — re-running prints `ok already matches` for both files. Dry-run by default; `--apply` writes.
- **`migrate-to-subtree.sh --symlink-consumer-skills`** — for repos that declare `consumer_skills_dir:` in `_meta.yml` (e.g. `.cursor/skills`), generates `.skills/_skills/<name> → ../../<consumer_skills_dir>/<name>` symlinks with correct relative depth. Skips entries without a `SKILL.md`, skips kit-skill name collisions, refuses to clobber pre-existing real directories (warns and skips). Idempotent. Eliminates the relative-depth foot-gun (`../../../` vs `../../`) flagged in the original report.
- **`migrate-to-subtree.sh --skip-subtree`** — companion flag for already-vendored installs: skips the subtree-add and kit-skill replacement steps so `--reconcile` and `--symlink-consumer-skills` can run in update-mode against an existing `.skills-harness/` tree without re-vendoring.
- **`harness-subtree` v1.4.0** — "Updating the vendored kit" section rewritten around the new single-command flow: `migrate-to-subtree.sh --skip-subtree --reconcile --symlink-consumer-skills --apply`. Notes section updated to mark both `consumer_skills_dir` auto-symlink and `_index.md`/`_meta.yml` reconcile as shipped (0.6.1+).

### Fixed

- **`migrate-to-subtree.sh` — `set -e` traps in helper functions.** New helpers (`reconcile_meta`, `reconcile_index`, `symlink_consumer_skills`) used bare `return` after conditional commands, which under `set -e` could propagate the conditional's exit status and abort the script mid-run. All bare `return`s in the new helpers now use explicit `return 0`. Same pattern applied as a defensive fix in pre-existing helpers.

## [0.6.0] - 2026-05-02

### Fixed

Real-world subtree-migration friction reported in [issue #3](https://github.com/Gargoyle-Apps/skills-harness/issues/3) (first-time migration of a stale 0.3.1 install). The fixes below close the critical and high-priority items from that report; `--reconcile` and auto-symlinking from `consumer_skills_dir` are deferred to a follow-up release.

- **`check.sh` — symlink-safe paths.** Path resolution now uses `${BASH_SOURCE[0]}` + `pwd -L` instead of `cd "$(dirname "$0")" && pwd`, so running `.skills/_harness/check.sh` after a subtree migration (where `.skills/_harness/` is a symlink into `.skills-harness/.skills/_harness/`) correctly resolves the consumer's `_skills/`/`_index.md`/repo root rather than the subtree's. Without this fix, every consumer-authored skill row in `_index.md` was reported as missing. Eliminates the wrapper-script workaround.
- **`check.sh` — auto consumer/kit role detection.** The kit-surface assertions (CHANGELOG/README/AGENTS_skills.md kit-version markers) are now skipped automatically when either `.skills-harness/` exists at the repo root or `.skills/_meta.yml` declares `role: consumer`. `SKILLS_CHECK_KIT_SURFACES` env var still wins when set explicitly. Documented in README's Validation section and CONTRIBUTING's Environment overrides table.
- **`migrate-to-subtree.sh` — dirty-tree check ignores self + `*.bak/`.** The dirty-tree precondition now filters out the script's own untracked path and any `*.bak/` directories, so dropping the script directly into `.skills/_harness/migrate-to-subtree.sh` and running from there with `--apply` works without moving it to `/tmp` first.
- **`migrate-to-subtree.sh` — stale `repo_url` safety.** When the upstream URL is derived from `.skills/_meta.yml` (no `--remote-url`) and doesn't match `Gargoyle-Apps/skills-harness`, the script now refuses to proceed and explains how to override (`--remote-url <canonical>` or `--accept-derived-url`). Stale installs that pointed at archived forks (e.g. `gotalab/skills-harness`) would previously vendor the wrong project silently.
- **`migrate-to-subtree.sh` — `--accept-upstream <name>[,<name>…]`.** New per-skill flag for accepting upstream on selected drifted kit skills, instead of `--force`'s sledgehammer that overwrites every drifted skill at once.
- **`migrate-to-subtree.sh` — prefix derivation also splits on whitespace.** A repo dir name like `Media Library` now correctly derives `ml-` instead of `m-`. The split collapses runs of `-`, `_`, and whitespace.
- **`migrate-to-subtree.sh` — surfaces `consumer_skills_dir:` from `_meta.yml`.** When declared (e.g. for Cursor-style repos that keep real bodies under `.cursor/skills/`), the audit prints a reminder that `.skills/_skills/<name>/` symlink shims must be created manually. Auto-symlinking is planned but not yet implemented.

### Added

- **`skill-author` v1.5.1 — explicit single-prefix override + whitespace split.** Derivation now documents whitespace as a separator (matching the script). Also documents the `prefixes: [single-prefix-]` pattern as the recommended way to override the auto-derived prefix on single-family repos where the heuristic gives the wrong answer.
- **`_meta.yml` schema (optional fields):** `role: consumer|kit`, `consumer_skills_dir: <path>`, `prefixes: [...]`. All three are read by the kit (`role` by `check.sh`, the others by `migrate-to-subtree.sh` and `skill-author`); none are required.
- **`skill-author` v1.5.0 — multi-prefix repos:** new "Multiple prefixes (per-repo override)" section. Consumer repos that host distinct skill families can declare an explicit `prefixes:` list in `.skills/_meta.yml` (e.g. `[bld-, bin-]`); when present, every consumer-authored skill must start with one of those prefixes and the auto-derived single prefix is bypassed. Absent the list, the existing single-derived-prefix rule applies. Kit-bundled skills stay unprefixed in both modes. The same convention is mirrored in `AGENTS_skills.md` so consumers see it during bootstrap.
- **`migrate-to-subtree.sh` — multi-prefix audit:** the prefix audit now reads `prefixes:` from `.skills/_meta.yml` (minimal block-style YAML parser, bash 3.2-safe) and accepts any declared prefix. Violation messages list the full allowed set so the user can pick the right family for each skill. Falls back to the single auto-derived prefix when no list is declared.
- **`migrate-to-subtree.sh`:** new helper script under `.skills/_harness/` that migrates a manual file-copy install to a subtree-vendored install **non-destructively**. Dry-run by default; `--apply` performs the actions. Adds the subtree at `.skills-harness/`, backs up `.skills/_harness/` and each kit-bundled skill to `*.bak/` and replaces them with symlinks into the subtree, and **never touches consumer-authored skills, `.skills/_index.md`, or `.skills/_meta.yml`**. Drifted kit skills are kept (the script prints `diff` commands); `--force --apply` accepts upstream after review. Audits consumer skills against the **skill-author** prefix convention (derives expected prefix from the repo's directory name and reports renames) and against the five required frontmatter fields; both audits are warn-only — renames stay manual because the index, frontmatter `name`, and `dependencies` references must move together.
- **`harness-subtree` skill (v1.3.0):** documents installing, updating, and **migrating to** the kit in a consumer repo as a `git subtree` at `.skills-harness/`, with a symlinked `.skills/` shell so kit-managed pieces stay overwritable while consumer-authored skills, the index, and `_meta.yml` remain independent. Covers initial install, `git subtree pull` updates, post-pull symlink/index reconcile, version pinning, and gotchas. Includes a 10-step **Migrating an existing manual install to subtree** workflow that leans on `migrate-to-subtree.sh` for the safe parts and walks through audit, drift handling, prefix/frontmatter cleanup, apply, backup inspection, index reconcile, native-discovery re-link, and validation. Issue #3 follow-ups land here too: curl-bootstrap line for stale installs, stale-`repo_url` safety, `--accept-upstream` vs `--force`, the symlink-safe `check.sh` (no wrapper needed), consumer/kit auto-detect, optional `consumer_skills_dir:` schema, and explicit call-outs for the deferred `--reconcile` and auto-symlinking follow-ups. Triggers include *migrate manual install to subtree* and *convert harness install to subtree*.
- **`README.md`:** new **Migrating an existing manual install** subsection under Deploying as a git subtree pointing at the helper script and the skill.
- **`README.md`:** new top-level **Deploying as a git subtree** section with layout diagram, install commands, update commands, pinning notes, and a "Why versioning matters more under subtree" subsection that ties consumer pulls to the per-skill `version` and `CHANGELOG` contract.
- **`AGENTS_skills.md`:** new **How this repo got the kit** section so agents detect manual-copy vs. subtree installs (presence of `.skills-harness/`) and route to **harness-upgrade** vs. **harness-subtree** accordingly.
- **`_rules.md` (and all `*_template.md` via `sync.sh`):** new bullet declaring that `.skills-harness/` is upstream-owned in subtree installs and pointing at **harness-subtree** for any reconcile work.

### Changed

- **`kit-release` v1.1.0:** new Notes bullets emphasizing that subtree consumers diff against `CHANGELOG.md` and per-skill `version` bumps on every `git subtree pull`, plus optional tagging guidance for consumers who pin to a release tag.
- **`harness-upgrade` v1.1.0:** "When to use" now defers to **harness-subtree** when `.skills-harness/` is present, so subtree-vendored repos don't follow the file-copy migration path.

## [0.5.2] - 2026-04-29

### Added

- **`skill-author` v1.4.0:** new "Naming convention" section. Skills authored in **consumer repos** must be prefixed with the repo's initials (split repo dir name on `-`/`_`, take first letter of each segment, lowercased, append `-`; e.g. `ux-package-management` → `uxpm-`, `git-minder` → `gm-`, `warehouse` → `w-`). The kit itself (`skills-harness`) deliberately stays unprefixed to avoid collisions with consumer repos that share initials (e.g. `so-high`).
- **`AGENTS_skills.md`:** new "Skill naming in consumer repos" section above the hard gate so consumers see the convention during bootstrap.
- **`CONTRIBUTING.md`:** callout in "Adding or editing a skill" clarifying that kit skills (added to this repo) stay unprefixed.

## [0.5.1] - 2026-04-16

### Changed

- **`README.md`:** "Skill format" table column changed from "Required" (all yes) to "Required by" (agentskills.io + harness vs harness only), matching the CONTRIBUTING.md style.
- **`AGENTS_skills.md`:** added upstream maintainer HTML comment explaining why the file remains in the canonical repo. Collapsed Path A template table into a pointer to the README "Supported tools" table; added Roo Code and OpenCode to the Path A environment list.

## [0.5.0] - 2026-04-16

### Added

- **`sync.sh`:** new script regenerates the Rules block in all `*_template.md` files from `_rules.md`. Dry-run by default; `sync.sh --write` performs edits. Replaces the manual copy-paste step in CONTRIBUTING.md.
- **`build-index.sh`:** new script regenerates `_index.md` table rows from SKILL.md frontmatter. Dry-run by default; `build-index.sh --write` performs edits. Frontmatter is now the author-time source of truth for index content.

### Changed

- **`CONTRIBUTING.md`:** "Changing the Rules block" step 2 now references `sync.sh --write`; "Adding or editing a skill" step 3 now references `build-index.sh --write`.
- **`skill-author` v1.3.0:** step 6 updated to run `build-index.sh --write` instead of manually adding an index row.
- **`_index.md`:** table rows regenerated from frontmatter (richer descriptions and full trigger lists).

## [0.4.2] - 2026-04-16

### Added

- **`check.sh --quiet`:** suppresses success footer for clean CI/hook output.
- **`SKILLS_CHECK_KIT_SURFACES=0`:** env var to skip README and `AGENTS_skills.md` version assertions (for downstream kits with custom surfaces).
- **Env-var overrides:** `check.sh` and `link.sh` accept `SKILLS_HARNESS_DIR`, `SKILLS_DIR`, `SKILLS_REPO_ROOT` (plus `SKILLS_INDEX`, `SKILLS_RULES` for check) to support non-standard repo layouts without forking scripts.
- **`link.sh` dangling-symlink pruning:** re-running `link.sh` without `--clean` now auto-removes broken symlinks left by deleted or renamed skills.

### Changed

- **`CONTRIBUTING.md`:** new "Environment overrides" section documenting env vars and `--quiet`.

## [0.4.1] - 2026-04-12

### Added

- **`kit-release` skill (v1.0.0):** procedure to bump kit semver while keeping `CHANGELOG.md`, `.skills/_meta.yml`, `README.md`, and `AGENTS_skills.md` aligned; validated by `check.sh`.

### Changed

- **`README.md`**, **`AGENTS_skills.md`:** surface **Current release** / **Kit version** matching the changelog and `_meta.yml`.
- **`check.sh`:** verifies kit version consistency across `_meta.yml`, top `CHANGELOG` release, `README`, and `AGENTS_skills.md`.
- **`CONTRIBUTING.md`:** versioning section references **kit-release** and the shared surfaces.

## [0.4.0] - 2026-04-07

### Added

- **`link.sh`:** symlink helper script that creates symlinks from native IDE discovery paths (`.agents/skills/`, `.claude/skills/`) into `.skills/_skills/`, enabling auto-invocation, `@skill-name` mentions, and skill panels across 9 IDEs.
- **`ROO_template.md`:** Roo Code environment template.
- **`OPENCODE_template.md`:** OpenCode environment template.
- **`harness-upgrade` skill (v1.0.0):** guides upgrading older harness installations to v0.4.0+ with native IDE discovery; includes IDE swap instructions.
- **`.gitignore`:** `.agents/skills/` and `.claude/skills/` entries for generated symlink directories.

### Changed

- **All templates:** SETUP sections now include a "Native discovery" step calling `link.sh` with the IDE-appropriate target directory.
- **`check.sh`:** added optional symlink validation for `.agents/skills/` and `.claude/skills/` directories.
- **`skill-template` v1.1.0:** added [agentskills.io](https://agentskills.io/specification) frontmatter constraints (`name` length/format, `description` length) to authoring instructions.
- **`skill-author` v1.2.0:** added step to re-run `link.sh` after creating a new skill.
- **`link.sh`:** stale symlink detection (auto-updates wrong targets), `_`-prefixed directory filter, flexible `--clean` arg position.
- **`AGENTS_skills.md`:** bootstrap table now includes Roo Code and OpenCode rows.
- **`README.md`:** added native IDE discovery section with `link.sh` usage and IDE swap guide; updated supported tools table.
- **`CONTRIBUTING.md`:** added frontmatter compatibility requirements and symlink helper guidance.

## [0.3.2] - 2026-04-04

### Changed

- **Rules:** replaced "Add new skills to the index when you create them" with a stronger obligation — `.skills/_index.md` is the source of truth; agents must update it on create, rename, or delete, and never leave it out of sync.
- **`skill-author` v1.1.0:** added "Renaming or deleting a skill" section reinforcing index sync on all lifecycle operations.
- **Index:** removed stale `ghost` placeholder row.

## [0.3.1] - 2026-04-03

### Fixed

- **`check.sh`:** `err()` no longer aborts on the first failure under `set -e` (use pre-increment for the error counter). Replaced bash 4 associative arrays with a portable marker string so the script runs on macOS `/bin/bash` 3.2.

## [0.3.0] - 2026-04-03

### Added

- **`_rules.md`:** canonical Rules block as a single source of truth under `.skills/_harness/`. All templates embed a copy; `_rules.md` is the maintainer reference.
- **`check.sh`:** validation script that verifies index-to-directory consistency, frontmatter completeness, `name` field matching, and Rules block sync across all templates.
- **`CONTRIBUTING.md`:** contributor guidance covering Rules changes, new templates, skill authoring, testing, and versioning.
- **`_meta.yml` `repo_url`:** added `repo_url` so embedded kits can trace their origin.

### Changed

- **Split `AGENTS_template.md`** into three separate files: `CURSOR_template.md`, `CODEX_template.md`, `COPILOT_template.md`. Each template is self-contained — no more stripping unused environment blocks.
- **Standardized merge guidance:** all templates now use "append under a `## Skills Harness` heading" as the default merge strategy instead of listing multiple options.
- **Template SETUP blocks:** each now ends with a **Verify** checklist for post-setup confirmation.
- **Bootstrap table (`AGENTS_skills.md`):** updated to reference the new split template filenames.
- **README:** updated supported tools table for split templates; added **Validation** and **Contributing** sections.
- **`ref/skills-harness-plan.md`:** updated to reflect current state — `AGENTS_skills.md` naming, split templates, `_rules.md`, `check.sh`, corrected frontmatter examples, and marked as historical design reference.

### Removed

- **`AGENTS_template.md`:** replaced by `CURSOR_template.md`, `CODEX_template.md`, `COPILOT_template.md`.
- **`.gitignore` `!.env.example`:** removed stale exception for a file that does not exist.

## [0.2.2] - 2026-04-02

### Changed

- **Path B (`AGENTS_skills.md`):** Clarify no harness-template paste into `AGENTS.md`; existing `AGENTS.md` stays the project contract; optional **Skills (agnostic)** section example; `_harness/` is reference-only for Path B.
- **`skill-author`:** Prerequisites no longer imply a permanent dependency on `AGENTS_skills.md`; after bootstrap removal, check root **`AGENTS.md`** / README for Path B policy.
- **Harness templates:** Rules bullet rewritten so the bootstrap gate applies **only while** `AGENTS_skills.md` exists; Path B may record policy in `AGENTS.md`.

## [0.2.1] - 2026-04-02

### Added

- **`AGENTS_skills.md` Path B — agnostic / multi-ecosystem:** author portable skills under `.skills/` without installing a tool-specific harness in the repo; document in README/CONTRIBUTING and remove bootstrap.
- **README:** subsection for agnostic repositories and downstream harness usage.

### Changed

- **`skill-author` prerequisites:** allow completion via Path A or Path B (`AGENTS_skills.md`).

## [0.2.0] - 2026-04-02

### Changed

- **Bootstrap renamed to `AGENTS_skills.md`** so it does not overwrite an existing project `AGENTS.md`. It is removed after setup.
- **AGENTS-based harness:** templates now require **merging** into existing `AGENTS.md` when that file already exists; sidecar templates merge pointers into `AGENTS.md` the same way.
- **`AGENTS_skills.md` gate:** explicit rules that the user must **declare the environment** before any skill creation, refactor, or index registration; runtime harness rules repeat this while the bootstrap file is present.
- **skill-author:** prerequisites section pointing at the bootstrap gate.

## [0.1.0] - 2026-04-02

### Added

- Bootstrap `AGENTS.md` and `.skills/` layout: index, bundled skills (`skill-template`, `skill-author`), and environment templates under `.skills/_harness/`.
- Human-facing `README` with quick start, supported tools, and optional MCP pointer.
