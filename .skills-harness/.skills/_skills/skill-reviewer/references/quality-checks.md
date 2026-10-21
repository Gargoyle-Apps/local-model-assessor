# Quality checks (Q1–Q7)

> Load when walking the **Quality** phase. Aligns with [agentskills.io skill creation](https://agentskills.io/skill-creation/best-practices) so reviewers and authors check against the same bar.

## Q1. Description triggering (HIGH when broken, MEDIUM when weak)

Native discovery routes from `name` and `description`; harness `triggers` supplement fallback lookup. Apply [optimizing-descriptions](https://agentskills.io/skill-creation/optimizing-descriptions):

| Rule | Check | Severity if violated |
|---|---|---|
| States what + when | Describes user intent and trigger contexts, not internal mechanics only | MEDIUM |
| Harness `triggers` | Phrases match how users ask; not single vague words | MEDIUM |
| Concise, ≤1024 chars | Hard cap on `description` | HIGH if over |

Keep descriptions self-sufficient: essential scope must not depend on harness `triggers`, a name prefix, or index notes. Shared routing terms are valid; procedural summaries and repeated outcomes may be removable. When reviewing a changed description or proposing a discovery-cost finding, load `references/description-cost.md`. Require a concrete shorter alternative and preserved positive/near-miss routing before flagging avoidable cost; length alone is not a finding.

If the user reports false positives or false negatives, recommend a trigger-eval set (~20 queries: 8–10 should-trigger + 8–10 near-miss should-not-trigger). Optionally store cases in `references/<evals>.json`.

## Q2. SKILL.md size and progressive disclosure (MEDIUM)

| Check | Threshold | Severity |
|---|---|---|
| `SKILL.md` line count | > 200 lines, no nested references | MEDIUM |
| `SKILL.md` line count | > 500 lines | MEDIUM (firmer) |
| Reference link without a gate | any | MEDIUM |
| Reference file > 120 lines, no TOC | any | MEDIUM |
| Reference nesting > 1 level deep from SKILL.md | any | MEDIUM |

**Shift-left:** usage context belongs before the file is loaded. A bare `see references/foo.md` without when-to-load context defeats progressive disclosure. Quote the line and propose a gated rewrite.

## Q2b. Scope (MEDIUM if too broad)

Symptoms: description lists 3+ unrelated triggers; parallel unrelated workflows; references organized by unrelated tasks. Recommend splitting into narrower skills with focused descriptions.

## Q2c. Harmful over-compression (MEDIUM / HIGH)

Lite, direct prose is the kit default. Concise, complete sentences are not a finding. Flag compression only when it removes information needed to route or execute safely.

| Check | Severity |
|---|---|
| `description` or `triggers` use dropped grammar, invented abbreviations, or shorthand instead of natural user language | MEDIUM; HIGH if triggering is broken |
| Numbered steps omit the actor, conjunction, or ordering needed to distinguish sequence or responsibility | MEDIUM; HIGH if the omission affects a safety, confirmation, irreversible-action, or required-order sequence |
| Compression obscures whether text is a confirmation gate or an instruction to act | HIGH |
| Compression weakens a security warning, irreversible-action warning, or required execution order | HIGH |

Recommend the smallest clear rewrite: restore the missing actor, conjunction, confirmation, or order, then resume lite prose. Do not request a full stylistic rewrite.

Do not flag arrows or fragments that express causality unambiguously in ordinary non-safety prose.

## Q3. Eval coverage (MEDIUM if missing)

| Check | Severity |
|---|---|
| New skill with no trigger eval cases | MEDIUM — recommend 2–3 cases |
| Eval set exists but no with-skill vs without-skill run | MEDIUM |
| Cases pass without the skill loaded | MEDIUM — skill may not earn its tokens |

## Q4. Workflow shape (LOW / MEDIUM)

| Check | Severity |
|---|---|
| Wall of prose, no numbered steps | MEDIUM for procedural skills |
| Heavy `ALWAYS` / `NEVER` without rationale | MEDIUM |

## Q5. Frontmatter completeness (LOW / MEDIUM)

Harness skills require: `name`, `description`, `triggers`, `dependencies`, `version`. See checks 1–4 in `references/security-checks.md` for agentskills.io contract.

| Check | Severity |
|---|---|
| Missing harness fields | HIGH in this kit |
| `name` doesn't match parent directory | HIGH |

## Q6. Best-effort / no-ping-pong (LOW)

Recommend skills include: do best-effort work before asking; batch questions into one message.

## Q7. Token-tax awareness (informational)

Keep three budgets separate:

| Budget | Measure | What reduces it |
|---|---|---|
| Native discovery | Names + descriptions exposed by the host; report character estimates and the method | Remove unnecessary discovery text while preserving routing |
| Activation | Loaded `SKILL.md`, unconditional dependencies, and references actually needed on this path | Prune unnecessary dependencies, deduplicate, gate optional detail |
| Fallback lookup | Index content actually read; distinguish full-file bytes from observed reads | Targeted search or justified generated sub-indexes |

Use `check.sh` estimates when available; configurable warnings are review signals, not universal runtime limits. Do not label characters or bytes as measured tokens. Splitting indexes does not shorten native descriptions. For activation above roughly 3k estimated tokens, inspect optional detail and dependencies; do not split a coherent workflow merely to meet a threshold. Keep findings scoped to changed skills. If aggregate discovery pressure needs a catalog-wide audit, hand the measurements to **skill-catalog-maintainer** without silently rewriting siblings.
