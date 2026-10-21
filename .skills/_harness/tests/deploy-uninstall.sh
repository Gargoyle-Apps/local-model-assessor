#!/bin/bash
set -euo pipefail

# Ownership checks must work on dangling links without deleting foreign entries.
# Compatible with macOS Bash 3.2; all deployment paths stay inside the fixture.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd -P)"
repo_root="$(cd "$script_dir/../../.." && pwd -P)"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-harness-uninstall.XXXXXX")"
cleanup() {
  case "$test_root" in
    "${TMPDIR:-/tmp}"/skills-harness-uninstall.*) rm -rf "$test_root" ;;
    *) echo "WARN: refusing to clean unexpected test path: $test_root" >&2 ;;
  esac
}
trap cleanup EXIT HUP INT TERM
pass() { printf 'ok - %s\n' "$1"; }
fail() { printf 'not ok - %s\n' "$1" >&2; exit 1; }

skills="$test_root/checkout with spaces/_skills"
current="$test_root/current"
legacy="$test_root/legacy"
# Keep a fixture-only installer sibling so even caveman itself can be removed.
mkdir -p "$skills/installer/scripts" "$current" "$legacy"
cp "$repo_root/.skills/_skills/caveman/scripts/deploy.sh" "$skills/installer/scripts/deploy.sh"
deploy="$skills/installer/scripts/deploy.sh"
trio=(caveman caveman-commit caveman-review)
for name in "${trio[@]}"; do
  mkdir "$skills/$name"
done

uninstall() {
  CODEX_SKILLS_DIR="$current" CODEX_LEGACY_SKILLS_DIR="$legacy" \
    CODEX_AGENTS_FILE="$test_root/unused-memory" \
    /bin/bash "$deploy" codex --uninstall "$@" >"$test_root/uninstall.out" 2>&1 \
    || { cat "$test_root/uninstall.out" >&2; fail "uninstall exits successfully"; }
}
link_trio() {
  for name in "${trio[@]}"; do
    ln -s "$skills/$name" "$current/$name"
    ln -s "../checkout with spaces/_skills/./$name" "$legacy/$name"
  done
}
assert_removed() {
  for name in "${trio[@]}"; do
    for dest in "$current/$name" "$legacy/$name"; do
      [[ ! -e "$dest" && ! -L "$dest" ]] || fail "managed link removed: $dest"
    done
  done
}

link_trio
rmdir "$skills/caveman-commit"
uninstall --dry-run
for name in "${trio[@]}"; do
  [[ -L "$current/$name" && -L "$legacy/$name" ]] || fail "dry-run preserves $name"
done
pass "dry-run preserves existing and dangling links"
uninstall
assert_removed
pass "absolute and relative links removed with one missing source"

link_trio
mv "$skills/caveman-review" "$skills/renamed-review"
uninstall
assert_removed
pass "partially missing trio removed after source rename"

link_trio
rmdir "$skills/caveman"
uninstall
assert_removed
uninstall
pass "entire dangling trio removed and repeated uninstall is harmless"

mkdir "$current/caveman"
printf 'keep directory content\n' > "$current/caveman/keep"
printf 'keep regular file\n' > "$current/caveman-commit"
mkdir -p "$test_root/foreign/_skills/caveman-review"
ln -s "$test_root/foreign/_skills/caveman-review" "$current/caveman-review"
ln -s "../foreign/_skills/caveman" "$legacy/caveman"
ln -s "$test_root/missing-parent/caveman-commit" "$legacy/caveman-commit"
ln -s "$skills/renamed-review" "$legacy/caveman-review"
uninstall
[[ "$(cat "$current/caveman/keep")" == 'keep directory content' ]] || fail "real directory preserved"
[[ "$(cat "$current/caveman-commit")" == 'keep regular file' ]] || fail "regular file preserved"
[[ "$(readlink "$current/caveman-review")" == "$test_root/foreign/_skills/caveman-review" ]] || fail "foreign absolute link preserved"
[[ "$(readlink "$legacy/caveman")" == '../foreign/_skills/caveman' ]] || fail "foreign relative dangling link preserved"
[[ "$(readlink "$legacy/caveman-commit")" == "$test_root/missing-parent/caveman-commit" ]] || fail "unresolvable foreign parent preserved"
[[ "$(readlink "$legacy/caveman-review")" == "$skills/renamed-review" ]] || fail "different skill path preserved"
pass "real files, directories, and foreign links preserved"

# Parent aliases must be resolved before comparing checkout ownership.
current="$test_root/alias-current"
legacy="$test_root/alias-legacy"
mkdir "$current" "$legacy"
ln -s "$skills" "$test_root/managed-alias"
ln -s "$test_root/foreign/_skills" "$test_root/foreign-alias"
ln -s "$test_root/managed-alias/caveman" "$current/caveman"
ln -s "$test_root/foreign-alias/caveman" "$legacy/caveman"
uninstall
[[ ! -L "$current/caveman" ]] || fail "managed parent alias removed"
[[ -L "$legacy/caveman" ]] || fail "foreign parent alias preserved"
pass "parent symlinks retain checkout ownership checks"

printf 'All deploy uninstall tests passed.\n'
