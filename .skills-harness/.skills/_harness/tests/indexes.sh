#!/usr/bin/env bash
set -euo pipefail
repo_root="$(cd "$(dirname "$0")/../../.." && pwd)"
fixture="$(mktemp -d)"
reconcile_log="$(mktemp)"
trap 'rm -rf "$fixture"; rm -f "$reconcile_log"' EXIT
trap 'exit 1' HUP INT TERM
mkdir -p "$fixture/.skills/_skills" "$fixture/.skills/_harness"
cp "$repo_root/.skills/_harness/"*.sh "$fixture/.skills/_harness/"
export SKILLS_HARNESS_DIR="$fixture/.skills/_harness"
export SKILLS_DIR="$fixture/.skills/_skills"
export SKILLS_INDEX="$fixture/.skills/_index.md"
export SKILLS_META="$fixture/.skills/_meta.yml"
export SKILLS_REPO_ROOT="$fixture"
generate() { bash "$SKILLS_HARNESS_DIR/build-index.sh" "$@" > "$fixture/output" 2>&1; }
expect_failure() {
  local expected="$1"; shift
  if generate "$@"; then echo "FAIL: expected $expected" >&2; exit 1; fi
  grep -q "$expected" "$fixture/output" || { cat "$fixture/output"; exit 1; }
}
create_skill() {
  local name="$1"
  mkdir -p "$SKILLS_DIR/$name"
  cat > "$SKILLS_DIR/$name/SKILL.md" <<EOF
---
name: $name
description: "Use $name for its workflow."
triggers:
  - run $name
dependencies: []
version: "1.0.0"
metadata:
  name: must-not-override
  family: advisory-only
---
# $name
EOF
}
for ((i=1; i<=7; i++)); do create_skill "kit-$i"; done
for ((i=1; i<=25; i++)); do create_skill "app-$i"; create_skill "ops-$i"; done
cat > "$SKILLS_INDEX" <<'EOF'
# Skills

Routing: use app for application work; ops for operations.

| name | description | triggers |
|------|-------------|----------|
| removed | stale wording | old trigger |

Keep this human-authored routing footer.
EOF
cat > "$SKILLS_META" <<'EOF'
kit_version: "1.0.0"
repo_url: "https://github.com/Gargoyle-Apps/skills-harness"
role: consumer
prefixes:
  - app-
  - ops-
EOF
cp "$SKILLS_INDEX" "$fixture/original"
: > "$SKILLS_INDEX"
expect_failure 'empty file' --write
test ! -s "$SKILLS_INDEX"
cp "$fixture/original" "$SKILLS_INDEX"
expect_failure 'Index drift' --dry-run
cmp "$SKILLS_INDEX" "$fixture/original"
generate --write
generate
test "$(grep -c '^| [a-z]' "$SKILLS_INDEX")" = 58
grep -q 'human-authored routing footer' "$SKILLS_INDEX"

# Duplicate legacy family tables must be diagnosed before any writes.
cp "$SKILLS_INDEX" "$fixture/single"
printf '\n## Extra family\n\n| name | description | triggers |\n|------|-------------|----------|\n| app-1 | stale | stale |\n' >> "$SKILLS_INDEX"
cp "$SKILLS_INDEX" "$fixture/duplicate"
expect_failure 'multiple skill tables' --write
cmp "$SKILLS_INDEX" "$fixture/duplicate"
sed 's/^|/  |/' "$SKILLS_INDEX" > "$fixture/indented"
cp "$fixture/indented" "$SKILLS_INDEX"
expect_failure 'multiple skill tables' --write
cmp "$SKILLS_INDEX" "$fixture/indented"
cp "$fixture/single" "$SKILLS_INDEX"

# Existing ownership declarations need not be exclusive in single mode.
cp "$SKILLS_META" "$fixture/single-meta"
printf '  - app-more-\n' >> "$SKILLS_META"
generate
printf 'prefixes: [app-, ops-]\n' > "$SKILLS_META"
generate
cp "$fixture/single-meta" "$SKILLS_META"

