# skills-harness

A zero-dependency, file-only kit that teaches coding agents how to discover and load skills on demand. Drop `.skills/` and `AGENTS_skills.md` into any repo — the agent sets itself up, routes from native skill metadata when available, and loads each matching `SKILL.md` only on demand.

## Quick start

1. Copy `AGENTS_skills.md` and `.skills/` into your project root.
2. Open `AGENTS_skills.md` in your agent. It will ask which environment you use, then walk through setup automatically.
3. After setup, `AGENTS_skills.md` is deleted. The harness lives in `AGENTS.md` or a sidecar file, depending on your IDE.

For repos that need to stay tool-neutral (used across Cursor, Claude Code, Windsurf, etc. by different people), follow the **Tool-Neutral** setup in `AGENTS_skills.md` — skills stay portable under `.skills/` without committing to a single tool's config files.

## How it works

| Role | What it does | Implemented by |
|------|-------------|----------------|
| **User** | Sets goals, chooses the IDE, resolves conflicts | The human |
| **Agent** | Routes from native metadata, loads skills on demand, manages files | The AI in your IDE |
| **Index** | Fallback catalog for targeted lookup, ambiguous routing, and maintenance | `.skills/_index.md` |
| **Skills** | Execute — step-by-step instructions for a specific task | `.skills/_skills/<name>/SKILL.md` |

Native hosts receive each skill's `name` and `description` and use that compact catalog for routing. The full index is consulted only when native discovery is unavailable, a match is ambiguous or missing, the host reports omitted skills, or the catalog itself is being maintained. Once a skill is selected, only its unconditional `dependencies` load immediately; branch-specific companions load at their documented decision point. Skills cannot override user intent or agent core behavior; they only provide domain-specific procedures.

Each description must stand on its own: what the skill does, when to use it, and relevant exclusions. Harness-only `triggers` and human-authored routing notes supplement that text; they must not be the sole source of a routing distinction. Prefix families describe deployment and ownership, not a mandatory family-first routing tier. Skill frontmatter is authoritative for generated catalog rows.

## DESIGN.md integration

