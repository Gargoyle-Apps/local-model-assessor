# Generated index layouts

`build-index.sh` generates every skill row from installed `.skills/_skills/*/SKILL.md` frontmatter, ordered by name in the C locale. Kit symlinks and consumer skills use the same rule. `description` and `triggers` are generated text; edit their source rather than a table cell. Optional `metadata.family` is descriptive and does not override prefix grouping.

## Default: one index

No configuration is required. `.skills/_index.md` contains one `| name | description | triggers |` table. Generation replaces that table and preserves surrounding prose. A legacy root with multiple skill tables is rejected before writes: consolidate its tables manually and retain family scope/disambiguation prose before generating. The tool never guesses which family headings or notes to discard.

## Optional split layout

Use this only when a targeted fallback lookup benefits from smaller child indexes. Native description-first discovery stays unchanged; splitting does not reduce aggregate native description cost.

```yaml
prefixes:
  - app-
  - ops-
index_layout: split
index_fallback: kit
```

Grouping is declared once in the existing `prefixes:` block list. `app-` maps to `.skills/_indexes/app.md`, and `ops-` to `.skills/_indexes/ops.md`. Prefixes must be lowercase alphanumeric/hyphen strings ending in one `-`, with no consecutive hyphens, and must be unique and nonoverlapping. The required `index_fallback` uses lowercase alphanumerics and interior single hyphens, and differs from prefix groups. It explicitly receives kit/unprefixed and all unmatched skills; no consumer prefix is hardcoded. A group with zero skills still has a child and a root link. Scalar identifiers may be plain or quoted; inline `#` comments require preceding whitespace. Split mode rejects malformed or inconsistently indented prefix entries. Single mode keeps existing ownership declarations without using them for grouping.

The root's sole skill table becomes a small directory of child links and counts. The fallback link comes first, followed by prefixes in declaration order. Keep cross-family scope and routing guidance around that directory so readers can select one child without reading all children. Root links are directory entries, not skill rows.

Run these commands to preview and apply a migration or update:

```bash
.skills/_harness/build-index.sh --dry-run
.skills/_harness/build-index.sh --write
.skills/_harness/check.sh
```

The default is also dry-run. It prints unified diffs identifying files and rows affected, writes nothing, and exits 1 on drift (0 when current, 2 on invalid configuration/ownership). All destinations are preflighted before any file is written.

## Ownership and preservation

The split root directory and each child table use these markers:

```markdown
<!-- BEGIN GENERATED SKILL INDEX -->
...generated links or table...
<!-- END GENERATED SKILL INDEX -->
```

Prose before/after markers is preserved. Place human-authored notes outside the markers. Existing unmarked child files are rejected, including empty files; archive or move them explicitly before adoption. Unexpected skill tables, unbalanced markers, generated children belonging to unknown groups, and symlink output destinations are rejected. Dangling child symlinks also require explicit removal or relocation because their ownership cannot be checked. Unrelated unowned files are left alone.

Renaming/removing a group or switching back to `index_layout: single` requires explicitly archiving/removing obsolete generated child files first; the generator does not delete files that may contain human notes. Preserve relevant scope guidance at the root. Single mode can reuse the existing root markers and replaces their contents with one table.

`check.sh` compares the complete configured output against frontmatter. This detects coverage gaps, duplicates, stale wording/order, rows in the wrong group, broken/missing generated links, and missing children. It checks generated root links; unrelated human-authored prose links are outside the index ownership contract.

## Subtree updates and authoring

After creating, changing, renaming, or removing a skill, run `build-index.sh --write` and the harness checks in either layout. Do not copy upstream index rows into consumer indexes.

`migrate-to-subtree.sh --skip-subtree --reconcile --symlink-consumer-skills --apply` refreshes skill shims and runs the same generator, then updates kit version/URL metadata. Local installed frontmatter takes precedence over upstream index wording and order. No extra generation pass is needed; a subsequent `build-index.sh` should exit 0. For already-vendored installs, dry-run includes rows from planned kit/consumer shim additions using a temporary view of source directories. Before the initial subtree add, upstream sources are unavailable and the preview reports that limitation. Other consumer metadata and routing prose are retained.