# Dry-run conversion shows files/rows but creates nothing.
printf '\nindex_layout: split\nindex_fallback: kit\n' >> "$SKILLS_META"
expect_failure 'Index drift' --dry-run
test ! -e "$fixture/.skills/_indexes"
cmp "$SKILLS_INDEX" "$fixture/single"
generate --write
generate
grep -q 'Routing: use app' "$SKILLS_INDEX"
grep -q 'human-authored routing footer' "$SKILLS_INDEX"
test "$(grep -h '^| ' "$fixture/.skills/_indexes/"*.md | grep -v '^| name ' | wc -l | tr -d ' ')" = 57
test "$(grep -h '^| ' "$fixture/.skills/_indexes/"*.md | grep -v '^| name ' | sort -u | wc -l | tr -d ' ')" = 57
for group in kit app ops; do
  grep -q "_indexes/$group.md" "$SKILLS_INDEX"
done
! grep -q '^| name ' "$SKILLS_INDEX"
grep -q '^| kit-1 ' "$fixture/.skills/_indexes/kit.md"
! grep -q '^| ops-' "$fixture/.skills/_indexes/app.md"

# Grouping accepts YAML comments/quotes and diagnoses malformed block entries.
# Single mode deliberately does not reinterpret legacy ownership declarations.
cp "$SKILLS_META" "$fixture/split-meta"
cat > "$SKILLS_META" <<'EOF'
prefixes : # consumer ownership
  - "app-" # application family
  - 'ops-' # operations family
index_layout : 'split' # opt in
index_fallback : "kit" # unmatched skills
EOF
generate
for bad in '  app-' '  - "app-' '  - app-#comment' '  - "app- # quoted text"' '  - app--' '  - app-more--'; do
  printf 'index_layout: split\nindex_fallback: kit\nprefixes:\n%s\n' "$bad" > "$SKILLS_META"
  expect_failure 'prefix' --write
done
printf 'index_layout: split\nindex_fallback: kit\nprefixes: ""\n' > "$SKILLS_META"
expect_failure 'block list' --write
printf 'index_layout: split\nindex_fallback: kit\nprefixes:\n  - app-\n    - ops-\n' > "$SKILLS_META"
expect_failure 'indentation' --write
for bad in kit- kit--fallback '"kit' '"kit"#comment'; do
  printf 'index_layout: split\nindex_fallback: %s\n' "$bad" > "$SKILLS_META"
  expect_failure 'index_fallback' --write
done
printf 'index_layout:split\nindex_fallback: kit\n' > "$SKILLS_META"
expect_failure 'space after the colon' --write
cp "$fixture/split-meta" "$SKILLS_META"
for bad in a- a--bad; do
  create_skill "$bad"
  expect_failure 'safe directory name' --write
  mv "$SKILLS_DIR/$bad" "$fixture/$bad.invalid"
done
generate

# Human scope prose survives updates; additions/removals/stale wording repair.
printf '\nHuman scope notes for app.\n' >> "$fixture/.skills/_indexes/app.md"
create_skill app-new
mv "$SKILLS_DIR/ops-25" "$fixture/removed-ops-25"
sed 's/Use app-1 for its workflow./Fresh local wording./' "$SKILLS_DIR/app-1/SKILL.md" > "$fixture/skill"
cp "$fixture/skill" "$SKILLS_DIR/app-1/SKILL.md"
expect_failure 'Index drift'
generate --write
generate
grep -q 'Human scope notes' "$fixture/.skills/_indexes/app.md"
grep -q 'Fresh local wording' "$fixture/.skills/_indexes/app.md"
! grep -q '^| ops-25 ' "$fixture/.skills/_indexes/ops.md"
grep -q '^| app-new ' "$fixture/.skills/_indexes/app.md"

# Missing child, broken link, stale row, and duplicated entry all cause drift.
mv "$fixture/.skills/_indexes/ops.md" "$fixture/ops.saved"
expect_failure 'Index drift'
generate --write
sed 's@_indexes/app.md@_indexes/missing.md@' "$SKILLS_INDEX" > "$fixture/root"
cp "$fixture/root" "$SKILLS_INDEX"
expect_failure 'Index drift'
generate --write
sed '/| app-1 |/p' "$fixture/.skills/_indexes/app.md" > "$fixture/app"
cp "$fixture/app" "$fixture/.skills/_indexes/app.md"
expect_failure 'Index drift'
generate --write

