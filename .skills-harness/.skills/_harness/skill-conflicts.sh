#!/usr/bin/env bash
set -euo pipefail

# Detect conflicts between skills managed by THIS repo (.skills/_skills/<name>)
# and same-named skills or slash-commands in the user's IDE config.
#
# Why: user-level config (e.g. ~/.cursor/skills/, ~/.claude/skills/) is discovered
# alongside this repo's skills. When the same NAME exists in both places with
# different content, it is ambiguous which definition wins — a silent conflict.
# A user-config entry that is a symlink back into this repo is NOT a conflict;
# it is the same skill, deployed from here (e.g. by caveman/scripts/deploy.sh).
#
# Usage: skill-conflicts.sh [--quiet]
#
# Config locations scanned (override via env):
#   SKILLS_HARNESS_DIR     (default: script dir, logical path via pwd -L)
#   SKILLS_DIR             (default: ../_skills relative to harness)
#   CURSOR_SKILLS_DIR      (default ~/.cursor/skills)
#   CLAUDE_SKILLS_DIR      (default ~/.claude/skills)
#   CODEX_SKILLS_DIR       (default ~/.agents/skills)
#   CODEX_LEGACY_SKILLS_DIR (default ~/.codex/skills; migration scan only)
#   CURSOR_COMMANDS_DIR    (default ~/.cursor/commands)
#   CLAUDE_COMMANDS_DIR    (default ~/.claude/commands)
#   CODEX_PROMPTS_DIR      (default ~/.codex/prompts)   Codex custom prompts (/name)
#
# Continue is rules-only (no SKILL.md discovery), so it has nothing that can
# shadow a repo skill by name and is intentionally not scanned here.
#
# Exit status: 0 = no conflicts (clean or only managed symlinks / identical copies),
#              1 = at least one CONFLICT (divergent same-named definition).

QUIET=false
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=true ;;
    -h|--help)
      awk '/^#!/||/^set /{next} /^#/{sub(/^# ?/,"");print;h=1;next} h{exit}' "$0"
      exit 0 ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# Resolve without following symlinks so subtree-vendored installs (where
# .skills/_harness/ → .skills-harness/.skills/_harness/) still scan the
# consumer's .skills/_skills/ rather than the kit subtree's. See gh issue #14.
script_src="${BASH_SOURCE[0]:-$0}"
script_dir="$(dirname "$script_src")"
HARNESS_DIR="${SKILLS_HARNESS_DIR:-$(cd "$script_dir" && pwd -L)}"
SKILLS_DIR="${SKILLS_DIR:-$(dirname "$HARNESS_DIR")/_skills}"

CURSOR_SKILLS_DIR="${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}"
CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CODEX_SKILLS_DIR="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
CODEX_LEGACY_SKILLS_DIR="${CODEX_LEGACY_SKILLS_DIR:-$HOME/.codex/skills}"
CURSOR_COMMANDS_DIR="${CURSOR_COMMANDS_DIR:-$HOME/.cursor/commands}"
CLAUDE_COMMANDS_DIR="${CLAUDE_COMMANDS_DIR:-$HOME/.claude/commands}"
CODEX_PROMPTS_DIR="${CODEX_PROMPTS_DIR:-$HOME/.codex/prompts}"

conflicts=0
managed=0
warnings=0

note() { $QUIET || echo "$1"; }
conflict() { echo "CONFLICT: $1" >&2; conflicts=$((conflicts + 1)); }
warn() { echo "WARN:  $1" >&2; warnings=$((warnings + 1)); }

# Physical (symlink-resolved) path of a directory, or empty if it doesn't exist.
canon_dir() { ( cd "$1" 2>/dev/null && pwd -P ) || true; }

# --- Collect repo-managed skills (exclude harness internals and backups) ---
skill_names=()
if [[ -d "$SKILLS_DIR" ]]; then
  for d in "$SKILLS_DIR"/*/; do
    [[ -d "$d" ]] || continue
    n="$(basename "$d")"
    case "$n" in _*|*.bak) continue ;; esac
    [[ -f "$d/SKILL.md" ]] || continue
    skill_names+=("$n")
  done
fi

if [[ ${#skill_names[@]} -eq 0 ]]; then
  note "No repo-managed skills found under $SKILLS_DIR."
  exit 0
fi

note "Scanning ${#skill_names[@]} repo-managed skill(s) against user config…"
note ""

if [[ -d "$CODEX_LEGACY_SKILLS_DIR" && "$CODEX_LEGACY_SKILLS_DIR" != "$CODEX_SKILLS_DIR" ]]; then
  warn "legacy Codex skill directory detected: $CODEX_LEGACY_SKILLS_DIR (migrate user skills to $CODEX_SKILLS_DIR)"
fi

# --- Skill-vs-skill collisions (directory targets) ---
check_skill_dir() {
  local label="$1" base="$2" name="$3"
  local user_path="$base/$name"
  [[ -e "$user_path" || -L "$user_path" ]] || return 0

  local repo_phys user_phys
  repo_phys="$(canon_dir "$SKILLS_DIR/$name")"
  user_phys="$(canon_dir "$user_path")"

  if [[ -n "$repo_phys" && "$user_phys" == "$repo_phys" ]]; then
    note "  OK   $label/$name → managed (symlink resolves into this repo)"
    managed=$((managed + 1))
    return 0
  fi

  if [[ -f "$user_path/SKILL.md" && -f "$SKILLS_DIR/$name/SKILL.md" ]] \
     && cmp -s "$user_path/SKILL.md" "$SKILLS_DIR/$name/SKILL.md"; then
    warn "$label/$name is an independent COPY with identical SKILL.md (drift risk; re-run deploy with symlink to keep in sync): $user_path"
    return 0
  fi

  conflict "$label/$name shadows repo skill with a DIFFERENT definition: $user_path"
}

# --- Skill-vs-command collisions (a /name command shares the slash menu with /skill) ---
check_command() {
  local label="$1" base="$2" name="$3"
  local cmd="$base/$name.md"
  [[ -e "$cmd" || -L "$cmd" ]] || return 0
  conflict "$label command /$name collides with repo skill '$name' in the slash menu: $cmd"
}

for name in "${skill_names[@]}"; do
  check_skill_dir "cursor:skills" "$CURSOR_SKILLS_DIR" "$name"
  check_skill_dir "claude:skills" "$CLAUDE_SKILLS_DIR" "$name"
  check_skill_dir "codex:skills"  "$CODEX_SKILLS_DIR"  "$name"
  if [[ "$CODEX_LEGACY_SKILLS_DIR" != "$CODEX_SKILLS_DIR" ]]; then
    check_skill_dir "codex:skills:legacy" "$CODEX_LEGACY_SKILLS_DIR" "$name"
  fi
  check_command   "cursor:commands" "$CURSOR_COMMANDS_DIR" "$name"
  check_command   "claude:commands" "$CLAUDE_COMMANDS_DIR" "$name"
  check_command   "codex:prompts"   "$CODEX_PROMPTS_DIR"   "$name"
done

# --- Summary ---
note ""
if (( conflicts == 0 )); then
  $QUIET || echo "No conflicts. (managed symlinks: $managed, copy warnings: $warnings)"
else
  echo "$conflicts conflict(s) found (managed symlinks: $managed, copy warnings: $warnings)." >&2
  exit 1
fi
