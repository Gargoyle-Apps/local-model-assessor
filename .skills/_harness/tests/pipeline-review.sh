#!/bin/bash
set -euo pipefail

# Regression coverage for backup exclusion and quiet validation diagnostics.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
repo_root="$(cd "$script_dir/../../.." && pwd -P)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-pipeline-review.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT
trap 'exit 1' HUP INT TERM
fail() { printf 'not ok - %s\n' "$1" >&2; exit 1; }
pass() { printf 'ok - %s\n' "$1"; }

fixture="$test_root/repo"
mkdir -p "$fixture/.skills/_skills/example" "$fixture/.skills/_harness"
cp "$repo_root/.skills/_harness/"*.sh "$fixture/.skills/_harness/"
cp "$repo_root/.skills/_harness/"*.awk "$fixture/.skills/_harness/"
cp "$repo_root/.skills/_harness/_rules.md" "$fixture/.skills/_harness/"
cat > "$fixture/.skills/_skills/example/SKILL.md" <<'EOF'
---
name: example
description: "Checks the harness review fixture."
triggers: []
dependencies: []
version: "1.0.0"
---
# Example
EOF
cp -R "$fixture/.skills/_skills/example" "$fixture/.skills/_skills/example.bak"
mkdir "$fixture/.skills/_skills/_notes"
printf 'Deliberately not a skill.\n' > "$fixture/.skills/_skills/_notes/SKILL.md"
cat > "$fixture/.skills/_meta.yml" <<'EOF'
kit_version: "0.0.0"
role: consumer
native_targets:
  - .agents/skills
EOF
printf '# Skills\n\n| name | description | triggers |\n|---|---|---|\n' > "$fixture/.skills/_index.md"
run_check() { /bin/bash "$fixture/.skills/_harness/check.sh" "$@"; }

/bin/bash "$fixture/.skills/_harness/build-index.sh" --write > "$test_root/generation.log"
/bin/sh "$fixture/.skills/_harness/link.sh" --no-record .agents/skills > "$test_root/link.log"
[[ -L "$fixture/.agents/skills/example" ]] || fail 'active skill has native link'
[[ ! -e "$fixture/.agents/skills/example.bak" && ! -L "$fixture/.agents/skills/example.bak" ]] || fail 'backup must not be exposed through native discovery'
[[ ! -e "$fixture/.agents/skills/_notes" && ! -L "$fixture/.agents/skills/_notes" ]] || fail 'internal directory must not be exposed'
run_check > "$test_root/check.log" 2>&1 || { cat "$test_root/check.log"; fail 'backup and internal files excluded from all validation'; }
cmp "$fixture/.skills/_skills/example/SKILL.md" "$fixture/.skills/_skills/example.bak/SKILL.md"
pass 'backup and internal directories are preserved but not catalogued, linked, or validated'

mkdir -p "$test_root/user-skills/example.bak" "$test_root/user-skills/_notes"
printf 'different backup\n' > "$test_root/user-skills/example.bak/SKILL.md"
printf 'different notes\n' > "$test_root/user-skills/_notes/SKILL.md"
SKILLS_DIR="$fixture/.skills/_skills" \
  CURSOR_SKILLS_DIR="$test_root/user-skills" \
  CLAUDE_SKILLS_DIR="$test_root/empty" CODEX_SKILLS_DIR="$test_root/empty" \
  CODEX_LEGACY_SKILLS_DIR="$test_root/empty" CURSOR_COMMANDS_DIR="$test_root/empty" \
  CLAUDE_COMMANDS_DIR="$test_root/empty" CODEX_PROMPTS_DIR="$test_root/empty" \
  /bin/bash "$fixture/.skills/_harness/skill-conflicts.sh" > "$test_root/conflicts.out" 2>&1 \
  || fail 'conflict scanner must ignore inactive backup and internal directories'
grep -q 'Scanning 1 repo-managed skill' "$test_root/conflicts.out" || fail 'conflict inventory includes only active skill'
pass 'conflict scanning excludes backups and internal directories'

# Clean up only inactive links previously created by this helper, not user files
# or foreign links that happen to have a backup-like name.
ln -s ../../.skills/_skills/example.bak "$fixture/.agents/skills/example.bak"
ln -s ../../.skills/_skills/_notes "$fixture/.agents/skills/_notes"
mkdir -p "$test_root/foreign"
ln -s "$test_root/foreign" "$fixture/.agents/skills/foreign.bak"
printf 'user file\n' > "$fixture/.agents/skills/file.bak"
if run_check --quiet > "$test_root/inactive.out" 2> "$test_root/inactive.err"; then
  fail 'validation must diagnose active managed backup exposure'
fi
grep -q 'inactive.*native discovery' "$test_root/inactive.err" || fail 'inactive exposure has actionable diagnostic'
/bin/sh "$fixture/.skills/_harness/link.sh" --no-record .agents/skills > "$test_root/repair.log"
[[ ! -L "$fixture/.agents/skills/example.bak" && ! -L "$fixture/.agents/skills/_notes" ]] || fail 'managed inactive links removed'
[[ -L "$fixture/.agents/skills/foreign.bak" ]] || fail 'foreign link preserved'
[[ "$(cat "$fixture/.agents/skills/file.bak")" == 'user file' ]] || fail 'user file preserved'
[[ -f "$fixture/.skills/_skills/example.bak/SKILL.md" ]] || fail 'source backup preserved'
pass 'native repair removes only managed inactive links and preserves backup content'

run_check --quiet > "$test_root/quiet.out" 2> "$test_root/quiet.err"
[[ ! -s "$test_root/quiet.out" ]] || fail 'quiet successful check has no stdout'
grep -q 'foreign.bak' "$test_root/quiet.err" || fail 'quiet mode retains warnings'
run_check --quiet --link > "$test_root/quiet-link.out" 2> "$test_root/quiet-link.err"
[[ ! -s "$test_root/quiet-link.out" ]] || fail 'quiet successful link check has no stdout'
pass 'quiet mode suppresses success output while retaining warnings'

sed 's/| example |/| absent |/' "$fixture/.skills/_index.md" > "$test_root/drifted-index.md"
cp "$test_root/drifted-index.md" "$fixture/.skills/_index.md"
if run_check --quiet > "$test_root/failure.out" 2> "$test_root/failure.err"; then
  fail 'quiet mode must fail on index drift'
fi
grep -q 'Generated index validation failed' "$test_root/failure.err" || fail 'quiet failure retains diagnostic'
grep -q 'absent' "$test_root/failure.out" || fail 'quiet failure retains actionable row diff'
pass 'quiet failure preserves error and generated-row diff'
printf 'Pipeline review regressions passed.\n'