# Refuse unowned child files, unknown managed groups, symlinks, unsafe names.
mv "$fixture/.skills/_indexes/app.md" "$fixture/app.saved"
: > "$fixture/.skills/_indexes/app.md"
expect_failure 'empty file' --write
test ! -s "$fixture/.skills/_indexes/app.md"
printf 'Human-owned file.\n' > "$fixture/.skills/_indexes/app.md"
expect_failure 'unowned index' --write
grep -q 'Human-owned file' "$fixture/.skills/_indexes/app.md"
cp "$fixture/app.saved" "$fixture/.skills/_indexes/app.md"
printf 'Unrelated human notes.\n' > "$fixture/.skills/_indexes/notes.md"
mkdir "$fixture/.skills/_indexes/notes-directory.md"
generate
grep -q 'Unrelated human notes' "$fixture/.skills/_indexes/notes.md"
ln -s "$fixture/missing-child.md" "$fixture/.skills/_indexes/unknown.md"
cp "$SKILLS_INDEX" "$fixture/before-dangling-root"
expect_failure 'dangling symlink; ownership cannot be checked' --write
cmp "$SKILLS_INDEX" "$fixture/before-dangling-root"
test -L "$fixture/.skills/_indexes/unknown.md"
! grep -q '^grep:' "$fixture/output"
unlink "$fixture/.skills/_indexes/unknown.md"
cp "$fixture/app.saved" "$fixture/.skills/_indexes/unknown.md"
expect_failure 'unknown generated group' --write
mv "$fixture/.skills/_indexes/unknown.md" "$fixture/unknown.saved"
mv "$fixture/.skills/_indexes/app.md" "$fixture/app.real"
ln -s "$fixture/app.real" "$fixture/.skills/_indexes/app.md"
expect_failure 'refusing non-regular index' --write
unlink "$fixture/.skills/_indexes/app.md"
cp "$fixture/app.real" "$fixture/.skills/_indexes/app.md"
cp "$SKILLS_META" "$fixture/meta"
printf 'index_fallback: ../escape\nindex_layout: split\n' > "$SKILLS_META"
expect_failure 'safe index_fallback' --write
cp "$fixture/meta" "$SKILLS_META"
sed '/  - app-/a\
  - app-more-
' "$SKILLS_META" > "$fixture/overlap"
cp "$fixture/overlap" "$SKILLS_META"
expect_failure 'overlapping prefixes' --write
cp "$fixture/meta" "$SKILLS_META"
generate

# A symlinked harness must address the consumer even under explicit bash -P.
# Normal fresh Bash already uses logical paths; inherited physical mode was
# the failing case, not ordinary direct invocation.
logical="$fixture/logical-consumer"
mkdir -p "$logical/.skills/_skills/local" "$logical/vendor/_harness" "$logical/vendor/_skills"
cp "$SKILLS_HARNESS_DIR/build-index.sh" "$logical/vendor/_harness/"
ln -s ../vendor/_harness "$logical/.skills/_harness"
printf '| name | description | triggers |\n|---|---|---|\n' > "$logical/.skills/_index.md"
printf 'Vendor index must remain untouched.\n' > "$logical/vendor/_index.md"
cat > "$logical/.skills/_skills/local/SKILL.md" <<'EOF'
---
name: local
description: Consumer local skill.
triggers: []
---
EOF
(
  unset SKILLS_HARNESS_DIR SKILLS_DIR SKILLS_INDEX SKILLS_META SKILLS_REPO_ROOT
  /bin/bash "$logical/.skills/_harness/build-index.sh" --write > "$logical/normal.out" 2>&1
  /bin/bash -P "$logical/.skills/_harness/build-index.sh" > "$logical/physical.out" 2>&1
)
grep -q '^| local |' "$logical/.skills/_index.md"
grep -qx 'Vendor index must remain untouched.' "$logical/vendor/_index.md"

# Real reconciliation: upstream index deliberately has stale wording/order.
# Local source is authoritative, even when an upstream row disagrees.
mkdir -p "$fixture/.skills-harness/.skills/_skills/kit-1"
cp "$SKILLS_DIR/kit-1/SKILL.md" "$fixture/.skills-harness/.skills/_skills/kit-1/SKILL.md"
cp "$SKILLS_META" "$fixture/.skills-harness/.skills/_meta.yml"
printf '| name | description | triggers |\n|---|---|---|\n| kit-1 | Wrong upstream wording | stale |\n' > "$fixture/.skills-harness/.skills/_index.md"
git -C "$fixture" init -q
git -C "$fixture" add .
git -C "$fixture" -c user.name=Test -c user.email=test@example.com commit -qm fixture
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --apply > "$reconcile_log" 2>&1
generate
git -C "$fixture" diff --exit-code -- .skills/_index.md .skills/_indexes
# Running generation first and reconcile twice also converges.
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --apply > "$reconcile_log" 2>&1
generate
git -C "$fixture" diff --exit-code -- .skills/_index.md .skills/_indexes

