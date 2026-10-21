#!/bin/bash
set -euo pipefail

# Zero-dependency smoke coverage for context-optimized routing and discovery.
# Compatible with macOS bash 3.2.

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
repo_root="$(cd "$script_dir/../../.." && pwd -P)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-harness-smoke.XXXXXX")"

cleanup() {
  case "$test_root" in
    "${TMPDIR:-/tmp}"/skills-harness-smoke.*) rm -rf "$test_root" ;;
    *) echo "WARN: refusing to clean unexpected test path: $test_root" >&2 ;;
  esac
}
trap cleanup EXIT HUP INT TERM

pass() { printf 'ok - %s\n' "$1"; }
fail() { printf 'not ok - %s\n' "$1" >&2; exit 1; }

fixture="$test_root/repo"
mkdir -p "$fixture/.skills/_harness" "$fixture/.skills/_skills/example" \
  "$fixture/.skills/_skills/cycle-a" "$fixture/.skills/_skills/cycle-b"
cp "$repo_root/.skills/_harness/check.sh" "$fixture/.skills/_harness/check.sh"
cp "$repo_root/.skills/_harness/link.sh" "$fixture/.skills/_harness/link.sh"
cp "$repo_root/.skills/_harness/build-index.sh" "$fixture/.skills/_harness/build-index.sh"
cp "$repo_root/.skills/_harness/validate-optional-frontmatter.awk" "$fixture/.skills/_harness/validate-optional-frontmatter.awk"
cp "$repo_root/.skills/_harness/_rules.md" "$fixture/.skills/_harness/_rules.md"
chmod +x "$fixture/.skills/_harness/check.sh" "$fixture/.skills/_harness/link.sh"

cat > "$fixture/.skills/_skills/example/SKILL.md" <<'EOF'
---
name: example
description: "Exercises native target smoke checks when validating the harness fixture."
triggers:
  - example smoke
dependencies:
  - missing-companion
version: "1.0.0"
---

# Example

Fixture body.
EOF

cat > "$fixture/.skills/_skills/cycle-a/SKILL.md" <<'EOF'
---
name: cycle-a
description: "Exercises dependency cycle detection when validating the harness fixture."
triggers:
  - cycle a smoke
dependencies:
  - cycle-b
version: "1.0.0"
---

# Cycle A
EOF

cat > "$fixture/.skills/_skills/cycle-b/SKILL.md" <<'EOF'
---
name: cycle-b
description: "Completes the dependency cycle used by the harness smoke fixture."
triggers:
  - cycle b smoke
dependencies:
  - cycle-a
version: "1.0.0"
---

# Cycle B
EOF

cat > "$fixture/.skills/_index.md" <<'EOF'
# Skills

| name | description | triggers | path |
|---|---|---|---|
| example | Exercises native target smoke checks. | example smoke | `.skills/_skills/example/SKILL.md` |
| cycle-a | Exercises dependency cycle detection. | cycle a smoke | `.skills/_skills/cycle-a/SKILL.md` |
| cycle-b | Completes the dependency cycle. | cycle b smoke | `.skills/_skills/cycle-b/SKILL.md` |
EOF
/bin/bash "$fixture/.skills/_harness/build-index.sh" --write > "$test_root/build-index.out"

cat > "$fixture/.skills/_meta.yml" <<'EOF'
kit_version: "0.0.0"
role: consumer
native_targets:
  - .agents/skills
EOF

undeclared="$test_root/undeclared"
cp -R "$fixture" "$undeclared"
cat > "$undeclared/.skills/_meta.yml" <<'EOF'
kit_version: "0.0.0"
role: consumer
EOF
undeclared_output="$test_root/undeclared.out"
if ! SKILLS_CHECK_KIT_SURFACES=0 /bin/bash \
  "$undeclared/.skills/_harness/check.sh" >"$undeclared_output" 2>&1; then
  fail "undeclared empty native target set completes under bash 3.2"
fi
if grep -q 'unbound variable' "$undeclared_output"; then
  fail "undeclared empty native target set avoids bash 3.2 nounset abort"
fi
grep -q 'All checks passed.' "$undeclared_output" \
  || fail "undeclared empty native target set reaches validation summary"
pass "undeclared empty native target set completes under bash 3.2"

missing_output="$test_root/missing.out"
if SKILLS_CHECK_KIT_SURFACES=0 "$fixture/.skills/_harness/check.sh" >"$missing_output" 2>&1; then
  fail "declared missing native target fails validation"
fi
grep -q "declared native target '.agents/skills' is absent" "$missing_output" \
  || fail "missing native target has actionable diagnostic"
pass "declared missing native target fails validation"

