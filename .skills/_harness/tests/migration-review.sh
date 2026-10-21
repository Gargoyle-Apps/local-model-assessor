#!/usr/bin/env bash
set -euo pipefail

# Regression tests for migration review findings. Every Git write is confined
# to disposable fixtures; the repository running this test is read-only.
repo_root="$(cd "$(dirname "$0")/../../.." && pwd -L)"
fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
trap 'exit 1' HUP INT TERM

skill() {
  local directory="$1" name="$2" description="$3"
  mkdir -p "$directory"
  cat > "$directory/SKILL.md" <<EOF
---
name: $name
description: "$description"
triggers: [run $name]
dependencies: []
version: "1.0.0"
---
# $name
EOF
}

seed() {
  local directory="$1"
  mkdir -p "$directory/.skills/_harness" "$directory/.skills/_skills"
  cp "$repo_root/.skills/_harness/migrate-to-subtree.sh" "$directory/.skills/_harness/"
  cat > "$directory/.skills/_meta.yml" <<'EOF'
kit_version: "1.0.0"
repo_url: "https://github.com/Gargoyle-Apps/skills-harness"
role: consumer
prefixes:
  - app-
EOF
  cat > "$directory/.skills/_index.md" <<'EOF'
# Consumer skills

Keep this routing prose.

| name | description | triggers |
|------|-------------|----------|
EOF
  git -C "$directory" init -q
}

migrate() {
  local directory="$1"; shift
  SKILLS_HARNESS_DIR="$directory/.skills/_harness" \
    SKILLS_REPO_ROOT="$directory" SKILLS_DIR="$directory/.skills/_skills" \
    bash "$directory/.skills/_harness/migrate-to-subtree.sh" "$@"
}

generate() {
  local directory="$1"; shift
  SKILLS_HARNESS_DIR="$directory/.skills/_harness" \
    SKILLS_META="$directory/.skills/_meta.yml" SKILLS_INDEX="$directory/.skills/_index.md" \
    SKILLS_DIR="$directory/.skills/_skills" bash "$directory/.skills/_harness/build-index.sh" "$@"
}

update="$fixture/update"
seed "$update"
cp "$repo_root/.skills/_harness/build-index.sh" "$update/.skills/_harness/"
cp "$repo_root/.skills/_harness/"*.awk "$update/.skills/_harness/"
mkdir -p "$update/.skills-harness/.skills"
cp "$update/.skills/_meta.yml" "$update/.skills-harness/.skills/_meta.yml"
printf '\nconsumer_skills_dir: custom\n' >> "$update/.skills/_meta.yml"
skill "$update/.skills/_skills/kit-current" kit-current 'Local wording retained in update mode.'
skill "$update/.skills-harness/.skills/_skills/kit-current" kit-current 'Upstream wording for full migration.'
skill "$update/.skills-harness/.skills/_skills/kit-renamed" kit-renamed 'Renamed upstream skill.'
skill "$update/.skills/_skills/app-existing" app-existing 'Existing consumer skill.'
skill "$update/.skills/_skills/kit-local" kit-local 'A real directory must be kept.'
skill "$update/.skills/_skills/kit-current.bak" kit-current 'Inactive backup with old name.'
skill "$update/.skills/_skills/_internal" invalid-internal 'Inactive internal directory.'
skill "$update/.skills-harness/.skills/_skills/kit-source.bak" kit-source 'Inactive upstream backup.'
skill "$update/custom/app-source.bak" app-source 'Inactive consumer backup.'
skill "$update/custom/_internal" invalid-internal 'Inactive consumer internal directory.'
skill "$update/custom/app-new" app-new 'New consumer skill.'
ln -s ../../.skills-harness/.skills/_skills/kit-removed "$update/.skills/_skills/kit-removed"
ln -s ../../.skills-harness/.skills/_skills/kit-old-name "$update/.skills/_skills/kit-old-name"
ln -s ../../foreign/missing "$update/.skills/_skills/app-foreign"
ln -s ../../.skills-harness/.skills/_skills/other-name "$update/.skills/_skills/app-foreign-kit-path"
git -C "$update" add .
git -C "$update" -c user.name=Test -c user.email=test@example.com commit -qm fixture