Repos with a visual design system can add [DESIGN.md](https://github.com/google-labs-code/design.md) (Google Labs) alongside the harness. Each layer owns one job:

| Layer | Location | When loaded | Owns |
|-------|----------|-------------|------|
| **Harness** | `.skills/_index.md` + skills | On trigger match | Multi-step workflows |
| **AGENTS.md** | Repo root (or tool sidecar) | Every session | Project policy and *pointers* to skills and `DESIGN.md` |
| **DESIGN.md** | Repo root (default) | UI / visual work | Design tokens (YAML) + design rationale (markdown) |

Point `AGENTS.md` at `DESIGN.md` for UI work; keep design tokens in `DESIGN.md` YAML front matter, not in `AGENTS.md` or skill files. Validate with `npx -y -p @google/design.md designmd lint DESIGN.md`.

Load **skill-reviewer** for a direct review of specific skills or a bounded skill-specific pass within authoring or repository review. General code/PR reviews, including `/review` and `/codereview`, retain the host's full scope and output format; skill findings feed into that review. **caveman-review** supplies terse wording only when requested. **skill-author** covers creating skills; **skill-catalog-maintainer** audits the catalog; **skill-import** / **skill-export** handle cross-repo vendoring.

## Install shapes: Single-Tool vs Tool-Neutral

When you install the harness into a repo, bootstrap (`AGENTS_skills.md`) forces a one-time choice between two shapes. They are named by **function** (the older "Path A / Path B" labels map directly). They differ in exactly **one** thing: whether *this* repo commits to a single tool's runtime harness files.

| | **Single-Tool** (Single-Tool Harness) | **Tool-Neutral** (Tool-Neutral Skills) |
|---|---|---|
| Formerly | Path A | Path B |
| Use when | Everyone working in this repo uses the same tool (always Cursor, or always Claude Code, …) | The repo is opened across different tools and must stay neutral |
| What gets installed | That tool's harness template (from `.skills/_harness/*_template.md`) is written into `AGENTS.md` / tool config | **Nothing tool-specific** — only a short policy note in `AGENTS.md` / README / CONTRIBUTING |
| `.skills/_harness/*_template.md` | The source you install from | **Reference only** — for other checkouts/consumers who run Single-Tool themselves |
| Skills + `.skills/_index.md` | Portable | Portable (identical) |
| Runtime skill loading | Installed tool harness **plus** native discovery | Native discovery + the index (no committed tool harness) |
| Net result | Repo is wired to one tool | Repo stays tool-agnostic |

**Quick decision:** one tool for everyone → **Single-Tool**. Mixed tools / must stay neutral → **Tool-Neutral**. Both keep skills portable under `.skills/_skills/` with the same `_index.md`; the only commitment Single-Tool makes that Tool-Neutral avoids is writing a specific tool's harness block into this repo.

**This repo (`skills-harness` upstream) is a special third case:** it is the *source* of those templates, so it never installs one into itself and never deletes `AGENTS_skills.md`. Agents here route through native discovery (`.agents/skills/` is declared in `_meta.yml`; local `.claude/skills/` may also exist) and use `.skills/_index.md` as a targeted fallback — effectively Tool-Neutral in spirit, with the maintainer exception that the bootstrap file stays.

## Supported tools

| Environment | Template |
|-------------|----------|
| Cursor | [CURSOR_template.md](.skills/_harness/CURSOR_template.md) |
| Codex | [CODEX_template.md](.skills/_harness/CODEX_template.md) |
| GitHub Copilot | [COPILOT_template.md](.skills/_harness/COPILOT_template.md) |
| Claude Code | [CLAUDE_template.md](.skills/_harness/CLAUDE_template.md) |
| Cline | [CLINE_template.md](.skills/_harness/CLINE_template.md) |
| Windsurf | [WINDSURF_template.md](.skills/_harness/WINDSURF_template.md) |
| Gemini CLI | [GEMINI_template.md](.skills/_harness/GEMINI_template.md) |
| Roo Code | [ROO_template.md](.skills/_harness/ROO_template.md) |
| OpenCode | [OPENCODE_template.md](.skills/_harness/OPENCODE_template.md) |
| Other / paste-only | [GENERIC_template.md](.skills/_harness/GENERIC_template.md) |

## Skill format

Each `SKILL.md` opens with YAML frontmatter. See [skill-template](.skills/_skills/skill-template/SKILL.md) for a complete example.

| Field | Required by | Purpose |
|-------|-------------|---------|
| `name` | agentskills.io + harness | Must match directory name (kebab-case, 1–64 chars) |
| `description` | agentskills.io + harness | One sentence for index and IDE matching (1–1024 chars) |
| `triggers` | harness only | Phrases that should cause this skill to load |
| `dependencies` | harness only | Unconditional prerequisite skill names (`[]` if none) |
| `version` | harness only | Semver string (e.g. `1.0.0`) |
| `compatibility` | optional Agent Skills field | Specific environment requirements, 1–500 characters when present |
| `metadata` | optional Agent Skills field | String-to-string annotations, such as `family`; not a routing gate |

`name` and `description` follow the [agentskills.io specification](https://agentskills.io/specification) and are used by IDEs with native skill discovery. The harness adds `triggers`, `dependencies`, and `version`; IDEs that don't recognize them silently ignore them. See [`.skills/_index.md`](.skills/_index.md) for bundled skills.

Optional `compatibility` and `metadata` stay in skill frontmatter and are validated when present. Keep selection-critical requirements in `description` too; optional field support varies by host. The kit supports single-line strings and flat block/flow string maps; see [skill-template](.skills/_skills/skill-template/SKILL.md#optional-portability-fields) for examples and supported YAML forms.

### Writing skill prose

Use lite, direct agent prose: remove filler and hedging, but keep short, complete sentences. Keep `description` and `triggers` in natural user language because they carry routing. Preserve explicit actors, conjunctions, step order, confirmation gates, and safety language whenever compression could make them ambiguous; do not substitute invented abbreviations or arrows for causality in those instructions.

For size pressure, prune conditional dependencies, remove duplication, and move optional bulk to explicitly gated `references/`. Keep common-path decisions and safety gates in `SKILL.md`. Never bulk-rewrite a catalog into ultra-caveman prose merely to satisfy a size warning.

### Generated catalog layouts

The default remains one generated table in `.skills/_index.md`. For catalogs with measured fallback-lookup pressure, an optional split layout generates a small root directory of links and one child index per declared prefix, plus an explicit fallback group for kit and unmatched skills. Keep cross-family routing notes in the root; agents can follow only the relevant child link. Splitting does not reduce native description cost or require family-first native routing.

Read [the index layout contract](.skills/_harness/index-layout.md) before configuring a split. Run `.skills/_harness/build-index.sh --dry-run` to inspect file and row changes, then `--write` for an approved migration. Reconciliation uses the same installed frontmatter and generator, and `check.sh` checks every configured generated index. Legacy multi-table layouts are diagnosed; consolidate them explicitly while preserving consumer prose before generating.

## Native IDE discovery

Most IDEs auto-discover skills from standard directories. After setup, run the symlink helper to enable native features (`@skill-name` mentions, auto-invocation, skill panels):

```bash
# Most IDEs (Cursor, Codex, Copilot, Windsurf, Gemini CLI, Roo Code, OpenCode)
.skills/_harness/link.sh .agents/skills

# Claude Code and Cline
.skills/_harness/link.sh .claude/skills
```

Symlinks point from the cross-agent discovery path back to `.skills/_skills/`. `link.sh` also records the chosen path under `native_targets:` in `.skills/_meta.yml`; pass `--no-record` only for a deliberately temporary surface. Add the generated target directory to `.gitignore` — symlinks are machine-local, but the declaration is committed.

Native discovery is the primary router. The harness index remains the portable human catalog and targeted fallback for non-native, ambiguous, omitted-skill, and catalog-maintenance cases.

```yaml
native_targets:
  - .agents/skills
```

A plain `check.sh` distinguishes an undeclared install from a declared target that is missing or unhealthy. `check.sh --link` creates and repairs every declared target. Avoid declaring both `.agents/skills` and `.cursor/skills` for the same catalog because Cursor scans both and may expose duplicate names.

### Swapping IDEs

Skills stay in `.skills/_skills/` regardless of IDE. To switch:

1. Follow the new IDE's template to install harness rules.
2. Run `link.sh` with the appropriate target if not already done.
3. `.agents/skills/` and `.claude/skills/` symlinks can coexist.

For upgrading from an older harness version, use the bundled **harness-upgrade** skill.

## Adding a skill

1. Copy [skill-template](.skills/_skills/skill-template/SKILL.md) to `.skills/_skills/<name>/SKILL.md` and edit.
2. Run `.skills/_harness/build-index.sh --write` to regenerate catalog rows from skill frontmatter.
3. Run `.skills/_harness/check.sh --link` to refresh every declared native target.
4. For the full checklist, load the **skill-author** skill.

## Updating the kit

Merge or replace `.skills/_harness/` and bundled skills from upstream. Keep your custom skills under `.skills/_skills/` and your index rows. See the **harness-upgrade** skill for guided migration.

For repos that vendor the entire kit via `git subtree pull` (see **Deploying as a git subtree** below), updates are a single command and the **harness-subtree** skill walks through the post-pull reconcile.

## Deploying as a git subtree

Manual file-copy installs work, but `git subtree` is the recommended way to vendor `skills-harness` into a consumer repo when you want **traceable, single-command updates** and **no submodule fragility**. The full procedure (and post-pull reconcile) is documented in the bundled **harness-subtree** skill — load it with a phrase like *"vendor skills-harness as a subtree"*. The summary:

### Layout

The kit is vendored as-is into `.skills-harness/`. The consumer's runtime tree under `.skills/` stays in place and uses **symlinks** to point its kit-managed pieces at the vendored copy:

```text
<consumer-repo>/
├── .skills-harness/        ← vendored kit (subtree; do not hand-edit)
│   └── .skills/{_harness,_skills,_index.md,_meta.yml}
├── .skills/
│   ├── _harness            → symlink → ../.skills-harness/.skills/_harness
│   ├── _skills/
│   │   ├── <kit-skill>     → symlinks → ../../.skills-harness/.skills/_skills/<name>
│   │   └── <prefix>-<own>/ → symlink to consumer_skills_dir when declared; else real dir
│   ├── _index.md           ← consumer-owned (kit rows + own rows)
│   └── _meta.yml           ← consumer-owned, mirrors vendored kit_version
└── AGENTS.md               ← Single-Tool harness or Tool-Neutral policy
```

This keeps the kit pieces overwritable on every pull while consumer-authored skills, the index, and the local `_meta.yml` stay independent.

### One-time install

```bash
git remote add skills-harness https://github.com/Gargoyle-Apps/skills-harness
git fetch skills-harness
git subtree add --prefix=.skills-harness skills-harness main --squash
```

Then create the symlinked `.skills/` shell, copy `.skills-harness/AGENTS_skills.md` to repo root, complete bootstrap (Single-Tool or Tool-Neutral), delete the bootstrap file, and run `.skills/_harness/check.sh --link`. The **harness-subtree** skill has the exact commands.

### Updating

```bash
git fetch skills-harness
git subtree pull --prefix=.skills-harness skills-harness main --squash
```

Read `.skills-harness/CHANGELOG.md` for the diff, refresh kit-skill symlinks, reconcile new rows and metadata, sync declared native targets, and re-run `check.sh`. The **harness-subtree** migration helper performs these steps idempotently.

### Migrating an existing manual install

If a repo already has `.skills/` from a file-copy install and you want to switch to subtree updates, run `.skills/_harness/migrate-to-subtree.sh` (dry-run by default; `--apply` to perform). It vendors the subtree, replaces kit-owned pieces with symlinks, and never touches consumer-authored skills. The index changes only under `--reconcile`; `_meta.yml` changes under `--reconcile` or when `--native-target` adds a declaration. It also audits consumer skills against the prefix convention (per **skill-author**) and required frontmatter fields, and prints rename/patch suggestions for you to apply manually.

Pass `--reconcile` (and optionally `--symlink-consumer-skills`) to fold the post-migration index/`_meta.yml` reconcile and consumer-skill shim creation into the same run. Existing `native_targets` are preserved and synced; `--native-target .agents/skills` selects one for a legacy install. Full procedure (including drift handling with `--accept-upstream <name>` or `--force`) lives in **harness-subtree**.

**Bootstrapping on a stale install** (pre-0.6.0 doesn't ship the script):

```bash
curl -sSLo .skills/_harness/migrate-to-subtree.sh \
  https://raw.githubusercontent.com/Gargoyle-Apps/skills-harness/main/.skills/_harness/migrate-to-subtree.sh
chmod +x .skills/_harness/migrate-to-subtree.sh
.skills/_harness/migrate-to-subtree.sh        # dry-run first
```

Swap `main` for a release tag (e.g. `v1.0.1`) for a reproducible install. The script ignores its own untracked status and any `*.bak/` directories during the dirty-tree check, so running it from `.skills/_harness/` is fine.

### Pinning

Pin to a specific kit release with `git subtree add/pull --prefix=.skills-harness skills-harness <tag-or-sha> --squash`. Kit tags follow the semver in **`.skills/_meta.yml`** and root **`CHANGELOG.md`** — which is exactly why the next two sections matter so much for subtree consumers.

### Why versioning matters more under subtree

Because the kit can be updated mid-project with a single command, **per-skill `version` fields and the kit `CHANGELOG.md` are the contract** between this repo and every vendored consumer:

- A bumped kit-bundled skill `version` signals consumers that behaviour they previously relied on may have changed.
- The kit-level semver in `.skills/_meta.yml` and the top entry in `CHANGELOG.md` are what consumers diff against their pinned version.
- `kit-release` (this repo) and `harness-subtree` / `harness-upgrade` (consumer side) are the two halves of that contract.

## Validation

Run `.skills/_harness/check.sh` to verify index/directory consistency, Agent Skills frontmatter shape, template sync, `_skills/` directory-symlink topology, and every declared native target. It also warns on missing/cyclic dependencies, large transitive dependency loads, native metadata budget, index growth, and oversized skill bodies. After adding kit skills or a subtree pull, run **`check.sh --link`** to create or sync all `native_targets`, then validate.

The kit-version surface checks (CHANGELOG/README/AGENTS_skills.md must agree on `kit_version`) only make sense in this upstream repo. **Consumer repos auto-skip them** when either `.skills-harness/` exists at the repo root (subtree install) or `.skills/_meta.yml` declares `role: consumer`. Override with `SKILLS_CHECK_KIT_SURFACES=1` (force checks) or `SKILLS_CHECK_KIT_SURFACES=0` (suppress) when the auto-detect gets it wrong. See [CONTRIBUTING.md — Environment overrides](CONTRIBUTING.md#environment-overrides) for the full list.

## Optional: MCP

For progressive skill loading via MCP, see [skillport](https://github.com/gotalab/skillport). This kit does not ship a server.

## Kit version

**Current release:** `1.7.0`

- **Canonical:** [`kit_version` in `.skills/_meta.yml`](.skills/_meta.yml)
- **History:** [CHANGELOG.md](CHANGELOG.md)
- **Bootstrap:** [`AGENTS_skills.md`](AGENTS_skills.md) shows the same release for agents during setup

When bumping the kit in this repository, load the **kit-release** skill and update the changelog, `_meta.yml`, this section, and `AGENTS_skills.md` together, then run `.skills/_harness/check.sh`. See [CONTRIBUTING.md — Versioning](CONTRIBUTING.md#versioning).

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

See [LICENSE](LICENSE).
