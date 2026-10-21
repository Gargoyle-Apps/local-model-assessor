#!/usr/bin/env bash
set -euo pipefail

# Generates single or opt-in split indexes from local SKILL.md frontmatter.
# Dry-run by default (prints drift, exits non-zero); --write performs edits.
#
# Usage: .skills/_harness/build-index.sh [--write|--dry-run]
# See index-layout.md for grouping, ownership, and migration.

script_src="${BASH_SOURCE[0]:-$0}"
# Keep consumer paths logical even when Bash inherits the physical option.
HARNESS_DIR="${SKILLS_HARNESS_DIR:-$(cd -L "$(dirname "$script_src")" && pwd -L)}"
SKILLS_DIR="${SKILLS_DIR:-$(dirname "$HARNESS_DIR")/_skills}"
INDEX_FILE="${SKILLS_INDEX:-$(dirname "$HARNESS_DIR")/_index.md}"
META_FILE="${SKILLS_META:-$(dirname "$HARNESS_DIR")/_meta.yml}"
export LC_ALL=C

WRITE=false
for arg in "$@"; do
  case "$arg" in
    --write) WRITE=true ;;
    --dry-run) WRITE=false ;;
    -h|--help) echo "Usage: $0 [--write|--dry-run]"; exit 0 ;;
    *) echo "ERROR: unknown argument: $arg" >&2; exit 2 ;;
  esac
done

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

strip_quotes() {
  local v="$1"
  v="${v#\"}"
  v="${v%\"}"
  v="${v#\'}"
  v="${v%\'}"
  printf '%s' "$v"
}

