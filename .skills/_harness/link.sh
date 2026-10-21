#!/usr/bin/env sh
# Creates symlinks from a target directory into .skills/_skills/ so IDEs
# with native skill discovery can find harness-managed skills.
#
# Usage: .skills/_harness/link.sh [--clean] [--no-record] <target-dir>
#        .skills/_harness/link.sh <target-dir> [--clean] [--no-record]
#
#   <target-dir>  Relative path from repo root (e.g. .agents/skills)
#   --clean       Remove existing symlinks in target before creating
#   --no-record   Do not persist the target under native_targets in _meta.yml

set -eu

HARNESS_DIR="${SKILLS_HARNESS_DIR:-$(cd "$(dirname "$0")" && pwd)}"
SKILLS_DIR="${SKILLS_DIR:-$(dirname "$HARNESS_DIR")/_skills}"
REPO_ROOT="${SKILLS_REPO_ROOT:-$(dirname "$(dirname "$HARNESS_DIR")")}"
META_FILE="${SKILLS_META:-$(dirname "$HARNESS_DIR")/_meta.yml}"

usage() {
  echo "Usage: $(basename "$0") [--clean] [--no-record] <target-dir>" >&2
  echo "  <target-dir>  Relative path from repo root (e.g. .agents/skills)" >&2
  exit 1
}

TARGET_REL=""
CLEAN=false
RECORD=true
for arg in "$@"; do
  case "$arg" in
    --clean) CLEAN=true ;;
    --no-record) RECORD=false ;;
    -*)      echo "Unknown option: $arg" >&2; usage ;;
    *)
      [ -n "$TARGET_REL" ] && usage
      TARGET_REL="$arg"
      ;;
  esac
done
[ -z "$TARGET_REL" ] && usage

TARGET_REL="${TARGET_REL#./}"
TARGET_REL="${TARGET_REL%/}"
case "$TARGET_REL" in
  ""|.|/*|..|../*|*/../*|*/..)
    echo "ERROR: target must be a safe path relative to the repo root: $TARGET_REL" >&2
    exit 1
    ;;
esac

TARGET_ABS="$REPO_ROOT/$TARGET_REL"

assert_target_within_repo() {
  link_repo_phys="$(cd "$REPO_ROOT" && pwd -P)" || exit 1
  link_probe="$TARGET_ABS"

  # Resolve the nearest existing ancestor before mkdir follows any symlinked
  # path component. Lexical '..' checks alone do not prevent symlink escapes.
  while [ ! -e "$link_probe" ] && [ ! -L "$link_probe" ]; do
    link_parent="$(dirname "$link_probe")"
    [ "$link_parent" = "$link_probe" ] && break
    link_probe="$link_parent"
  done

  if [ ! -d "$link_probe" ]; then
    echo "ERROR: target ancestor is not a directory: $link_probe" >&2
    exit 1
  fi
  link_probe_phys="$(cd "$link_probe" && pwd -P)" || exit 1
  case "$link_probe_phys" in
    "$link_repo_phys"|"$link_repo_phys"/*) ;;
    *)
      echo "ERROR: target resolves outside repo root through '$link_probe': $TARGET_REL" >&2
      exit 1
      ;;
  esac
}

record_native_target() {
  if [ ! -f "$META_FILE" ]; then
    echo "WARNING: $META_FILE not found; linked target cannot be persisted" >&2
    return 0
  fi

  if awk -v target="$TARGET_REL" '
    /^native_targets:[[:space:]]*$/ { in_targets=1; next }
    in_targets && /^[^[:space:]#][^:]*:/ { in_targets=0 }
    in_targets && /^[[:space:]]*-[[:space:]]*/ {
      value=$0
      sub(/^[[:space:]]*-[[:space:]]*/, "", value)
      gsub(/^["'"'']|["'"'']$/, "", value)
      if (value == target) found=1
    }
    END { exit(found ? 0 : 1) }
  ' "$META_FILE"; then
    return 0
  fi

  if grep -qE '^native_targets:[[:space:]]*\[' "$META_FILE"; then
    echo "ERROR: $META_FILE uses unsupported flow-style native_targets; use a block list" >&2
    exit 1
  fi

  tmp_meta="$(mktemp)"
  mode="644"
  if stat -f '%Lp' "$META_FILE" >/dev/null 2>&1; then
    mode="$(stat -f '%Lp' "$META_FILE")"
  elif stat -c '%a' "$META_FILE" >/dev/null 2>&1; then
    mode="$(stat -c '%a' "$META_FILE")"
  fi

  awk -v target="$TARGET_REL" '
    BEGIN { in_targets=0; saw_targets=0; inserted=0 }
    /^native_targets:[[:space:]]*$/ {
      saw_targets=1
      in_targets=1
      print
      next
    }
    in_targets && /^[^[:space:]#][^:]*:/ {
      print "  - " target
      inserted=1
      in_targets=0
    }
    { print }
    END {
      if (in_targets && !inserted) print "  - " target
      if (!saw_targets) {
        print "native_targets:"
        print "  - " target
      }
    }
  ' "$META_FILE" > "$tmp_meta"
  chmod "$mode" "$tmp_meta"
  mv "$tmp_meta" "$META_FILE"
  echo "  recorded $TARGET_REL in .skills/_meta.yml native_targets"
}

