#!/usr/bin/env bash
set -euo pipefail

# Deploy the caveman skill trio (caveman, caveman-commit, caveman-review) to an
# IDE config location so it is available across all your projects — not just this repo.
#
# Repo harness skills load on-demand (trigger match). A config-level skill is
# available everywhere but is still on-demand. To get the always-on token savings
# (caveman on EVERY response), pass --always-on, which also writes a rule/memory
# entry the IDE injects each turn.
#
# Usage:
#   deploy.sh <target> [--always-on [DIR]] [--level LVL] [--copy] [--uninstall] [--dry-run]
#   deploy.sh [target] --print [--level LVL]
#
# Targets (skill dir → override env):
#   cursor     Symlink trio into ~/.cursor/skills/     (CURSOR_SKILLS_DIR)
#   claude     Symlink trio into ~/.claude/skills/     (CLAUDE_SKILLS_DIR)
#   codex      Symlink trio into ~/.agents/skills/     (CODEX_SKILLS_DIR)
#   continue   Rules-only (no SKILL.md discovery) — writes ~/.continue/rules/caveman.md
#              (CONTINUE_RULES_DIR). VS Code / JetBrains "Continue" extension.
#
# Options:
#   --always-on [DIR]  Install the always-on activation the tool injects every turn:
#                        cursor:   <DIR>/.cursor/rules/caveman.mdc (per-project; DIR defaults to cwd)
#                        claude:   marker block in ~/.claude/CLAUDE.md   (global)   (CLAUDE_MEMORY_FILE)
#                        codex:    marker block in ~/.codex/AGENTS.md    (global)   (CODEX_AGENTS_FILE)
#                        continue: sets alwaysApply:true in the rule file (else alwaysApply:false)
#   --level LVL        Default intensity baked into the activation. One of:
#                        lite | full | ultra | wenyan-lite | wenyan-full | wenyan-ultra.
#   --print            Don't touch the filesystem — print the activation block to stdout
#                        (paste target + guidance go to stderr) so you can copy/paste it into
#                        an IDE's global "User Rules" / "Custom Instructions" box. This is the
#                        only path for non-scriptable globals like Cursor's user rules. `target`
#                        is optional and only tailors the paste hint; omit it for generic text.
#   --copy             Copy skill files instead of symlinking (not applicable to continue).
#   --uninstall        Remove the trio and any activation artifacts for the target.
#                        For cursor, pass the project DIR to also remove its rule:
#                        deploy.sh cursor --uninstall <DIR>  (DIR defaults to cwd).
#   --dry-run          Print actions without touching the filesystem.
#   -h, --help         Show this help.
#
# Notes:
#   - Symlinks point back to this repo, so edits here propagate to the deployed copy.
#   - Cursor global user rules are UI-only and cannot be scripted; --always-on for
#     cursor is per-project (.cursor/rules). For a GLOBAL cursor rule use --print and
#     paste the output into Settings → Rules → User Rules. Claude Code and Codex support
#     true global always-on via ~/.claude/CLAUDE.md and ~/.codex/AGENTS.md respectively.
#   - Continue has no SKILL.md discovery; its standing-instruction mechanism is
#     ~/.continue/rules/*.md, so `continue` always writes that rule (alwaysApply toggled
#     by --always-on) and never symlinks skills.
#   - Idempotent: safe to re-run. Marker blocks are not duplicated.

TRIO=(caveman caveman-commit caveman-review)
BEGIN_MARKER="<!-- caveman-begin -->"
END_MARKER="<!-- caveman-end -->"
CAVEMAN_LEVELS="lite full ultra wenyan-lite wenyan-full wenyan-ultra"

# Always-on rule body, mirroring caveman's own src/rules/caveman-activate.md
# (MIT, JuliusBrussee/caveman). Emits an optional leading "Start in <level>" line
# when LEVEL is set. Shared verbatim by every target's activation artifact.
rule_body() {
  if [[ -n "${LEVEL:-}" ]]; then
    printf 'Start in %s mode (as if the user ran /caveman %s).\n\n' "$LEVEL" "$LEVEL"
  fi
  cat <<'BODY'
Respond terse like smart caveman. All technical substance stay. Only fluff die.

Rules:
- Drop: articles (a/an/the), filler (just/really/basically), pleasantries, hedging
- Fragments OK. Short synonyms. Technical terms exact. Code unchanged.
- Pattern: [thing] [action] [reason]. [next step].
- Not: "Sure! I'd be happy to help you with that."
- Yes: "Bug in auth middleware. Fix:"

Switch level: /caveman lite|full|ultra|wenyan
Stop: "stop caveman" or "normal mode"

Auto-Clarity: drop caveman for security warnings, irreversible actions, user confused. Resume after.

Boundaries: code/commits/PRs written normal.
BODY
}

