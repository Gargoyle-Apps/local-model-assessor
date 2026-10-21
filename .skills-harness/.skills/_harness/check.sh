#!/usr/bin/env bash
set -euo pipefail

# Validates skills-harness consistency:
#   1. Every directory under _skills/ has a matching row in _index.md
#   2. Every row in _index.md has a matching directory under _skills/
#   3. Each SKILL.md has required frontmatter fields
#   4. Each SKILL.md name field matches its directory name
#   5. Level 3 resource layout (scripts/, references/, assets/) and path references
#   6. Rules blocks in all templates match the canonical _rules.md
#   7. _skills/<name>/ entry topology (directory symlinks for kit/consumer shims) when applicable
#   8. Declared native discovery targets exist and mirror _skills/
#   9. Dependency graph, skill-size, index-size, and native metadata health
#  10. kit_version in _meta.yml matches newest CHANGELOG release, README, and AGENTS_skills.md
#
# Options:
#   --quiet              Suppress success output; retain warnings and errors
#   --link               Create/sync every declared native discovery target, then validate
#   SKILLS_AUTO_LINK=1   Same as --link

QUIET=false
AUTO_LINK=false
for arg in "$@"; do
  case "$arg" in
    --quiet) QUIET=true ;;
    --link)  AUTO_LINK=true ;;
    -h|--help)
      echo "Usage: $(basename "$0") [--quiet] [--link]" >&2
      echo "  --link  Create/sync native_targets declared in .skills/_meta.yml" >&2
      exit 0
      ;;
    -*)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done
[[ "${SKILLS_AUTO_LINK:-}" == "1" ]] && AUTO_LINK=true

# Resolve the script's own location WITHOUT following symlinks, so subtree-vendored
# installs (where .skills/_harness/ is a symlink into .skills-harness/.skills/_harness/)
# still derive the consumer's _skills/_index.md/repo root rather than the subtree's.
# See gh issue #3, friction point 5.
script_src="${BASH_SOURCE[0]:-$0}"
script_dir="$(dirname "$script_src")"
HARNESS_DIR="${SKILLS_HARNESS_DIR:-$(cd "$script_dir" && pwd -L)}"
SKILLS_DIR="${SKILLS_DIR:-$(dirname "$HARNESS_DIR")/_skills}"
INDEX_FILE="${SKILLS_INDEX:-$(dirname "$HARNESS_DIR")/_index.md}"
RULES_FILE="${SKILLS_RULES:-$HARNESS_DIR/_rules.md}"
REPO_ROOT="${SKILLS_REPO_ROOT:-$(dirname "$(dirname "$HARNESS_DIR")")}"
META_FILE="${SKILLS_META:-$(dirname "$HARNESS_DIR")/_meta.yml}"

# Auto-detect consumer-vs-kit role for the kit-surface checks (CHANGELOG/README/AGENTS_skills.md
# version assertions). These only make sense in the upstream kit repo; consumers shouldn't
# need to mirror them. Detection signals:
#   - .skills-harness/ subtree directory at REPO_ROOT (subtree-vendored install), OR
#   - role: consumer in .skills/_meta.yml
# The SKILLS_CHECK_KIT_SURFACES env var still wins if set explicitly (0/1).
if [[ -z "${SKILLS_CHECK_KIT_SURFACES:-}" ]]; then
  SKILLS_CHECK_KIT_SURFACES=1
  if [[ -d "$REPO_ROOT/.skills-harness" ]]; then
    SKILLS_CHECK_KIT_SURFACES=0
  else
    META_FILE_AUTO="$META_FILE"
    if [[ -f "$META_FILE_AUTO" ]] && grep -qE '^role:[[:space:]]*consumer[[:space:]]*$' "$META_FILE_AUTO"; then
      SKILLS_CHECK_KIT_SURFACES=0
    fi
  fi
fi

errors=0

# Use ((++errors)) not ((errors++)) — with set -e, post-increment returns status 1 when the
# value was 0 and aborts the script. Pre-increment is always non-zero. Requires bash 3+.
err() { echo "ERROR: $1" >&2; ((++errors)) || true; }
warn() { echo "WARN:  $1" >&2; }

