# Validate the optional Agent Skills fields without evaluating YAML or requiring
# a YAML runtime. Supports single-line scalars and flat block/flow string maps.
# Unsupported optional-field constructs fail with a format hint rather than
# being ignored.
# This is not a whole-document YAML validator. For required scalar/list fields,
# it also diagnoses misplaced optional keys; custom extension mappings remain
# opaque, and optional-looking text inside multiline scalars remains content.
# Usage: LC_ALL=C awk -f validate-optional-frontmatter.awk path/to/SKILL.md
function trim(s) { sub(/^[ \t]+/, "", s); sub(/[ \t]+$/, "", s); return s }
function error(message) {
  print FILENAME ":" NR ": " message > "/dev/stderr"
  failed=1
}
# Quote marks embedded in plain scalars are literal characters, not delimiters.
function uncomment(s,    i,c,q,out,start,quoted_key,flow) {
  q=""; out=""; start=1; quoted_key=0; flow=0
  for (i=1; i<=length(s); i++) {
    c=substr(s,i,1)
    if (q=="\"" && c=="\\") { out=out c substr(s,++i,1); continue }
    if (q=="'" && c=="'" && substr(s,i+1,1)=="'") { out=out "''"; i++; continue }
    if (q!="" && c==q) q=""
    else if (q=="" && start && (c=="\"" || c=="'")) {
      q=c
      if (trim(out)=="" || (flow && out ~ /[{,][ \t]*$/)) quoted_key=1
    }
    else if (q=="" && c=="#" && (i==1 || substr(s,i-1,1) ~ /[ \t]/)) break
    if (q=="" && start && c=="{") flow=1
    if (q=="" && ((start && c=="{") || (flow && c==",") || (c==":" && (quoted_key || substr(s,i+1,1) ~ /[ \t]/)))) { start=1; quoted_key=0 }
    else if (c !~ /[ \t]/) start=0
    out=out c
  }
  return trim(out)
}
# Result is decoded in the global scalar variable; no shell/YAML evaluation.
function string_value(s, label,    q,i,c,n,closed,low) {
  s=trim(s); scalar=""; q=substr(s,1,1)
  if (q=="\"" || q=="'") {
    closed=0
    for (i=2; i<=length(s); i++) {
      c=substr(s,i,1)
      if (c==q) {
        if (q=="'" && substr(s,i+1,1)=="'") { scalar=scalar "'"; i++; continue }
        if (trim(substr(s,i+1))!="") break
        closed=1; break
      }
      if (q=="\"" && c=="\\") {
        n=substr(s,++i,1)
        if (n=="n") c="\n"
        else if (n=="r") c="\r"
        else if (n=="t") c="\t"
        else if (n=="\\" || n=="\"" || n=="/") c=n
        else { error(label ": unsupported escape; use literal UTF-8 or single quotes"); return 0 }
      }
      scalar=scalar c
    }
    if (!closed) { error(label ": use a complete single-line quoted string"); return 0 }
    return 1
  }
  low=tolower(s)
  if (s=="" || s ~ /^[!&*|>{\[\]}'"%@`]/ || s ~ /^[-?:]([ \t]|$)/ || s ~ /:([ \t]|$)/ ||
      low ~ /^(null|~|true|false|yes|no|on|off|\.nan|[-+]?\.inf)$/ ||
      s ~ /^[-+]?([0-9][0-9_]*([.][0-9_]*)?|[.][0-9_]+)([eE][-+]?[0-9]+)?$/ ||
      s ~ /^[-+]?0[xXoObB][0-9a-fA-F_]+$/ || s ~ /^[0-9][0-9_]*(:[0-9]+)+$/ ||
      s ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]([Tt ].*)?$/) {
    error(label ": expected a string; quote numeric/boolean-looking text and use a flat mapping")
    return 0
  }
  scalar=s; return 1
}
function pair(s,flow,    i,c,q,at,key,quoted_key) {
  s=trim(s); q=""; at=0
  quoted_key=(substr(s,1,1)=="\"" || substr(s,1,1)=="'")
  for (i=1; i<=length(s); i++) {
    c=substr(s,i,1)
    if (q=="\"" && c=="\\") { i++; continue }
    if (q=="'" && c=="'" && substr(s,i+1,1)=="'") { i++; continue }
    if (q!="" && c==q) q=""
    else if (q=="" && i==1 && quoted_key) q=c
    else if (q=="" && c==":" && ((flow && quoted_key) || i==length(s) || substr(s,i+1,1) ~ /[ \t]/)) { at=i; break }
  }
  if (!at) { error("metadata: expected key: value string pairs"); return }
  if (!string_value(substr(s,1,at-1), "metadata key")) return
  key=scalar
  if (key in keys) error("metadata: duplicate key '" key "'")
  keys[key]=1
  string_value(substr(s,at+1), "metadata value for '" key "'")
  entries++
}
function flow_map(s,    i,c,q,part,start,quoted_key) {
  if (substr(s,length(s),1)!="}") { error("metadata: flow map must close on the same line"); return }
  s=trim(substr(s,2,length(s)-2)); if (s=="") return
  q=""; part=""; start=1; quoted_key=0
  for (i=1; i<=length(s); i++) {
    c=substr(s,i,1)
    if (q=="\"" && c=="\\") { part=part c substr(s,++i,1); continue }
    if (q=="'" && c=="'" && substr(s,i+1,1)=="'") { part=part "''"; i++; continue }
    if (q!="" && c==q) q=""
    else if (q=="" && start && (c=="\"" || c=="'")) {
      q=c
      if (trim(part)=="") quoted_key=1
    }
    else if (q=="" && c==",") { pair(part,1); part=""; start=1; quoted_key=0; continue }
    else if (q=="" && c ~ /[{}\[\]]/) { error("metadata: nested collections are not string values"); return }
    if (q=="" && c==":" && (quoted_key || substr(s,i+1,1) ~ /[ \t]/)) { start=1; quoted_key=0 }
    else if (c !~ /[ \t]/) start=0
    part=part c
  }
  if (trim(part)!="") pair(part,1)
}
function character_length(s) {
  # With LC_ALL=C, remove UTF-8 continuation bytes to count code points.
  gsub(/[\200-\277]/,"",s)
  return length(s)
}
function finish() {
  if (mode=="metadata" && entries==0) error("metadata: empty value is null; use metadata: {} for an empty map")
  mode=""
}
function optional_key(s) {
  return s ~ /^(compatibility|metadata)[ \t]*:/ ||
    s ~ /^"(compatibility|metadata)"[ \t]*:/ ||
    s ~ /^'(compatibility|metadata)'[ \t]*:/
}
# Return an unfinished quote, or empty when this scalar's quote has closed.
function remaining_quote(s,q,first,    i,c) {
  for (i=first; i<=length(s); i++) {
    c=substr(s,i,1)
    if (q=="\"" && c=="\\") { i++; continue }
    if (q=="'" && c=="'" && substr(s,i+1,1)=="'") { i++; continue }
    if (c==q) return ""
  }
  return q
}
function block_marker(s) {
  return s ~ /^[|>]([1-9][+-]?|[+-][1-9]?)?$/
}
function required_context(s,    at,key,value,q) {
  guard_required=0; scalar_quote=""; block_indent=-1; item_map_indent=-1
  at=index(s,":"); if (!at) return
  key=trim(substr(s,1,at-1)); value=trim(substr(s,at+1))
  if (key !~ /^(name|description|triggers|dependencies|version)$/) return
  guard_required=1
  if (block_marker(value)) block_indent=0
  q=substr(value,1,1)
  if (q=="\"" || q=="'") scalar_quote=remaining_quote(value,q,2)
  # Multiline flow collections are outside this bounded structural check.
  if ((q=="[" && value !~ /\]$/) || (q=="{" && value !~ /}$/)) guard_required=0
}
function check_required_child(raw,s,    depth,value,q) {
  if (!guard_required) return
  match(raw,/^[ \t]*/); depth=RLENGTH
  if (block_indent>=0) {
    if (depth>block_indent) return
    block_indent=-1
  }
  if (item_map_indent>=0) {
    if (depth>item_map_indent) return
    item_map_indent=-1
  }
  if (s ~ /^-[ \t]+/) {
    value=s; sub(/^-[ \t]+/,"",value)
    if (block_marker(value)) block_indent=depth
    q=substr(value,1,1)
    if (q=="\"" || q=="'") scalar_quote=remaining_quote(value,q,2)
    # A mapping inside a list is not a root optional field. Its legality for
    # the enclosing field belongs to that field's schema, not this validator.
    if ((q!="\"" && q!="'" && value ~ /:([ \t]|$)/) ||
        value ~ /^".*"[ \t]*:([ \t]|$)/ || value ~ /^'.*'[ \t]*:([ \t]|$)/)
      item_map_indent=depth
  } else if (optional_key(s)) {
    error("misindented optional field: compatibility and metadata must be top-level fields")
  }
}
!begun && $0=="---" { begun=1; in_fm=1; next }
in_fm && $0=="---" { finish(); in_fm=0; exit }
!in_fm { next }
{
  if (scalar_quote!="") {
    scalar_quote=remaining_quote($0,scalar_quote,1)
    next
  }
  line=uncomment($0)
  if (line=="") next
  if ($0 ~ /^[^ \t]/) {
    finish()
    required_context(line)
    # Quoted optional keys must not bypass their value validation.
    if (line ~ /^"(compatibility|metadata)"[ \t]*:/ || line ~ /^'(compatibility|metadata)'[ \t]*:/) {
      sub(/^["']/, "", line); sub(/["'][ \t]*:/, ":", line)
    }
    if (line ~ /^(compatibility|metadata)[ \t]+:/) sub(/[ \t]+:/, ":", line)
    if (line ~ /^(compatibility|metadata):[^ \t]/) {
      error("optional fields require a space after the field colon")
      next
    }
    if (line ~ /^compatibility:/) {
      if (seen_compat++) error("duplicate compatibility field")
      sub(/^compatibility:[ \t]*/, "", line)
      if (string_value(line,"compatibility") && (character_length(scalar)<1 || character_length(scalar)>500))
        error("compatibility must contain 1-500 characters")
      mode="inline"
    } else if (line ~ /^metadata:/) {
      if (seen_meta++) error("duplicate metadata field")
      sub(/^metadata:[ \t]*/, "", line)
      entries=0; indent=0
      if (line=="") mode="metadata"
      else if (substr(line,1,1)=="{") { flow_map(line); mode="inline" }
      else error("metadata must be a flat string map (block form or {key: value})")
    }
  } else if (mode=="inline") {
    error("optional fields require single-line strings or a flat metadata block map")
  } else if (mode=="metadata") {
    match($0,/^[ \t]*/); current_indent=RLENGTH
    if ($0 ~ /^ *\t/) error("metadata: use spaces for indentation")
    if (!indent) indent=current_indent
    if (indent!=current_indent) error("metadata: nested or multiline values are unsupported; use single-line strings")
    else pair(line)
  } else {
    check_required_child($0,line)
  }
}
END { exit failed ? 1 : 0 }