# Print the leading comment header as help (stops at first non-comment line).
usage() { awk '/^#!/||/^set /{next} /^#/{sub(/^# ?/,"");print;h=1;next} h{exit}' "$0"; }

# --- Resolve this repo's _skills root (skill dir is parent of scripts/) ---
script_src="${BASH_SOURCE[0]:-$0}"
script_dir="$(cd "$(dirname "$script_src")" && pwd -P)"
SKILLS_ROOT="$(cd "$script_dir/../.." && pwd -P)"
PROJECT_ROOT="$(pwd -P)"

# Resolve ALWAYS_ON_DIR to a canonical path; reject if outside PROJECT_ROOT (PWD at script start).
resolve_always_on_dir() {
  local input="${1:-$PROJECT_ROOT}"
  local dir parent

  if [[ -d "$input" ]]; then
    dir="$(cd "$input" && pwd -P)"
  elif [[ -d "$(dirname "$input")" ]]; then
    parent="$(cd "$(dirname "$input")" && pwd -P)"
    dir="$parent/$(basename "$input")"
  else
    echo "ERROR: project directory does not exist: $input" >&2
    exit 1
  fi

  case "$dir" in
    "$PROJECT_ROOT"|"$PROJECT_ROOT"/*) ;;
    *)
      echo "ERROR: project directory must be inside $PROJECT_ROOT (got: $dir)" >&2
      exit 1
      ;;
  esac
  printf '%s' "$dir"
}

run() {
  if $DRY_RUN; then
    printf '  [dry-run]'
    printf ' %q' "$@"
    echo
  else
    "$@"
  fi
}

resolve_symlink_target() {
  local link="$1"
  local target parent
  target="$(readlink "$link")" || return 1
  if [[ "$target" != /* ]]; then
    parent="$(cd "$(dirname "$link")" && pwd -P)" || return 1
    target="$parent/$target"
  fi
  # Resolve parent aliases, but do not require the final skill to still exist.
  parent="$(cd "$(dirname "$target")" 2>/dev/null && pwd -P)" || return 1
  printf '%s/%s' "$parent" "$(basename "$target")"
}

is_managed_skill_dest() {
  local dest="$1" name="$2"
  [[ -L "$dest" ]] || return 1
  local resolved expected
  resolved="$(resolve_symlink_target "$dest")" || return 1
  # SKILLS_ROOT is already physical; compare the stored path, including when
  # this checkout's source skill was deleted or renamed after deployment.
  expected="$SKILLS_ROOT/$name"
  [[ "$resolved" == "$expected" ]]
}

verify_skills_present() {
  for name in "${TRIO[@]}"; do
    if [[ ! -f "$SKILLS_ROOT/$name/SKILL.md" ]]; then
      echo "ERROR: expected skill not found: $SKILLS_ROOT/$name/SKILL.md" >&2
      exit 1
    fi
  done
}

clear_dest_for_install() {
  local dest="$1" name="$2"
  [[ ! -e "$dest" && ! -L "$dest" ]] && return 0

  if is_managed_skill_dest "$dest" "$name"; then
    run rm -f "$dest"
    return 0
  fi

  if [[ -d "$dest" && ! -L "$dest" ]]; then
    echo "ERROR: $dest is a real directory (not created by deploy.sh). Move it aside or resolve with skill-conflicts.sh." >&2
    exit 1
  fi

  if [[ -L "$dest" ]]; then
    echo "ERROR: $dest is a symlink to $(readlink "$dest"), not $SKILLS_ROOT/$name. Remove manually first." >&2
    exit 1
  fi

  run rm -f "$dest"
}

remove_managed_skill_dest() {
  local dest="$1" name="$2"
  [[ ! -e "$dest" && ! -L "$dest" ]] && return 0
  if is_managed_skill_dest "$dest" "$name"; then
    run rm -f "$dest"
    echo "  removed $dest"
  else
    echo "  skipped $dest (not managed by deploy.sh)"
  fi
}

remove_memory_block() {
  local mem="$1"
  if [[ ! -f "$mem" ]]; then
    return 0
  fi
  if grep -qF "$BEGIN_MARKER" "$mem" && ! grep -qF "$END_MARKER" "$mem"; then
    echo "WARN:  $mem has begin marker but no end marker; skipping removal (fix manually)" >&2
    return 0
  fi
  if ! grep -qF "$BEGIN_MARKER" "$mem"; then
    return 0
  fi
  if $DRY_RUN; then
    echo "  [dry-run] remove always-on block from $mem"
    return 0
  fi
  local tmp
  tmp="$(mktemp)"
  awk -v begin="$BEGIN_MARKER" -v end="$END_MARKER" '
    $0 == begin { skip=1; next }
    $0 == end { skip=0; next }
    !skip { print }
  ' "$mem" > "$tmp"
  cat "$tmp" > "$mem"
  rm -f "$tmp"
  echo "  removed always-on block from $mem"
}

write_memory_block() {
  local mem="$1"
  echo "Adding always-on block to $mem${LEVEL:+ (level=$LEVEL)}"
  run mkdir -p "$(dirname "$mem")"
  if [[ -f "$mem" ]] && grep -qF "$BEGIN_MARKER" "$mem"; then
    echo "  block already present; skipping (idempotent). Re-run --uninstall then --always-on to change level."
  elif $DRY_RUN; then
    echo "  [dry-run] append caveman block to $mem"
  else
    {
      printf '\n%s\n' "$BEGIN_MARKER"
      rule_body
      printf '%s\n' "$END_MARKER"
    } >> "$mem"
    echo "  appended block."
  fi
}

# --- Parse args ---
TARGET=""
ALWAYS_ON=false
ALWAYS_ON_DIR=""
LEVEL=""
DO_COPY=false
UNINSTALL=false
DRY_RUN=false
PRINT=false

is_target() { case "$1" in cursor|claude|codex|continue) return 0 ;; *) return 1 ;; esac; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    cursor|claude|codex|continue) TARGET="$1"; shift ;;
    --always-on)
      ALWAYS_ON=true; shift
      if [[ $# -gt 0 && "$1" != -* ]] && ! is_target "$1"; then
        ALWAYS_ON_DIR="$1"; shift
      fi
      ;;
    --level)
      shift
      [[ $# -gt 0 ]] || { echo "ERROR: --level needs a value ($CAVEMAN_LEVELS)" >&2; exit 1; }
      LEVEL="$1"; shift
      ;;
    --print) PRINT=true; shift ;;
    --copy) DO_COPY=true; shift ;;
    --uninstall) UNINSTALL=true; shift ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *)
      if [[ -n "$TARGET" && -z "$ALWAYS_ON_DIR" && "$1" != -* ]]; then
        ALWAYS_ON_DIR="$1"; shift
      else
        echo "Unknown argument: $1" >&2; echo "Run with --help." >&2; exit 1
      fi
      ;;
  esac
done

# A target is required for install/uninstall, but optional for --print (it only
# tailors the paste hint). Validate --level first so --print reports bad levels too.
if [[ -z "$TARGET" ]] && ! $PRINT; then
  echo "ERROR: no target given (cursor|claude|codex|continue). Run with --help." >&2
  exit 1
fi

if [[ -n "$LEVEL" ]]; then
  level_ok=false
  for l in $CAVEMAN_LEVELS; do [[ "$l" == "$LEVEL" ]] && level_ok=true && break; done
  if ! $level_ok; then
    echo "ERROR: invalid --level '$LEVEL' (allowed: $CAVEMAN_LEVELS)" >&2
    exit 1
  fi
fi

if [[ -n "$ALWAYS_ON_DIR" ]]; then
  ALWAYS_ON_DIR="$(resolve_always_on_dir "$ALWAYS_ON_DIR")"
fi

# --- Print mode: emit paste-ready activation, touch nothing ---
# stdout = exactly the text to paste; stderr = where to paste it.
if $PRINT; then
  case "$TARGET" in
    cursor)   dest="Cursor → Settings → Rules → User Rules (global; applies to every project)." ;;
    claude)   dest="~/.claude/CLAUDE.md (global). Scriptable alt: deploy.sh claude --always-on." ;;
    codex)    dest="~/.codex/AGENTS.md (global). Scriptable alt: deploy.sh codex --always-on." ;;
    continue) dest="Continue global rules (~/.continue/rules/caveman.md). Scriptable alt: deploy.sh continue --always-on." ;;
    *)        dest="your IDE's global \"User Rules\" / \"Custom Instructions\" box." ;;
  esac
  {
    echo "Caveman — user-level activation${LEVEL:+ (level=$LEVEL)}"
    echo "Paste the block below (stdout) into: $dest"
    echo "Note: non-scriptable globals (e.g. Cursor user rules) must be added via the UI."
    echo "------------------------------------------------------------------------"
  } >&2
  rule_body
  exit 0
fi

# --- Per-target capabilities ---
SKILLS_DIR=""
AO_KIND=""
MEM_FILE=""
case "$TARGET" in
  cursor)
    SKILLS_DIR="${CURSOR_SKILLS_DIR:-$HOME/.cursor/skills}"
    AO_KIND="cursor-rule" ;;
  claude)
    SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
    AO_KIND="memory-block"; MEM_FILE="${CLAUDE_MEMORY_FILE:-$HOME/.claude/CLAUDE.md}" ;;
  codex)
    SKILLS_DIR="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
    CODEX_LEGACY_SKILLS_DIR="${CODEX_LEGACY_SKILLS_DIR:-$HOME/.codex/skills}"
    AO_KIND="memory-block"; MEM_FILE="${CODEX_AGENTS_FILE:-$HOME/.codex/AGENTS.md}" ;;
  continue)
    AO_KIND="continue-rule"; CONTINUE_RULES_DIR="${CONTINUE_RULES_DIR:-$HOME/.continue/rules}" ;;
esac

if [[ -z "$SKILLS_DIR" ]] && $DO_COPY; then
  echo "WARN:  --copy has no effect for $TARGET (rules-only target)." >&2
fi
if [[ -n "$LEVEL" ]] && ! $ALWAYS_ON && [[ "$AO_KIND" != "continue-rule" ]]; then
  echo "WARN:  --level only affects the always-on activation; add --always-on to apply it." >&2
fi

# --- Uninstall ---
if $UNINSTALL; then
  echo "Uninstalling caveman trio from $TARGET"
  if [[ -n "$SKILLS_DIR" ]]; then
    for name in "${TRIO[@]}"; do
      remove_managed_skill_dest "$SKILLS_DIR/$name" "$name"
    done
  fi
  if [[ "$TARGET" == "codex" && "${CODEX_LEGACY_SKILLS_DIR:-}" != "$SKILLS_DIR" ]]; then
    for name in "${TRIO[@]}"; do
      remove_managed_skill_dest "$CODEX_LEGACY_SKILLS_DIR/$name" "$name"
    done
  fi

  case "$AO_KIND" in
    cursor-rule)
      rule_file="$(resolve_always_on_dir "${ALWAYS_ON_DIR:-}")/.cursor/rules/caveman.mdc"
      if [[ -f "$rule_file" ]]; then
        run rm -f "$rule_file"
        echo "  removed always-on rule $rule_file"
      fi ;;
    memory-block) remove_memory_block "$MEM_FILE" ;;
    continue-rule)
      rule_file="$CONTINUE_RULES_DIR/caveman.md"
      if [[ -f "$rule_file" ]]; then
        run rm -f "$rule_file"
        echo "  removed rule $rule_file"
      fi ;;
  esac
  echo "Done."
  exit 0
fi

# --- Continue: rules-only target (no skill symlinks) ---
if [[ "$AO_KIND" == "continue-rule" ]]; then
  rule_file="$CONTINUE_RULES_DIR/caveman.md"
  always="$($ALWAYS_ON && echo true || echo false)"
  echo "Writing Continue rule: $rule_file (alwaysApply=$always${LEVEL:+, level=$LEVEL})"
  run mkdir -p "$CONTINUE_RULES_DIR"
  if $DRY_RUN; then
    echo "  [dry-run] write $rule_file"
  else
    {
      printf -- '---\n'
      printf 'name: caveman\n'
      printf 'alwaysApply: %s\n' "$always"
      printf 'description: Ultra-compressed caveman output mode (~75%% fewer tokens); terse, keeps code and technical terms exact.\n'
      printf -- '---\n\n'
      rule_body
    } > "$rule_file"
  fi
  $ALWAYS_ON || echo "  note: alwaysApply:false — Continue pulls this in by description. Use --always-on for every-turn savings."
  echo "Done."
  exit 0
fi

verify_skills_present

# --- Install skills (cursor / claude / codex) ---
echo "Deploying caveman trio to $TARGET ($SKILLS_DIR)"
run mkdir -p "$SKILLS_DIR"

for name in "${TRIO[@]}"; do
  src="$SKILLS_ROOT/$name"
  dest="$SKILLS_DIR/$name"

  clear_dest_for_install "$dest" "$name"

  if $DO_COPY; then
    run cp -R "$src" "$dest"
    echo "  copied  $name -> $dest"
  else
    run ln -s "$src" "$dest"
    echo "  linked  $name -> $dest"
  fi
done

# --- Always-on activation ---
if $ALWAYS_ON; then
  case "$AO_KIND" in
    cursor-rule)
      proj="$(resolve_always_on_dir "${ALWAYS_ON_DIR:-}")"
      rule_dir="$proj/.cursor/rules"
      rule_file="$rule_dir/caveman.mdc"
      echo "Writing always-on rule: $rule_file (per-project${LEVEL:+, level=$LEVEL})"
      run mkdir -p "$rule_dir"
      if $DRY_RUN; then
        echo "  [dry-run] write $rule_file"
      else
        {
          printf -- '---\n'
          printf 'description: Always-on caveman compression%s\n' "${LEVEL:+ ($LEVEL)}"
          printf 'alwaysApply: true\n'
          printf -- '---\n\n'
          rule_body
        } > "$rule_file"
      fi
      echo "  note: Cursor global user rules are UI-only; this rule applies to $proj only." ;;
    memory-block) write_memory_block "$MEM_FILE" ;;
  esac
else
  echo "Skills installed on-demand (trigger match). Re-run with --always-on for every-response savings."
fi

echo "Done."