migrate "$update" --skip-subtree --reconcile --symlink-consumer-skills \
  --force --accept-upstream kit-current > "$fixture/update-preview" 2>&1
grep -q 'PLAN.*remove.*kit-removed' "$fixture/update-preview"
grep -q 'PLAN.*remove.*kit-old-name' "$fixture/update-preview"
grep -q '^+| kit-current | Local wording retained' "$fixture/update-preview"
! grep -q '^+| kit-current | Upstream wording' "$fixture/update-preview"
! grep -q "consumer skill '.*\.bak'" "$fixture/update-preview"
! grep -q 'PLAN.*link.*\.bak' "$fixture/update-preview"
test -L "$update/.skills/_skills/kit-removed"
test -L "$update/.skills/_skills/kit-old-name"
test ! -e "$update/.skills/_skills/app-new"
git -C "$update" diff --exit-code

migrate "$update" --skip-subtree --reconcile --symlink-consumer-skills \
  --force --accept-upstream kit-current --apply > "$fixture/update-apply" 2>&1
test ! -L "$update/.skills/_skills/kit-removed"
test ! -L "$update/.skills/_skills/kit-old-name"
test -f "$update/.skills/_skills/kit-renamed/SKILL.md"
test -d "$update/.skills/_skills/kit-local"
test ! -L "$update/.skills/_skills/kit-current"
test -L "$update/.skills/_skills/app-foreign"
test -L "$update/.skills/_skills/app-foreign-kit-path"
test -d "$update/.skills/_skills/kit-current.bak"
test ! -e "$update/.skills/_skills/kit-source.bak"
test ! -e "$update/.skills/_skills/app-source.bak"
! grep -q "consumer skill '.*\.bak'" "$fixture/update-apply"
generate "$update" > "$fixture/generator" 2>&1
grep -q '^| kit-current | Local wording retained' "$update/.skills/_index.md"
grep -q 'build-index.sh --write' "$fixture/update-apply"
git -C "$update" add .
git -C "$update" -c user.name=Test -c user.email=test@example.com commit -qm applied
migrate "$update" --skip-subtree --reconcile --symlink-consumer-skills --apply > "$fixture/repeated" 2>&1
git -C "$update" diff --exit-code

# A downloaded migration helper must finish its dry-run even when the legacy
# install has no generator and upstream sources have not been fetched.
legacy="$fixture/legacy"
seed "$legacy"
skill "$legacy/.skills/_skills/harness-upgrade" harness-upgrade 'Legacy local wording.'
migrate "$legacy" --reconcile --force --native-target .agents/skills > "$fixture/legacy-preview" 2>&1
grep -q 'Index preview unavailable.*generator' "$fixture/legacy-preview"
grep -q '[Uu]pstream.*unavailable' "$fixture/legacy-preview"
grep -q 'PLAN.*\.agents/skills' "$fixture/legacy-preview"
grep -q 'dry-run.*Re-run with --apply' "$fixture/legacy-preview"
test ! -e "$legacy/.skills-harness"
test ! -e "$legacy/.agents"

# A current local generator cannot predict unknown upstream replacements.
cp "$repo_root/.skills/_harness/build-index.sh" "$legacy/.skills/_harness/"
cp "$repo_root/.skills/_harness/"*.awk "$legacy/.skills/_harness/"
migrate "$legacy" --reconcile --accept-upstream harness-upgrade > "$fixture/legacy-current" 2>&1
grep -q 'upstream additions and replacements.*unavailable' "$fixture/legacy-current"
grep -q '^+| harness-upgrade | Legacy local wording.' "$fixture/legacy-current"
test ! -e "$legacy/.skills-harness"

echo 'Migration review regressions passed.'