# Dry-run includes newly planned kit and consumer shims, without writing them.
mkdir -p "$fixture/.skills-harness/.skills/_skills/kit-new" "$fixture/custom/app-extra"
sed 's/kit-1/kit-new/g' "$SKILLS_DIR/kit-1/SKILL.md" > "$fixture/.skills-harness/.skills/_skills/kit-new/SKILL.md"
sed 's/app-1/app-extra/g' "$SKILLS_DIR/app-1/SKILL.md" > "$fixture/custom/app-extra/SKILL.md"
# A resolvable consumer shim needs retargeting; a dangling kit shim is repaired.
mkdir -p "$fixture/old-app" "$fixture/custom/app-retarget" "$fixture/.skills-harness/.skills/_skills/kit-dangling"
sed 's/app-1/app-retarget/g' "$SKILLS_DIR/app-1/SKILL.md" > "$fixture/old-app/SKILL.md"
sed 's/Fresh local wording./Correct retargeted wording./' "$fixture/old-app/SKILL.md" > "$fixture/custom/app-retarget/SKILL.md"
ln -s ../../old-app "$SKILLS_DIR/app-retarget"
sed 's/kit-1/kit-dangling/g' "$SKILLS_DIR/kit-1/SKILL.md" > "$fixture/.skills-harness/.skills/_skills/kit-dangling/SKILL.md"
ln -s ../../missing-kit "$SKILLS_DIR/kit-dangling"
printf '\nconsumer_skills_dir: custom\n' >> "$SKILLS_META"
sed 's/Fresh local wording./New local wording./' "$SKILLS_DIR/app-1/SKILL.md" > "$fixture/skill"
cp "$fixture/skill" "$SKILLS_DIR/app-1/SKILL.md"
git -C "$fixture" add .
git -C "$fixture" -c user.name=Test -c user.email=test@example.com commit -qm additions
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --symlink-consumer-skills > "$reconcile_log" 2>&1
grep -q '^+| kit-new ' "$reconcile_log"
grep -q '^+| app-extra ' "$reconcile_log"
grep -q '^+| app-retarget | Correct retargeted wording.' "$reconcile_log"
grep -q '^+| kit-dangling ' "$reconcile_log"
test ! -e "$SKILLS_DIR/kit-new"
test ! -e "$SKILLS_DIR/app-extra"
git -C "$fixture" diff --exit-code
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --symlink-consumer-skills --apply > "$reconcile_log" 2>&1
generate
grep -q 'New local wording' "$fixture/.skills/_indexes/app.md"
grep -q 'Correct retargeted wording' "$fixture/.skills/_indexes/app.md"
test -f "$SKILLS_DIR/kit-dangling/SKILL.md"
git -C "$fixture" add .
git -C "$fixture" -c user.name=Test -c user.email=test@example.com commit -qm repaired
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --symlink-consumer-skills --apply > "$reconcile_log" 2>&1
generate
git -C "$fixture" diff --exit-code -- .skills/_index.md .skills/_indexes .skills/_skills

# Single mode uses the same reconcile pipeline after explicitly archiving children.
mv "$fixture/.skills/_indexes" "$fixture/archived-indexes"
sed 's/index_layout: split/index_layout: single/' "$SKILLS_META" > "$fixture/meta-single"
cp "$fixture/meta-single" "$SKILLS_META"
generate --write
git -C "$fixture" add .
git -C "$fixture" -c user.name=Test -c user.email=test@example.com commit -qm single
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --apply > "$reconcile_log" 2>&1
generate
git -C "$fixture" diff --exit-code -- .skills/_index.md

# Dry-run with no installed skill directory must not create it.
mv "$SKILLS_DIR" "$fixture/installed-skills"
bash "$SKILLS_HARNESS_DIR/migrate-to-subtree.sh" --skip-subtree --reconcile --symlink-consumer-skills > "$reconcile_log" 2>&1
test ! -e "$SKILLS_DIR"

echo 'Index regression tests passed (57-skill single/split fixture and reconciliation).'
