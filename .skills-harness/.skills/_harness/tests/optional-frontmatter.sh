#!/bin/bash
set -euo pipefail
# Optional Agent Skills fields: zero dependencies, compatible with Bash 3.2.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
validator="$script_dir/../validate-optional-frontmatter.awk"
test_root="$(mktemp -d "${TMPDIR:-/tmp}/skills-optional-frontmatter.XXXXXX")"
trap 'rm -rf "$test_root"' EXIT HUP INT TERM
count=0

check_case() {
  local expected="$1" label="$2" actual=0
  { printf '%s\n' '---' 'name: fixture'; cat; printf '%s\n' '---' '# Fixture'; } > "$test_root/SKILL.md"
  LC_ALL=C awk -f "$validator" "$test_root/SKILL.md" > "$test_root/output" 2>&1 || actual=$?
  if [[ "$expected" == pass && "$actual" != 0 ]] || [[ "$expected" == fail && "$actual" == 0 ]]; then
    printf 'not ok - %s\n' "$label" >&2
    cat "$test_root/output" >&2
    exit 1
  fi
  count=$((count + 1))
  printf 'ok - %s\n' "$label"
}

check_case pass 'absent optional fields preserve legacy skills' <<'EOF'
description: "A legacy skill."
EOF
check_case pass 'block map, quoted numeric values, environment requirements' <<'EOF'
compatibility: "Requires mods.yaml and servers[]."
metadata:
  family: server
  revision: "1"
  boolean-label: 'true'
  runtime: 3d-engine
EOF
check_case pass 'flow map with quoted punctuation and comments' <<'EOF'
compatibility: Requires git # environment requirement
metadata: {family: server, "strange:key": "comma, brace } and # text", note: 'It''s portable'} # comment
EOF
check_case pass 'empty map is allowed' <<'EOF'
metadata: {}
EOF
check_case pass 'escaped quotes, slash and newline' <<'EOF'
compatibility: "Requires \"git\" and a path\\tool."
metadata: {note: "first\nsecond", path: "a\/b"}
EOF
check_case fail 'empty compatibility is rejected' <<'EOF'
compatibility: ""
EOF
check_case pass '500 character compatibility boundary' < <(printf 'compatibility: "%0500d"\n' 0)
check_case fail '501 character compatibility is rejected' < <(printf 'compatibility: "%0501d"\n' 0)
for value in true false null '~' 42 1.2 1e3 0xff 2026-10-20 '[one]' '{nested: value}' '*alias' '&anchor value' '!tag value'; do
  check_case fail "non-string metadata value: $value" < <(printf 'metadata:\n  value: %s\n' "$value")
done
check_case fail 'metadata must be a map' <<'EOF'
metadata: server
EOF
check_case fail 'empty metadata is null, not a map' <<'EOF'
metadata:
EOF
check_case fail 'nested map is rejected' <<'EOF'
metadata:
  nested:
    child: value
EOF
check_case fail 'duplicate metadata keys are rejected' <<'EOF'
metadata: {family: server, family: other}
EOF
check_case fail 'duplicate optional fields are rejected' <<'EOF'
compatibility: git
compatibility: docker
EOF
check_case fail 'numeric metadata key is rejected' <<'EOF'
metadata: {1: server}
EOF
check_case fail 'unterminated quotes are rejected' <<'EOF'
compatibility: "Requires git
EOF
check_case fail 'unsupported scalar blocks are diagnosed' <<'EOF'
compatibility: >
  Requires git.
EOF
check_case fail 'multiline plain scalar cannot evade length checks' <<'EOF'
compatibility: Requires git
  and additional tools
EOF
check_case fail 'multiline metadata cannot be silently truncated' <<'EOF'
metadata:
  note: first line
    second line
EOF
check_case pass 'apostrophes in plain flow values and keys remain literal' <<'EOF'
metadata: {note: Don't panic, owner's: server}
EOF
check_case pass 'apostrophes in plain block keys remain literal' <<'EOF'
metadata:
  owner's: team
EOF
check_case pass 'plain quotes and punctuation do not hide comments' <<'EOF'
compatibility: Don't require git, "tools # comment
metadata:
  note: Don't require git, "tools # comment
EOF
check_case pass 'comment after plain apostrophe is excluded from character limit' < <(printf 'compatibility: Don\047t require git # %0600d\n' 0)
check_case pass 'comment after plain comma and literal quote is excluded from character limit' < <(printf 'compatibility: git, "tools # %0600d\n' 0)
check_case pass 'quoted compact flow pairs and comments are supported' <<'EOF'
metadata: {"family":"server", "note":"# literal, brace }", "count":"1"} # comment
EOF
check_case pass 'quoted top-level keys are validated' <<'EOF'
"compatibility": "Requires git."
'metadata': {family: server}
EOF
check_case fail 'quoted top-level metadata cannot bypass map validation' <<'EOF'
"metadata": true
EOF
check_case fail 'quoted top-level compatibility cannot bypass string validation' <<'EOF'
'compatibility': 123
EOF
check_case fail 'plain compatibility cannot end with a mapping colon' <<'EOF'
compatibility: requires:
EOF
check_case fail 'plain block metadata value cannot end with a mapping colon' <<'EOF'
metadata:
  note: requires:
EOF
check_case fail 'plain flow metadata value cannot end with a mapping colon' <<'EOF'
metadata: {note: requires:}
EOF
check_case fail 'literal quotes in plain flow text do not hide commas' <<'EOF'
metadata: {note: say "hello, world", family: server}
EOF
check_case fail 'literal quotes in plain flow text do not hide collections' <<'EOF'
metadata: {note: say "hello [world]", family: server}
EOF
check_case fail 'unterminated flow quotes cannot hide following pairs' <<'EOF'
metadata: {note: "never closed, family: server}
EOF
check_case fail 'compact unquoted top-level field is not a YAML mapping' <<'EOF'
compatibility:git
EOF
check_case fail 'compact quoted block pair needs separation' <<'EOF'
metadata:
  "family":"server"
EOF
utf8_compatibility() {
  local count="$1" i
  printf 'compatibility: "'
  for ((i=0; i<count; i++)); do printf '\303\251'; done
  printf '"\n'
}
check_case pass '500 UTF-8 code points fit the character limit' < <(utf8_compatibility 500)
check_case fail '501 UTF-8 code points exceed the character limit' < <(utf8_compatibility 501)
check_case fail 'space before key colon cannot bypass validation' <<'EOF'
metadata : true
EOF

# This helper validates reserved root fields, not all YAML or extension schemas.
# Optional-looking child names must not be treated as root fields, while a
# misplaced root field beneath a required scalar/string-list is diagnosed.
for field in name description version; do
  check_case fail "indented optional key after $field scalar" < <(printf '%s: "value"\n  metadata: true\n' "$field")
done
check_case fail 'quoted indented optional key after inline list' <<'EOF'
dependencies: []
  'compatibility' : false
EOF
check_case fail 'misplaced optional key before first list item' <<'EOF'
triggers:
  metadata: true
EOF
check_case fail 'misplaced optional key after plain list item' <<'EOF'
triggers:
  - review a skill
  metadata: true
EOF
check_case fail 'deeper optional key cannot extend a plain list string' <<'EOF'
dependencies:
  - skill-author
    compatibility: false
EOF
check_case fail 'optional mapping cannot extend a plain scalar' <<'EOF'
description: first line
  metadata: true
EOF
check_case pass 'custom nested maps and lists retain their own optional-looking keys' <<'EOF'
custom:
  metadata: true
  nested:
    compatibility: false
  events:
    - event:
        metadata: true
EOF
check_case pass 'nested sequence mappings are outside root optional validation' <<'EOF'
custom:
  - metadata: true
    compatibility: false
EOF
check_case pass 'sequence mapping children do not become reserved root fields' <<'EOF'
triggers:
  - example:
      metadata: true
    compatibility: false
EOF
check_case pass 'literal description content is not optional frontmatter' <<'EOF'
description: |
  metadata: true
EOF
check_case pass 'folded description content is not optional frontmatter' <<'EOF'
description: >-
  compatibility: false
EOF
check_case pass 'explicit block scalar indentation and chomping are preserved' <<'EOF'
description: |2-
  metadata: true
EOF
check_case pass 'literal list item content is not optional frontmatter' <<'EOF'
triggers:
  - |
    metadata: true
  - review a skill
EOF
check_case fail 'dedent from list scalar restores misplaced-key detection' <<'EOF'
triggers:
  - |+
    metadata: true
  compatibility: false
EOF
check_case pass 'multiline quoted description preserves optional-looking content' <<'EOF'
description: "First line
  metadata: true
  last line"
EOF
check_case pass 'multiline quoted list item preserves optional-looking content' <<'EOF'
triggers:
  - 'First line
    compatibility: false
    last line'
EOF
check_case fail 'closed multiline quote restores misplaced-key detection' <<'EOF'
description: "First line
  metadata: true
  last line"
  compatibility: false
EOF
check_case fail 'nested custom data does not hide subsequent root validation' <<'EOF'
custom:
  metadata: true
compatibility: false
EOF

# Check integration: arbitrary metadata keys must not overwrite required fields,
# or satisfy a required field missing at the top level.
(
  export SKILLS_DIR="$test_root/catalog/_skills" SKILLS_INDEX="$test_root/catalog/_index.md"
  export SKILLS_META="$test_root/catalog/_meta.yml" SKILLS_REPO_ROOT="$test_root/catalog"
  export SKILLS_CHECK_KIT_SURFACES=0
  mkdir -p "$SKILLS_DIR/example"
  printf 'kit_version: "0.0.0"\nrole: consumer\n' > "$SKILLS_META"
  cat > "$SKILLS_DIR/example/SKILL.md" <<'EOF'
---
name: example
description: "Tests optional metadata integration."
triggers: []
dependencies: []
version: "1.0.0"
metadata:
  name: annotation-name
  description: annotation-description
  version: annotation-version
---
# Example
EOF
  printf '# Skills\n\n| name | description | triggers |\n|---|---|---|\n' > "$SKILLS_INDEX"
  /bin/bash "$script_dir/../build-index.sh" --write > "$test_root/generate.out"
  /bin/bash "$script_dir/../check.sh" > "$test_root/check.out" 2>&1 || { cat "$test_root/check.out"; exit 1; }
  sed '/^description:/d' "$SKILLS_DIR/example/SKILL.md" > "$test_root/missing-description"
  cp "$test_root/missing-description" "$SKILLS_DIR/example/SKILL.md"
  if /bin/bash "$script_dir/../check.sh" > "$test_root/check.out" 2>&1; then
    echo 'not ok - nested metadata cannot satisfy required description' >&2; exit 1
  fi
  grep -q "missing required frontmatter field 'description'" "$test_root/check.out" || { cat "$test_root/check.out"; exit 1; }
)
printf 'ok - nested metadata cannot overwrite or satisfy top-level required fields\n'
printf 'Passed %s optional-frontmatter checks and required-field integration.\n' "$count"