linked_output="$test_root/linked.out"
SKILLS_CHECK_KIT_SURFACES=0 "$fixture/.skills/_harness/check.sh" --link >"$linked_output" 2>&1
[[ -L "$fixture/.agents/skills/example" ]] || fail "check --link creates declared target"
grep -q "declares missing dependency 'missing-companion'" "$linked_output" \
  || fail "dependency target warning is emitted"
grep -q 'dependency cycle detected:' "$linked_output" \
  || fail "dependency cycle warning is emitted"
pass "check --link creates target and dependency graph warnings"

flow_guard="$test_root/flow-guard"
cp -R "$fixture" "$flow_guard"
cat > "$flow_guard/.skills/_meta.yml" <<'EOF'
kit_version: "0.0.0"
role: consumer
native_targets: [.agents/skills]
EOF
if "$flow_guard/.skills/_harness/link.sh" --clean .agents/skills \
  >"$test_root/flow-guard.out" 2>&1; then
  fail "link --clean rejects unsupported metadata before deletion"
fi
[[ -L "$flow_guard/.agents/skills/example" ]] \
  || fail "link --clean preserves links when metadata validation fails"
pass "link --clean validates metadata before deletion"

escape_outside="$test_root/escape-outside"
mkdir -p "$escape_outside"
ln -s "$escape_outside" "$flow_guard/.escape"
if "$flow_guard/.skills/_harness/link.sh" --no-record .escape/skills \
  >"$test_root/escape-guard.out" 2>&1; then
  fail "link rejects native target escaping through symlink"
fi
grep -q 'target resolves outside repo root' "$test_root/escape-guard.out" \
  || fail "symlink escape has actionable diagnostic"
[[ ! -e "$escape_outside/skills" ]] \
  || fail "symlink escape creates no outside target"
pass "link rejects native target escaping through symlink"

"$fixture/.skills/_harness/link.sh" .claude/skills >"$test_root/record.out" 2>&1
grep -A3 '^native_targets:' "$fixture/.skills/_meta.yml" | grep -q '  - .claude/skills' \
  || fail "link records an additional native target"
[[ -L "$fixture/.claude/skills/example" ]] || fail "recorded target is linked"
pass "link persists additional native targets"

migration="$test_root/migration"
mkdir -p "$migration/.skills/_harness" "$migration/.skills/_skills" \
  "$migration/.skills-harness/.skills/_skills/kit-demo"
cp "$repo_root/.skills/_harness/migrate-to-subtree.sh" "$migration/.skills/_harness/migrate-to-subtree.sh"
cp "$repo_root/.skills/_harness/link.sh" "$migration/.skills/_harness/link.sh"
cp "$repo_root/.skills/_harness/build-index.sh" "$migration/.skills/_harness/build-index.sh"
chmod +x "$migration/.skills/_harness/migrate-to-subtree.sh" "$migration/.skills/_harness/link.sh"
cat > "$migration/.skills/_meta.yml" <<'EOF'
kit_version: "0.0.0"
repo_url: "https://github.com/Gargoyle-Apps/skills-harness"
role: consumer
EOF
cat > "$migration/.skills-harness/.skills/_skills/kit-demo/SKILL.md" <<'EOF'
---
name: kit-demo
description: "Supports the subtree migration smoke fixture."
triggers: []
dependencies: []
version: "1.0.0"
---
EOF
(
  cd "$migration"
  git init -q
  git config user.email smoke@example.invalid
  git config user.name "Smoke Test"
  git add .
  git commit -qm fixture
  .skills/_harness/migrate-to-subtree.sh \
    --skip-subtree --native-target .agents/skills \
    --native-target '.native skills' --apply
) >"$test_root/migration.out" 2>&1
grep -A2 '^native_targets:' "$migration/.skills/_meta.yml" | grep -q '  - .agents/skills' \
  || fail "migration persists explicit native target"
[[ -L "$migration/.agents/skills/kit-demo" ]] \
  || fail "migration syncs explicit native target"
grep -Fq '  - .native skills' "$migration/.skills/_meta.yml" \
  || fail "migration preserves native target containing spaces"
[[ -L "$migration/.native skills/kit-demo" ]] \
  || fail "migration syncs native target containing spaces"
pass "subtree migration persists and syncs native targets"

migration_help="$test_root/migration-help.out"
/bin/bash "$migration/.skills/_harness/migrate-to-subtree.sh" --help \
  >"$migration_help" 2>&1
grep -q '^Defaults:$' "$migration_help" \
  || fail "subtree migration help includes Defaults section"
grep -q '^  ref         = main$' "$migration_help" \
  || fail "subtree migration help includes ref default"
grep -q '^  prefix      = .skills-harness$' "$migration_help" \
  || fail "subtree migration help includes prefix default"
pass "subtree migration help includes complete defaults"