# Only grouping identifiers are parsed here, never arbitrary YAML or shell.
# Preserve # inside quotes and require whitespace before an inline comment.
parse_index_scalar() {
  local raw quote rest tail
  raw="$(trim "$1")"
  parsed_scalar=""
  case "$raw" in
    \"*|\'*)
      quote="${raw:0:1}"
      rest="${raw:1}"
      [[ "$rest" == *"$quote"* ]] || return 1
      parsed_scalar="${rest%%"$quote"*}"
      tail="${rest#*"$quote"}"
      if [[ -n "$tail" ]]; then
        [[ "$tail" == [[:space:]]* ]] || return 1
        tail="$(trim "$tail")"
        [[ -z "$tail" || "$tail" == \#* ]] || return 1
      fi ;;
    \#*) ;;
    *) parsed_scalar="$(trim "${raw%%[[:space:]]#*}")" ;;
  esac
}

safe_index_name() {
  [[ "$1" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ && "$1" != *--* ]]
}

strip_trailing_newlines() {
  local s="$1"
  while [[ "$s" == *$'\n' ]]; do
    s="${s%$'\n'}"
  done
  printf '%s' "$s"
}

escape_table_cell() {
  local v="$1"
  v="${v//$'\n'/ }"
  v="${v//|/\\|}"
  printf '%s' "$v"
}

parse_triggers_inline() {
  local val="$1"
  local inner item result="" rest
  inner="${val#\[}"
  inner="${inner%\]}"
  rest="$inner"
  while [[ -n "$rest" ]]; do
    if [[ "$rest" == *,* ]]; then
      item="${rest%%,*}"
      rest="${rest#*,}"
    else
      item="$rest"
      rest=""
    fi
    item="$(strip_quotes "$(trim "$item")")"
    [[ -z "$item" ]] && continue
    if [[ -n "$result" ]]; then
      result="$result, $item"
    else
      result="$item"
    fi
  done
  printf '%s' "$result"
}

parse_triggers_block_lines() {
  local result="" line tline item
  while [[ $# -gt 0 ]]; do
    line="$1"
    shift
    tline="$(trim "$line")"
    [[ "$tline" != -* ]] && break
    item="${tline#- }"
    item="$(strip_quotes "$(trim "$item")")"
    if [[ -n "$result" ]]; then
      result="$result, $item"
    else
      result="$item"
    fi
  done
  printf '%s' "$result"
}

parse_skill_frontmatter() {
  local skill_file="$1"
  fm_name="" fm_desc="" fm_triggers=""
  local in_fm=false
  local -a fm_lines=()

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == "---" ]]; then
      if $in_fm; then break
      else in_fm=true; continue
      fi
    fi
    if $in_fm; then
      fm_lines+=("$line")
    fi
  done < "$skill_file"

  local idx=0 line key val tline item
  while (( idx < ${#fm_lines[@]} )); do
    line="${fm_lines[idx]}"
    [[ "$line" == [[:space:]]* ]] && { idx=$((idx + 1)); continue; }
    key="${line%%:*}"
    key="$(trim "$key")"
    val="${line#*:}"
    val="$(strip_quotes "$(trim "$val")")"

    case "$key" in
      name) fm_name="$val" ;;
      description) fm_desc="$val" ;;
      triggers)
        if [[ "$val" =~ ^\[.*\]$ ]]; then
          fm_triggers="$(parse_triggers_inline "$val")"
        elif [[ -z "$val" ]]; then
          local -a trigger_lines=()
          ((idx++)) || true
          while (( idx < ${#fm_lines[@]} )); do
            tline="$(trim "${fm_lines[idx]}")"
            [[ "$tline" != -* ]] && { idx=$((idx - 1)); break; }
            trigger_lines+=("${fm_lines[idx]}")
            ((idx++)) || true
          done
          if ((${#trigger_lines[@]} > 0)); then
            fm_triggers="$(parse_triggers_block_lines "${trigger_lines[@]}")"
          fi
        fi
        ;;
    esac
    idx=$((idx + 1))
  done
}

fail() { echo "ERROR: $*" >&2; exit 2; }
[[ -d "$SKILLS_DIR" ]] || fail "_skills directory not found at $SKILLS_DIR"
[[ -f "$INDEX_FILE" ]] || fail "_index.md not found at $INDEX_FILE"
[[ ! -L "$INDEX_FILE" ]] || fail "refusing symlink index: $INDEX_FILE"

# Deliberately constrained metadata syntax, like native_targets: plain scalars
# and a block list. No eval, YAML dependencies, user-controlled paths, or globs.
layout=single
fallback=""
prefixes=()
prefix_config_error=""
fallback_config_error=""
if [[ -f "$META_FILE" ]]; then
  in_prefixes=false
  seen_layout=false
  seen_fallback=false
  seen_prefixes=false
  prefix_indent=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$(trim "$line")" || "$(trim "$line")" == \#* ]] && continue
    # Permit ordinary YAML spacing before the colon without accepting an
    # unseparated value such as index_layout:split as a mapping declaration.
    if [[ "$line" =~ ^(index_layout|index_fallback|prefixes)[[:space:]]*:(.*)$ ]]; then
      config_key="${BASH_REMATCH[1]}"
      config_value="${BASH_REMATCH[2]}"
      if [[ -n "$config_value" && "$config_value" != [[:space:]]* ]]; then
        case "$config_key" in
          index_layout) fail "index_layout requires a space after the colon" ;;
          index_fallback) fallback_config_error="index_fallback requires a space after the colon" ;;
          prefixes) prefix_config_error="prefixes requires a space after the colon" ;;
        esac
      fi
      line="$config_key:$config_value"
    fi
    case "$line" in
      index_layout:*)
        $seen_layout && fail "duplicate index_layout"
        seen_layout=true
        parse_index_scalar "${line#*:}" || fail "malformed index_layout scalar"
        layout="$parsed_scalar" ;;
      index_fallback:*)
        $seen_fallback && fail "duplicate index_fallback"
        seen_fallback=true
        parse_index_scalar "${line#*:}" || fallback_config_error="malformed index_fallback scalar"
        fallback="$parsed_scalar" ;;
    esac
    if [[ "$line" == prefixes:* ]]; then
      $seen_prefixes && prefix_config_error="duplicate prefixes declaration"
      seen_prefixes=true
      prefix_header="$(trim "${line#*:}")"
      if ! parse_index_scalar "$prefix_header" || [[ -n "$parsed_scalar" || "$prefix_header" == \"* || "$prefix_header" == \'* ]]; then
        prefix_config_error="split index prefixes must use a block list"
      fi
      in_prefixes=true
      prefix_indent=""
      continue
    fi
    if $in_prefixes; then
      if [[ "$line" =~ ^[^[:space:]#-][^:]*: ]]; then
        in_prefixes=false
        continue
      fi
      if [[ "$line" =~ ^([[:space:]]*)-[[:space:]]+(.*)$ ]]; then
        current_indent="${BASH_REMATCH[1]}"
        prefix_value="${BASH_REMATCH[2]}"
        [[ "$current_indent" != *$'\t'* ]] || prefix_config_error="prefixes must use spaces for indentation"
        if [[ -z "$prefix_indent" ]]; then prefix_indent="x$current_indent"
        elif [[ "$prefix_indent" != "x$current_indent" ]]; then prefix_config_error="prefixes must use one list indentation level"
        fi
        if parse_index_scalar "$prefix_value"; then prefixes+=("$parsed_scalar")
        else prefix_config_error="malformed scalar in prefixes block list"
        fi
      else
        prefix_config_error="malformed prefixes block list: expected - prefix- entries"
      fi
    fi
  done < "$META_FILE"
fi
case "$layout" in single|split) ;; *) fail "unknown index_layout '$layout'" ;; esac

INDEX_DIR="$(dirname "$INDEX_FILE")"
CHILD_DIR="$INDEX_DIR/_indexes"
[[ ! -L "$CHILD_DIR" ]] || fail "refusing symlink index directory: $CHILD_DIR"
groups=()
if [[ "$layout" == split ]]; then
  [[ -z "$prefix_config_error" ]] || fail "$prefix_config_error"
  [[ -z "$fallback_config_error" ]] || fail "$fallback_config_error"
  safe_index_name "$fallback" || fail "split layout requires a safe index_fallback group (for example: kit)"
  groups+=("$fallback")
  checked_prefixes=()
  for prefix in ${prefixes[@]+"${prefixes[@]}"}; do
    [[ "$prefix" == *- ]] && safe_index_name "${prefix%-}" || fail "unsafe family prefix '$prefix'"
    for old in ${checked_prefixes[@]+"${checked_prefixes[@]}"}; do
      [[ "$old" == "$prefix"* || "$prefix" == "$old"* ]] && fail "duplicate or overlapping prefixes '$old' and '$prefix'"
    done
    checked_prefixes+=("$prefix")
    group="${prefix%-}"
    [[ "$group" != "$fallback" ]] || fail "index_fallback collides with prefix group '$group'"
    groups+=("$group")
  done
fi

stage="$(mktemp -d)"
trap 'rm -rf "$stage"' EXIT
trap 'exit 2' HUP INT TERM
mkdir "$stage/rows" "$stage/output"
: > "$stage/rows/single"
for group in ${groups[@]+"${groups[@]}"}; do : > "$stage/rows/$group"; done

# Shell glob ordering is deterministic under LC_ALL=C. Local frontmatter is
# authoritative for kit symlinks and consumer skills alike.
for skill_dir in "$SKILLS_DIR"/*/; do
  [[ -d "$skill_dir" ]] || continue
  name="$(basename "$skill_dir")"
  case "$name" in _*|*.bak) continue ;; esac
  skill_file="$skill_dir/SKILL.md"
  [[ -f "$skill_file" ]] || fail "missing SKILL.md for '$name'"
  parse_skill_frontmatter "$skill_file"
  [[ "$fm_name" == "$name" && ${#name} -le 64 ]] && safe_index_name "$name" || fail "frontmatter name must match safe directory name '$name'"
  [[ -n "$fm_desc" ]] || fail "missing description for '$name'"
  group=single
  if [[ "$layout" == split ]]; then
    group="$fallback"
    for prefix in ${prefixes[@]+"${prefixes[@]}"}; do
      [[ "$name" == "$prefix"* ]] && group="${prefix%-}" && break
    done
  fi
  printf '| %s | %s | %s |\n' "$(escape_table_cell "$fm_name")" "$(escape_table_cell "$fm_desc")" "$(escape_table_cell "$fm_triggers")" >> "$stage/rows/$group"
done

BEGIN_MARK='<!-- BEGIN GENERATED SKILL INDEX -->'
END_MARK='<!-- END GENERATED SKILL INDEX -->'

# Replace only a balanced owned block, or the one legacy skill table in the
# root. Reject extra tables anywhere, including outside generated markers.
render() {
  local source="$1" body="$2" target="$3" root="$4"
  if [[ ! -e "$source" && ! -L "$source" ]]; then
    [[ "$root" == false ]] || fail "missing root index"
    printf '# %s skills\n\n%s\n' "$(basename "$source" .md)" "$BEGIN_MARK" > "$target"
    cat "$body" >> "$target"
    printf '%s\n' "$END_MARK" >> "$target"
    return
  fi
  [[ -f "$source" && ! -L "$source" ]] || fail "refusing non-regular index: $source"
  [[ -s "$source" ]] || fail "unowned index: empty file at $source"
  awk -v body="$body" -v begin="$BEGIN_MARK" -v end="$END_MARK" -v root="$root" '
    function error(message) { print "ERROR: " FILENAME ": " message > "/dev/stderr"; bad=1 }
    function emit(   line) { while ((getline line < body)>0) print line; close(body) }
    FNR==NR {
      if ($0==begin) { starts++; inside=1 }
      if ($0==end) { ends++; if (!inside) error("unexpected generated end marker"); inside=0 }
      if ($0 ~ /^[[:space:]]*\|[[:space:]]*name[[:space:]]*\|/) {
        tables++; if (!inside) outside++
      }
      next
    }
    FNR==1 {
      if (starts!=ends || starts>1) error("unbalanced or duplicate generated markers")
      if (tables>1) error("legacy multiple skill tables: consolidate manually while preserving routing prose; no files written")
      if (starts && outside) error("skill table outside generated block")
      if (!starts && (root!="true" || tables!=1)) error("unowned index: expected generated markers or one root skill table")
      if (bad) exit 2
    }
    starts {
      if ($0==begin) { print; emit(); skipping=1; next }
      if ($0==end) { skipping=0; print; next }
      if (!skipping) print
      next
    }
    /^[[:space:]]*\|[[:space:]]*name[[:space:]]*\|/ {
      if (root=="true" && split_mode) { print begin; emit(); print end }
      else emit()
      skipping=1; next
    }
    skipping && /^[[:space:]]*\|/ { next }
    { skipping=0; print }
  ' split_mode="$([[ "$layout" == split ]] && echo 1 || echo 0)" "$source" "$source" > "$target" || fail "cannot generate $source"
}

table() {
  printf '| name | description | triggers |\n|------|-------------|----------|\n'
  cat "$1"
}

# Refuse orphaned managed children rather than silently deleting their prose.
# Non-managed unrelated files are never touched.
if [[ -d "$CHILD_DIR" ]]; then
  for child in "$CHILD_DIR"/*.md; do
    [[ -e "$child" || -L "$child" ]] || continue
    if [[ -L "$child" && ! -e "$child" ]]; then
      fail "refusing non-regular index: $child (dangling symlink; ownership cannot be checked, move/remove explicitly)"
    fi
    # An unrelated directory or other non-file cannot contain an owned table.
    [[ -f "$child" ]] || continue
    if grep -qF "$BEGIN_MARK" "$child"; then
      known=false
      for group in ${groups[@]+"${groups[@]}"}; do
        [[ "$child" == "$CHILD_DIR/$group.md" ]] && known=true
      done
      $known || fail "unknown generated group: $child; archive its prose and remove/move the file explicitly"
    fi
  done
fi

outputs=("$INDEX_FILE")
staged=("$stage/output/root")
if [[ "$layout" == single ]]; then
  table "$stage/rows/single" > "$stage/body"
else
  : > "$stage/body"
  for group in "${groups[@]}"; do
    count="$(wc -l < "$stage/rows/$group" | tr -d '[:space:]')"
    printf -- '- [%s](%s) — %s skills\n' "$group" "_indexes/$group.md" "$count" >> "$stage/body"
    table "$stage/rows/$group" > "$stage/child-body"
    render "$CHILD_DIR/$group.md" "$stage/child-body" "$stage/output/$group.md" false
    outputs+=("$CHILD_DIR/$group.md")
    staged+=("$stage/output/$group.md")
  done
fi
render "$INDEX_FILE" "$stage/body" "$stage/output/root" true

drift=false
for ((i=0; i<${#outputs[@]}; i++)); do
  target="${outputs[i]}"
  if ! cmp -s "${staged[i]}" "$target"; then
    drift=true
    echo "Index changes: $target"
    if [[ -f "$target" ]]; then
      diff -u "$target" "${staged[i]}" || true
    else
      diff -u /dev/null "${staged[i]}" || true
    fi
  fi
done
if ! $drift; then
  echo "Indexes are in sync with local skill frontmatter."
  exit 0
fi
if ! $WRITE; then
  echo "Index drift: files/rows above are a dry-run. Run with --write to apply."
  exit 1
fi
# Every destination has been validated before the first write.
[[ "$layout" != split ]] || mkdir -p "$CHILD_DIR"
for ((i=0; i<${#outputs[@]}; i++)); do
  cmp -s "${staged[i]}" "${outputs[i]}" && continue
  cat "${staged[i]}" > "${outputs[i]}"
done
echo "Updated generated indexes."