assert_target_within_repo

case "$(uname -s)" in
  MINGW*|MSYS*|CYGWIN*)
    echo "WARNING: Symlinks on Windows require 'git config core.symlinks true'" >&2
    echo "         and may need elevated privileges." >&2
    ;;
esac

mkdir -p "$TARGET_ABS"

# Persist before --clean removes anything. Invalid metadata must not turn a
# repair operation into a partially destructive one.
if $RECORD; then
  record_native_target
fi

if $CLEAN && [ -d "$TARGET_ABS" ]; then
  for item in "$TARGET_ABS"/*; do
    [ -e "$item" ] || [ -L "$item" ] || continue
    [ ! -L "$item" ] && continue
    rm -f "$item"
    echo "  removed  $TARGET_REL/$(basename "$item")"
  done
fi

# Compute relative path from target back to .skills/_skills.
# Each segment in TARGET_REL needs one "../" to climb back to repo root.
rel_prefix=""
tmp="$TARGET_REL"
while [ "$tmp" != "." ] && [ -n "$tmp" ]; do
  rel_prefix="../$rel_prefix"
  parent="$(dirname "$tmp")"
  [ "$parent" = "$tmp" ] && break
  tmp="$parent"
done
REL_SKILLS="${rel_prefix}.skills/_skills"

linked=0
skipped=0
updated=0
pruned=0

for skill_dir in "$SKILLS_DIR"/*/; do
  [ ! -d "$skill_dir" ] && continue
  name="$(basename "$skill_dir")"

  # Harness internals and migration backups are not discoverable skills.
  case "$name" in
    _*|*.bak) continue ;;
  esac

  target_link="$TARGET_ABS/$name"
  expected_target="$REL_SKILLS/$name"

  if [ -L "$target_link" ]; then
    actual_target="$(readlink "$target_link")"
    if [ "$actual_target" = "$expected_target" ]; then
      skipped=$((skipped + 1))
      continue
    fi
    echo "  update  $TARGET_REL/$name (was -> $actual_target)"
    rm -f "$target_link"
    ln -s "$expected_target" "$target_link"
    updated=$((updated + 1))
    continue
  fi

  if [ -e "$target_link" ]; then
    echo "  SKIP  $TARGET_REL/$name (not a symlink)" >&2
    skipped=$((skipped + 1))
    continue
  fi

  ln -s "$expected_target" "$target_link"
  echo "  linked  $TARGET_REL/$name"
  linked=$((linked + 1))
done

# Remove inactive links created by older helpers, without touching the backup
# source, real native entries, or foreign links with a similar name.
for item in "$TARGET_ABS"/*; do
  [ -L "$item" ] || continue
  name="$(basename "$item")"
  case "$name" in
    _*|*.bak)
      if [ "$(readlink "$item")" = "$REL_SKILLS/$name" ]; then
        rm -f "$item"
        echo "  pruned  $TARGET_REL/$name (inactive backup/internal directory)"
        pruned=$((pruned + 1))
      fi
      ;;
  esac
done

# Prune dangling symlinks (targets that no longer exist)
for item in "$TARGET_ABS"/*; do
  [ -e "$item" ] || [ -L "$item" ] || continue
  [ ! -L "$item" ] && continue
  if [ ! -e "$item" ]; then
    link_target="$(readlink "$item")"
    echo "  pruned  $TARGET_REL/$(basename "$item") (dangling -> $link_target)"
    rm -f "$item"
    pruned=$((pruned + 1))
  fi
done

echo ""
summary="Done: $linked linked, $skipped unchanged"
if [ "$updated" -gt 0 ]; then
  summary="$summary, $updated updated"
fi
if [ "$pruned" -gt 0 ]; then
  summary="$summary, $pruned pruned"
fi
echo "$summary."
if [ "$linked" -gt 0 ]; then
  echo "Ensure '$TARGET_REL/' is in .gitignore."
fi