cursor_template="$repo_root/.skills/_harness/CURSOR_template.md"
[[ "$(grep -c '^# Skills Harness (Cursor)$' "$cursor_template")" -eq 1 ]] \
  || fail "Cursor template contains one shared harness surface"
if grep -qE 'CURSOR_RULE|alwaysApply:[[:space:]]*true' "$cursor_template"; then
  fail "Cursor template avoids duplicate always-on rule"
fi
pass "Cursor template uses one shared always-on surface"

codex_home="$test_root/codex-home"
mkdir -p "$codex_home"
codex_output="$test_root/codex.out"
(
  cd "$repo_root"
  HOME="$codex_home" .skills/_skills/caveman/scripts/deploy.sh codex --dry-run
) >"$codex_output" 2>&1
grep -Fq "$codex_home/.agents/skills" "$codex_output" \
  || fail "Codex deploy uses current user-skill path"
if grep -Fq "$codex_home/.codex/skills" "$codex_output"; then
  fail "Codex deploy avoids legacy user-skill path"
fi
pass "Codex deploy uses HOME/.agents/skills"

legacy_dir="$test_root/codex-legacy-override"
default_legacy_dir="$codex_home/.codex/skills"
mkdir -p "$legacy_dir" "$default_legacy_dir" \
  "$test_root/empty-cursor" "$test_root/empty-claude" \
  "$test_root/empty-codex" "$test_root/empty-commands" "$test_root/empty-prompts"
for name in caveman caveman-commit caveman-review; do
  ln -s "$repo_root/.skills/_skills/$name" "$legacy_dir/$name"
  ln -s "$repo_root/.skills/_skills/$name" "$default_legacy_dir/$name"
done
HOME="$codex_home" CODEX_LEGACY_SKILLS_DIR="$legacy_dir" \
  "$repo_root/.skills/_skills/caveman/scripts/deploy.sh" codex --uninstall \
  >"$test_root/codex-uninstall.out" 2>&1
for name in caveman caveman-commit caveman-review; do
  [[ ! -e "$legacy_dir/$name" && ! -L "$legacy_dir/$name" ]] \
    || fail "Codex uninstall removes legacy managed $name"
  [[ -L "$default_legacy_dir/$name" ]] \
    || fail "Codex legacy override leaves default path untouched"
done
pass "Codex uninstall honors legacy path override"

HOME="$codex_home" \
  "$repo_root/.skills/_skills/caveman/scripts/deploy.sh" codex --uninstall \
  >"$test_root/codex-default-uninstall.out" 2>&1
for name in caveman caveman-commit caveman-review; do
  [[ ! -e "$default_legacy_dir/$name" && ! -L "$default_legacy_dir/$name" ]] \
    || fail "Codex uninstall removes default legacy managed $name"
done
pass "Codex uninstall removes default legacy managed trio"

HOME="$codex_home" CURSOR_SKILLS_DIR="$test_root/empty-cursor" \
  "$repo_root/.skills/_skills/caveman/scripts/deploy.sh" cursor --uninstall \
  >"$test_root/cursor-uninstall.out" 2>&1 \
  || fail "non-Codex uninstall remains nounset-safe"
pass "non-Codex uninstall remains nounset-safe"

mkdir -p "$legacy_dir/example"
cat > "$legacy_dir/example/SKILL.md" <<'EOF'
---
name: example
description: "Divergent legacy fixture."
---
EOF

conflict_output="$test_root/conflict.out"
if SKILLS_DIR="$fixture/.skills/_skills" \
  CURSOR_SKILLS_DIR="$test_root/empty-cursor" \
  CLAUDE_SKILLS_DIR="$test_root/empty-claude" \
  CODEX_SKILLS_DIR="$test_root/empty-codex" \
  CODEX_LEGACY_SKILLS_DIR="$legacy_dir" \
  CURSOR_COMMANDS_DIR="$test_root/empty-commands" \
  CLAUDE_COMMANDS_DIR="$test_root/empty-commands" \
  CODEX_PROMPTS_DIR="$test_root/empty-prompts" \
  "$repo_root/.skills/_harness/skill-conflicts.sh" >"$conflict_output" 2>&1; then
  fail "legacy Codex conflicts remain visible during migration"
fi
grep -q 'codex:skills:legacy/example' "$conflict_output" \
  || fail "legacy Codex conflict identifies legacy surface"
pass "legacy Codex conflicts remain visible during migration"

/bin/bash "$script_dir/deploy-uninstall.sh"
/bin/bash "$script_dir/optional-frontmatter.sh"
/bin/bash "$script_dir/indexes.sh"
/bin/bash "$script_dir/migration-review.sh"
/bin/bash "$script_dir/pipeline-review.sh"

printf 'All smoke tests passed.\n'