trim() {
  local s="$1"
  s="${s#"${s%%[![:space:]]*}"}"
  s="${s%"${s##*[![:space:]]}"}"
  printf '%s' "$s"
}

# Migration backups and harness internals are not active catalog entries.
is_catalog_skill() {
  case "$1" in _*|*.bak) return 1 ;; esac
  return 0
}

# --- 1 & 2: Generated index coverage, uniqueness, links, and wording ---
# One pipeline owns single/split validation and generation. Comparing generated
# output detects missing, stale, duplicate, misplaced rows and broken links.
if index_output="$(SKILLS_HARNESS_DIR="$HARNESS_DIR" SKILLS_DIR="$SKILLS_DIR" \
  SKILLS_INDEX="$INDEX_FILE" SKILLS_META="$META_FILE" \
  bash "$HARNESS_DIR/build-index.sh")"; then
  $QUIET || printf '%s\n' "$index_output"
else
  [[ -z "$index_output" ]] || printf '%s\n' "$index_output"
  err "Generated index validation failed; review build-index.sh dry-run above"
fi

# --- 3 & 4: Frontmatter validation ---

required_fields=("name" "description" "triggers" "dependencies" "version")

if [[ -d "$SKILLS_DIR" ]]; then
  for skill_file in "$SKILLS_DIR"/*/SKILL.md; do
    [[ ! -f "$skill_file" ]] && continue
    dir_name="$(basename "$(dirname "$skill_file")")"

    is_catalog_skill "$dir_name" || continue

    in_frontmatter=false
    frontmatter_closed=false
    # Pipe-delimited list of seen keys (bash 3.2–compatible; no associative arrays)
    found_keys="|"
    fm_name=""

    while IFS= read -r line; do
      if [[ "$line" == "---" ]]; then
        if $in_frontmatter; then
          frontmatter_closed=true
          break
        else
          in_frontmatter=true
          continue
        fi
      fi
      if $in_frontmatter; then
        # Optional metadata keys may reuse names such as description/version.
        # Only top-level fields satisfy the skill frontmatter contract.
        [[ "$line" == [[:space:]]* ]] && continue
        key="$(trim "$(echo "$line" | cut -d: -f1)")"
        for f in "${required_fields[@]}"; do
          if [[ "$key" == "$f" ]]; then
            found_keys="${found_keys}${f}|"
            if [[ "$f" == "name" ]]; then
              fm_name="$(trim "$(echo "$line" | cut -d: -f2-)")"
            fi
          fi
        done
      fi
    done < "$skill_file"

    if ! $frontmatter_closed; then
      err "$dir_name/SKILL.md: no valid YAML frontmatter (missing closing ---)"
      continue
    fi

    for f in "${required_fields[@]}"; do
      if [[ "$found_keys" != *"|${f}|"* ]]; then
        err "$dir_name/SKILL.md: missing required frontmatter field '$f'"
      fi
    done

    if [[ -n "$fm_name" && "$fm_name" != "$dir_name" ]]; then
      err "$dir_name/SKILL.md: frontmatter name '$fm_name' does not match directory name '$dir_name'"
    fi
    if ! LC_ALL=C awk -f "$HARNESS_DIR/validate-optional-frontmatter.awk" "$skill_file"; then
      err "$dir_name/SKILL.md: invalid optional compatibility/metadata frontmatter"
    fi
  done
fi

# --- 4b: Contract, dependency graph, and context-health warnings ---

TRANSITIVE_WARN_BYTES="${SKILLS_TRANSITIVE_WARN_BYTES:-20000}"
NATIVE_METADATA_LIMIT="${SKILLS_NATIVE_METADATA_LIMIT:-8000}"
INDEX_WARN_BYTES="${SKILLS_INDEX_WARN_BYTES:-12000}"
SKILL_LARGE_LINES="${SKILLS_SKILL_LARGE_LINES:-180}"
SKILL_SPLIT_LINES="${SKILLS_SKILL_SPLIT_LINES:-350}"

for numeric_setting in TRANSITIVE_WARN_BYTES NATIVE_METADATA_LIMIT INDEX_WARN_BYTES SKILL_LARGE_LINES SKILL_SPLIT_LINES; do
  eval "numeric_value=\${$numeric_setting}"
  case "$numeric_value" in
    ''|*[!0-9]*)
      err "$numeric_setting must be a non-negative integer (got '$numeric_value')"
      eval "$numeric_setting=0"
      ;;
  esac
done

metrics_tmp="$(mktemp)"
deps_tmp="$(mktemp)"
trap 'rm -f "$metrics_tmp" "$deps_tmp"' EXIT HUP INT TERM

catalog_names=()
native_metadata_estimate=0

if [[ -d "$SKILLS_DIR" ]]; then
  for skill_file in "$SKILLS_DIR"/*/SKILL.md; do
    [[ -f "$skill_file" ]] || continue
    dir_name="$(basename "$(dirname "$skill_file")")"
    is_catalog_skill "$dir_name" || continue
    catalog_names+=("$dir_name")

    skill_bytes="$(LC_ALL=C wc -c < "$skill_file" | tr -d '[:space:]')"
    skill_lines="$(wc -l < "$skill_file" | tr -d '[:space:]')"
    fm_description="$(awk '
      NR == 1 && $0 == "---" { in_fm=1; next }
      in_fm && $0 == "---" { exit }
      in_fm && /^description:/ { sub(/^description:[[:space:]]*/, ""); print; exit }
    ' "$skill_file")"
    fm_description="${fm_description#\"}"
    fm_description="${fm_description%\"}"
    fm_description="${fm_description#\'}"
    fm_description="${fm_description%\'}"

    name_len="${#dir_name}"
    if (( name_len < 1 || name_len > 64 )) || [[ ! "$dir_name" =~ ^[a-z0-9]([a-z0-9-]*[a-z0-9])?$ ]] || [[ "$dir_name" == *--* ]]; then
      err "$dir_name/SKILL.md: name violates Agent Skills shape (1-64 lowercase alphanumeric/hyphen characters; no edge or consecutive hyphens)"
    fi

    description_len="${#fm_description}"
    if (( description_len < 1 || description_len > 1024 )); then
      err "$dir_name/SKILL.md: description must contain 1-1024 characters (got $description_len)"
    elif [[ "$fm_description" == *"<"* || "$fm_description" == *">"* ]]; then
      err "$dir_name/SKILL.md: description must not contain XML-like angle brackets"
    fi

    if (( skill_lines > SKILL_SPLIT_LINES )); then
      warn "$dir_name/SKILL.md is $skill_lines lines (split candidate: > $SKILL_SPLIT_LINES)"
    elif (( skill_lines > SKILL_LARGE_LINES )); then
      warn "$dir_name/SKILL.md is $skill_lines lines (large: > $SKILL_LARGE_LINES; consider references/)"
    fi

    printf '%s\t%s\t%s\t%s\n' "$dir_name" "$skill_bytes" "$skill_lines" "$fm_description" >> "$metrics_tmp"
    representative_path=".agents/skills/$dir_name/SKILL.md"
    native_metadata_estimate=$((native_metadata_estimate + ${#dir_name} + ${#fm_description} + ${#representative_path} + 3))

    while IFS= read -r dep; do
      [[ -n "$dep" ]] || continue
      printf '%s\t%s\n' "$dir_name" "$dep" >> "$deps_tmp"
    done <<EOF
$(awk '
  NR == 1 && $0 == "---" { in_fm=1; next }
  in_fm && $0 == "---" { exit }
  !in_fm { next }
  /^dependencies:/ {
    rest=$0
    sub(/^dependencies:[[:space:]]*/, "", rest)
    if (rest ~ /^\[/) {
      gsub(/^\[[[:space:]]*|[[:space:]]*\]$/, "", rest)
      count=split(rest, values, /[[:space:]]*,[[:space:]]*/)
      for (i=1; i<=count; i++) if (values[i] != "") {
        gsub(/^["'"'']|["'"'']$/, "", values[i])
        print values[i]
      }
      exit
    }
    in_deps=1
    next
  }
  in_deps && /^[^[:space:]#][^:]*:/ { exit }
  in_deps && /^[[:space:]]*-[[:space:]]*/ {
    value=$0
    sub(/^[[:space:]]*-[[:space:]]*/, "", value)
    gsub(/^["'"'']|["'"'']$/, "", value)
    if (value != "") print value
  }
' "$skill_file")
EOF
  done
fi

catalog_has_name() {
  local needle="$1" candidate
  for candidate in ${catalog_names[@]+"${catalog_names[@]}"}; do
    [[ "$candidate" == "$needle" ]] && return 0
  done
  return 1
}

while IFS=$'\t' read -r owner dep; do
  [[ -n "$owner" && -n "$dep" ]] || continue
  if ! catalog_has_name "$dep"; then
    warn "$owner/SKILL.md declares missing dependency '$dep'"
  fi
done < "$deps_tmp"

cycles="$(awk -F '\t' '
  NF >= 2 { nodes[$1]=1; nodes[$2]=1; edge[$1 SUBSEP $2]=1 }
  function dfs(n,    key, pair, next_node, i, start, chain) {
    state[n]=1
    stack[++depth]=n
    for (key in edge) {
      split(key, pair, SUBSEP)
      if (pair[1] != n) continue
      next_node=pair[2]
      if (state[next_node] == 0) dfs(next_node)
      else if (state[next_node] == 1) {
        start=1
        for (i=1; i<=depth; i++) if (stack[i] == next_node) { start=i; break }
        chain=stack[start]
        for (i=start+1; i<=depth; i++) chain=chain " -> " stack[i]
        chain=chain " -> " next_node
        if (!reported[chain]++) print chain
      }
    }
    state[n]=2
    delete stack[depth--]
  }
  END { for (n in nodes) if (state[n] == 0) dfs(n) }
' "$deps_tmp")"
while IFS= read -r cycle; do
  [[ -n "$cycle" ]] && warn "dependency cycle detected: $cycle"
done <<EOF
$cycles
EOF

transitive_reports="$(awk -F '\t' -v limit="$TRANSITIVE_WARN_BYTES" '
  FILENAME == ARGV[1] { size[$1]=$2; next }
  NF >= 2 { edge[$1 SUBSEP $2]=1 }
  function total(n,    key, pair, subtotal) {
    if (seen[n] == generation) return 0
    seen[n]=generation
    subtotal=size[n] + 0
    for (key in edge) {
      split(key, pair, SUBSEP)
      if (pair[1] == n) subtotal += total(pair[2])
    }
    return subtotal
  }
  END {
    for (n in size) {
      generation++
      bytes=total(n)
      if (bytes > limit) print n "\t" bytes
    }
  }
' "$metrics_tmp" "$deps_tmp")"
while IFS=$'\t' read -r root_skill transitive_bytes; do
  [[ -n "$root_skill" ]] && warn "$root_skill loads approximately $transitive_bytes bytes including transitive dependencies (threshold: $TRANSITIVE_WARN_BYTES)"
done <<EOF
$transitive_reports
EOF

if (( native_metadata_estimate > NATIVE_METADATA_LIMIT )); then
  warn "native skill metadata estimate is $native_metadata_estimate characters (configured review threshold: $NATIVE_METADATA_LIMIT; not a runtime limit)"
fi

if [[ -f "$INDEX_FILE" ]]; then
  index_bytes="$(LC_ALL=C wc -c < "$INDEX_FILE" | tr -d '[:space:]')"
  if (( index_bytes > INDEX_WARN_BYTES )); then
    warn "_index.md is $index_bytes bytes (growth threshold: $INDEX_WARN_BYTES); keep fallback lookup targeted"
  fi
fi

# --- 5: Level 3 resource layout (scripts/, references/, assets/) ---

resource_dirs=(scripts references assets)

trim_resource_ref() {
  local s="$1"
  s="$(echo "$s" | sed -E 's/[.,;:!?)}\`"'\''>]+$//')"
  printf '%s' "$s"
}

if [[ -d "$SKILLS_DIR" ]]; then
  for skill_dir in "$SKILLS_DIR"/*/; do
    [[ -d "$skill_dir" ]] || continue
    dir_name="$(basename "$skill_dir")"
    is_catalog_skill "$dir_name" || continue
    skill_file="$skill_dir/SKILL.md"
    [[ -f "$skill_file" ]] || continue

    for rd in "${resource_dirs[@]}"; do
      if [[ -e "$skill_dir/$rd" && ! -d "$skill_dir/$rd" ]]; then
        err "$dir_name/$rd exists but is not a directory"
      fi
    done

    for item in "$skill_dir"/*; do
      [[ -f "$item" && ! -L "$item" ]] || continue
      base="$(basename "$item")"
      [[ "$base" == "SKILL.md" ]] && continue
      case "$base" in
        *.sh|*.py|*.js|*.ts|*.rb|*.pl)
          warn "$dir_name/$base: script at skill root — move to scripts/"
          ;;
        *.md)
          warn "$dir_name/$base: markdown at skill root — move to references/"
          ;;
      esac
    done

    # Track referenced paths so we only report each missing path once.
    seen_refs="|"
    in_fm=false
    fm_done=false
    while IFS= read -r line; do
      if [[ "$line" == "---" ]]; then
        if $in_fm; then
          fm_done=true
          in_fm=false
          continue
        else
          in_fm=true
          continue
        fi
      fi
      $fm_done || continue

      refs="$(echo "$line" | grep -oE '(scripts|references|assets)/[A-Za-z0-9_./-]+\.[A-Za-z0-9][A-Za-z0-9._-]*' || true)"
      [[ -z "$refs" ]] && continue

      while IFS= read -r ref_path; do
        [[ -z "$ref_path" ]] && continue
        ref_path="$(trim_resource_ref "$ref_path")"
        [[ -z "$ref_path" ]] && continue
        if [[ "$seen_refs" == *"|${ref_path}|"* ]]; then
          continue
        fi
        seen_refs="${seen_refs}${ref_path}|"

        if [[ ! -e "$skill_dir/$ref_path" ]]; then
          err "$dir_name/SKILL.md references missing resource: $ref_path"
          continue
        fi

        # Symlink stability: bundled resources must resolve through symlinked skill dirs.
        if [[ -L "$skill_dir" && ! -r "$skill_dir/$ref_path" ]]; then
          err "$dir_name/SKILL.md resource not readable through directory symlink: $ref_path (→ $(readlink "$skill_dir"))"
        fi
      done <<EOF
$refs
EOF
    done < "$skill_file"
  done
fi

# --- 6: Rules block sync ---

if [[ -f "$RULES_FILE" ]]; then
  canonical="$(sed -n '/^# Rules$/,$ p' "$RULES_FILE" | tail -n +2)"

  for tmpl in "$HARNESS_DIR"/*_template.md; do
    [[ ! -f "$tmpl" ]] && continue
    tmpl_name="$(basename "$tmpl")"

    tmpl_rules="$(sed -n '/^## Rules$/,/^<!-- END RULES -->/ { /^<!-- END RULES -->/d; p; }' "$tmpl" | tail -n +2)"
    if [[ -z "$tmpl_rules" ]]; then
      tmpl_rules="$(sed -n '/^## Rules$/,$ p' "$tmpl" | tail -n +2)"
    fi

    tmpl_rules="$(echo "$tmpl_rules" | sed '/^$/d')"
    canonical_clean="$(echo "$canonical" | sed '/^$/d')"

    if [[ "$tmpl_rules" != "$canonical_clean" ]]; then
      err "$tmpl_name: Rules block differs from _rules.md"
    fi
  done
else
  warn "_rules.md not found; skipping Rules sync check"
fi

# Skill names managed by the harness (mirrors link.sh: exclude internals/backups).
skill_names=()
if [[ -d "$SKILLS_DIR" ]]; then
  for skill_dir in "$SKILLS_DIR"/*/; do
    [[ -d "$skill_dir" ]] || continue
    name="$(basename "$skill_dir")"
    is_catalog_skill "$name" || continue
    [[ -f "$skill_dir/SKILL.md" ]] || continue
    skill_names+=("$name")
  done
fi

# --- 7: _skills/ entry topology (directory symlinks) ---
# When the kit is subtree-vendored or consumer_skills_dir is declared, kit skills and
# consumer shims are directory symlinks. Inner files (SKILL.md) look like regular files;
# verify sync here, not with readlink on inner paths. See gh issue #5.

SUBTREE_PREFIX=".skills-harness"
SUBTREE_SKILLS_DIR="$REPO_ROOT/$SUBTREE_PREFIX/.skills/_skills"
HAS_SUBTREE=false
[[ -d "$SUBTREE_SKILLS_DIR" ]] && HAS_SUBTREE=true

CONSUMER_SKILLS_DIR=""
TOPO_META_FILE="$(dirname "$HARNESS_DIR")/_meta.yml"
if [[ -f "$TOPO_META_FILE" ]]; then
  raw_csd="$(grep -E '^consumer_skills_dir:' "$TOPO_META_FILE" | head -1 | sed 's/^consumer_skills_dir://' || true)"
  raw_csd="$(trim "$raw_csd")"
  raw_csd="${raw_csd#\"}"
  raw_csd="${raw_csd%\"}"
  CONSUMER_SKILLS_DIR="$raw_csd"
fi

kit_skill_names=()
if $HAS_SUBTREE; then
  for kit_dir in "$SUBTREE_SKILLS_DIR"/*/; do
    [[ -d "$kit_dir" ]] || continue
    kit_name="$(basename "$kit_dir")"
    is_catalog_skill "$kit_name" || continue
    kit_skill_names+=("$kit_name")
  done
fi

is_kit_skill_name() {
  local name="$1" k
  for k in ${kit_skill_names[@]+"${kit_skill_names[@]}"}; do
    [[ "$k" == "$name" ]] && return 0
  done
  return 1
}

if $HAS_SUBTREE || [[ -n "$CONSUMER_SKILLS_DIR" ]]; then
  for name in ${skill_names[@]+"${skill_names[@]}"}; do
    entry_path="$SKILLS_DIR/$name"
    expected=""

    if is_kit_skill_name "$name"; then
      expected="../../$SUBTREE_PREFIX/.skills/_skills/$name"
    elif [[ -n "$CONSUMER_SKILLS_DIR" ]] && [[ -f "$REPO_ROOT/$CONSUMER_SKILLS_DIR/$name/SKILL.md" ]]; then
      expected="../../$CONSUMER_SKILLS_DIR/$name"
    fi

    if [[ -L "$entry_path" ]]; then
      if [[ ! -d "$entry_path" ]]; then
        err "_skills/$name is a broken directory symlink (target: $(readlink "$entry_path"))"
        continue
      fi

      actual="$(readlink "$entry_path")"
      if [[ -n "$expected" ]]; then
        if [[ "$actual" != "$expected" ]]; then
          err "_skills/$name points to '$actual' but should be '$expected'"
          continue
        fi
        $QUIET || echo "_skills/$name: directory symlink → $actual ✓"
      else
        warn "_skills/$name is a directory symlink (→ $actual) but no expected target for this layout"
      fi
      continue
    fi

    if [[ ! -d "$entry_path" ]]; then
      continue
    fi

    if [[ -n "$expected" ]]; then
      if is_kit_skill_name "$name"; then
        warn "_skills/$name is a real directory; expected directory symlink → $expected"
      else
        warn "_skills/$name is a real directory; expected directory symlink → $expected (run: migrate-to-subtree.sh --symlink-consumer-skills)"
      fi
    fi
  done
fi

# --- 8: Persisted native discovery targets ---

native_symdirs=()
native_targets_declared=false

if [[ -f "$META_FILE" ]]; then
  if grep -qE '^native_targets:[[:space:]]*\[' "$META_FILE"; then
    err "_meta.yml: native_targets must use a block list, not flow-style YAML"
  fi

  in_native_targets=false
  while IFS= read -r line; do
    if [[ "$line" =~ ^native_targets:[[:space:]]*$ ]]; then
      native_targets_declared=true
      in_native_targets=true
      continue
    fi
    if $in_native_targets && [[ "$line" =~ ^[^[:space:]#][^:]*: ]]; then
      in_native_targets=false
    fi
    if $in_native_targets && [[ "$line" =~ ^[[:space:]]*-[[:space:]]*(.*)$ ]]; then
      target="${BASH_REMATCH[1]}"
      target="$(trim "$target")"
      target="${target#\"}"; target="${target%\"}"
      target="${target#\'}"; target="${target%\'}"
      target="${target#./}"; target="${target%/}"
      case "$target" in
        ""|.|/*|..|../*|*/../*|*/..)
          err "_meta.yml: unsafe native target '$target' (must be relative to repo root)"
          continue
          ;;
      esac
      duplicate=false
      for existing_target in ${native_symdirs[@]+"${native_symdirs[@]}"}; do
        [[ "$existing_target" == "$target" ]] && duplicate=true && break
      done
      if $duplicate; then
        warn "_meta.yml: duplicate native target '$target'"
      else
        native_symdirs+=("$target")
      fi
    fi
  done < "$META_FILE"
fi

if $native_targets_declared && (( ${#native_symdirs[@]} == 0 )); then
  err "_meta.yml: native_targets is declared but contains no valid targets"
elif ! $native_targets_declared; then
  warn "native discovery is not configured; add native_targets to .skills/_meta.yml"
  # Backward-compatible validation for pre-metadata installs. These existing
  # directories are checked, but --link will not invent a target choice.
  for legacy_target in ".agents/skills" ".claude/skills"; do
    [[ -d "$REPO_ROOT/$legacy_target" ]] && native_symdirs+=("$legacy_target")
  done
fi

# Relative path from <symdir>/ to .skills/_skills (same climb logic as link.sh).
native_expected_skills_base() {
  local symdir_rel="$1"
  local rel_prefix="" tmp="$symdir_rel" parent
  while [[ "$tmp" != "." && -n "$tmp" ]]; do
    rel_prefix="../$rel_prefix"
    parent="$(dirname "$tmp")"
    [[ "$parent" == "$tmp" ]] && break
    tmp="$parent"
  done
  printf '%s' "${rel_prefix}.skills/_skills"
}

if $AUTO_LINK; then
  for symdir in ${native_symdirs[@]+"${native_symdirs[@]}"}; do
    $QUIET || echo "Syncing native discovery: $symdir"
    if link_output="$("$HARNESS_DIR/link.sh" --no-record "$symdir")"; then
      $QUIET || printf '%s\n' "$link_output"
    else
      [[ -z "$link_output" ]] || printf '%s\n' "$link_output" >&2
      err "Native discovery synchronization failed for '$symdir'"
    fi
  done
fi

has_agents_target=false
has_cursor_target=false
for symdir in ${native_symdirs[@]+"${native_symdirs[@]}"}; do
  [[ "$symdir" == ".agents/skills" ]] && has_agents_target=true
  [[ "$symdir" == ".cursor/skills" ]] && has_cursor_target=true
done
if $has_agents_target && $has_cursor_target; then
  warn "both .agents/skills and .cursor/skills are configured; Cursor may expose duplicate skill names from both native surfaces"
fi

for symdir in ${native_symdirs[@]+"${native_symdirs[@]}"}; do
  symdir_abs="$REPO_ROOT/$symdir"
  if [[ ! -d "$symdir_abs" ]]; then
    if $native_targets_declared; then
      err "declared native target '$symdir' is absent. Run: .skills/_harness/check.sh --link"
    fi
    continue
  fi

  rel_skills="$(native_expected_skills_base "$symdir")"

  for name in ${skill_names[@]+"${skill_names[@]}"}; do
    link_path="$symdir_abs/$name"
    expected="${rel_skills}/${name}"

    if [[ ! -e "$link_path" && ! -L "$link_path" ]]; then
      err "$symdir/$name missing (expected symlink -> $expected). Run: .skills/_harness/link.sh $symdir  (or: check.sh --link)"
      continue
    fi

    if [[ ! -L "$link_path" ]]; then
      warn "$symdir/$name is not a symlink (expected -> $expected)"
      continue
    fi

    actual="$(readlink "$link_path")"
    if [[ "$actual" != "$expected" ]]; then
      err "$symdir/$name points to '$actual' but should be '$expected'. Run: .skills/_harness/link.sh $symdir  (or: check.sh --link)"
      continue
    fi

    if [[ ! -d "$link_path" ]]; then
      err "$symdir/$name is a broken symlink (target: $actual)"
      continue
    fi

    if [[ ! -f "$link_path/SKILL.md" ]]; then
      warn "$symdir/$name symlink target has no SKILL.md"
    fi
  done

  for link in "$symdir_abs"/*; do
    [[ -e "$link" || -L "$link" ]] || continue
    name="$(basename "$link")"
    if ! is_catalog_skill "$name" && [[ -L "$link" ]] && [[ "$(readlink "$link")" == "$rel_skills/$name" ]]; then
      err "$symdir/$name exposes an inactive backup/internal directory through native discovery. Run: .skills/_harness/link.sh $symdir  (or: check.sh --link)"
      continue
    fi
    found=false
    for skill_name in ${skill_names[@]+"${skill_names[@]}"}; do
      [[ "$skill_name" == "$name" ]] && found=true && break
    done
    if ! $found; then
      if [[ -L "$link" ]] && [[ ! -e "$link" ]]; then
        err "$symdir/$name is a dangling symlink (target: $(readlink "$link")). Run: .skills/_harness/link.sh $symdir  (or: check.sh --link)"
      else
        warn "$symdir/$name has no matching _skills/$name/ (extra entry or non-harness skill)"
      fi
    fi
  done
done

# --- 10: Kit version surfaces (_meta.yml, CHANGELOG, README, AGENTS_skills.md) ---

CHANGELOG_FILE="$REPO_ROOT/CHANGELOG.md"
README_FILE="$REPO_ROOT/README.md"
BOOTSTRAP_FILE="$REPO_ROOT/AGENTS_skills.md"

if [[ -f "$META_FILE" ]]; then
  meta_line="$(grep -E '^kit_version:' "$META_FILE" | head -1 || true)"
  meta_ver="${meta_line#kit_version:}"
  meta_ver="$(trim "$meta_ver")"
  meta_ver="${meta_ver#\"}"
  meta_ver="${meta_ver%\"}"

  if [[ -z "$meta_ver" ]]; then
    err "_meta.yml: could not parse kit_version"
  else
    # All three kit-version surface checks (CHANGELOG, README, AGENTS_skills.md)
    # only make sense in the upstream kit repo. Consumers auto-skip via the
    # SKILLS_CHECK_KIT_SURFACES detection at the top of this script. See gh
    # issue #3, friction point 6.
    if [[ "${SKILLS_CHECK_KIT_SURFACES:-1}" == "1" ]]; then
      if [[ -f "$CHANGELOG_FILE" ]]; then
        cl_line="$(grep -E '^## \[[0-9]' "$CHANGELOG_FILE" | head -1 || true)"
        if [[ -z "$cl_line" ]]; then
          err "CHANGELOG.md: no release heading like ## [x.y.z] found after intro"
        else
          cl_ver="$(echo "$cl_line" | sed -E 's/^## \[([^]]+)\].*/\1/')"
          if [[ "$cl_ver" != "$meta_ver" ]]; then
            err "CHANGELOG first release [$cl_ver] does not match _meta.yml kit_version ($meta_ver)"
          fi
        fi
      else
        err "CHANGELOG.md not found at $CHANGELOG_FILE (required for kit version check)"
      fi

      if [[ -f "$README_FILE" ]]; then
        if ! grep -Fq "**Current release:** \`${meta_ver}\`" "$README_FILE"; then
          err "README.md: expected **Current release:** \`${meta_ver}\` to match .skills/_meta.yml"
        fi
      else
        err "README.md not found at $README_FILE (required for kit version check)"
      fi

      if [[ -f "$BOOTSTRAP_FILE" ]]; then
        if ! grep -Fq "**Kit version:** \`${meta_ver}\`" "$BOOTSTRAP_FILE"; then
          err "AGENTS_skills.md: expected **Kit version:** \`${meta_ver}\` to match .skills/_meta.yml"
        fi
      else
        err "AGENTS_skills.md not found at $BOOTSTRAP_FILE (required for kit version check)"
      fi
    fi
  fi
else
  warn ".skills/_meta.yml not found; skipping kit version surface check"
fi

# --- Summary ---

$QUIET && (( errors == 0 )) || echo ""
if (( errors == 0 )); then
  $QUIET || echo "All checks passed."
else
  echo "$errors error(s) found."
  exit 1
fi
