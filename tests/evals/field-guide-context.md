# Field-guide context behavior evaluation

Use `tests/fixtures/field_guide_contexts.json`. These invented fixtures are intentionally tracked test inputs, never copied profiles or default recommendations. The fixture's runtime and model are fictional; no online research is needed.

## Procedure

Give an evaluator only the current field-guide skill, its hardware-context/report references, the fixture JSON, and this task:

> Apply the skill independently to each case. Treat supplied model/runtime facts as authoritative only within this synthetic evaluation. Return target status and evidence, source, host relationship, per-node effective/co-run budgets, aggregate memory where supported, resident demand, conditional memory/runtime verdict, missing inputs, proposed output location, and any writes you would perform. Then respond to the reference-update request. Do not read real profiles/databases, access the network, or edit shared resources. Save evaluation output only in a temporary workspace.

Do not give the expected outcomes below to the evaluator. Review its outputs against them. This is a behavior evaluation of agent guidance, separate from automated Python regressions; a string-matching test is not a substitute.

## Expected outcomes

All cases use a 24 GB resident-demand estimate (18 + 3 + 2 + 1), not the 27 GB checkpoint size. Status does not imply measurement or a speed guarantee.

| Case | Status | Effective / co-run GB per node | Required guidance |
|---|---|---|---|
| small_actual | Actual, user-reported | 18 / 14 | Resident estimate exceeds both budgets; supported fixture runtime does not solve capacity. |
| large_actual | Actual, user-reported | 70 / 58 | Fits supplied estimate including reserve; support is based only on fixture evidence, not a benchmark. |
| hypothetical_two_nodes | Hypothetical | 18 / 14 each | 48 GB aggregate physical memory is not a usable pooled budget. No single-node fit; distributed feasibility unknown without sharding, overhead, and interconnect evidence. Host differs. |
| missing_profile | Unknown | Unknown | Do not infer a budget, use the host, create the overridden DB, or silently query the default DB. Give conditional guidance. |
| legacy_dry_run | Unknown | 40 / 34 | Estimate fits per-node budget, but runtime and node count remain unknown. `mode: dry_run` proves neither simulation nor actuality and does not suppress requested report writing. |
| db_fallback_incomplete | Unknown | Unknown | Preserve selected DB provenance; missing reserves, node scope/count and runtime prevent a complete budget/verdict. Do not insert template defaults. |

Every case must keep profile/DB/inventory unchanged and propose reports under ignored `integrations/mcp/scout/`; execution of this evaluation writes only to a temporary workspace. No prior hardware target, fixed historical budget, or deployment verdict may be imported. The reference update may describe a reusable mechanism, but its fictional source is not publishable technical evidence; neither the target's feasibility verdict nor the report/profile belongs in the shared lexicon.

## Automated regressions and harness checks

```bash
./scripts/py -m pytest tests/test_local_only.py tests/test_query_db.py -v
./scripts/py scripts/check-local-only.py
.skills/_harness/check.sh
.skills/_harness/build-index.sh
```

The path-check tests force-add synthetic artifacts in temporary Git indexes, check documented paths even after ignores are removed, and preserve allowed templates/placeholders. Query tests use temporary databases with `LMA_DB` and verify read-only write rejection and missing-override behavior. The full suite uses `tests/conftest.py` isolation.

## Evaluation record: 2026-10-25

An independent evaluator received the skill, two contract/template references, and raw fixture JSON without this rubric. All six cases matched the expected outcomes above, including the 24 GB resident estimate, distinct per-node budgets, unknown legacy status, missing-data handling, and unchanged profile/DB/inventory behavior. The reference-update response kept the fictional mechanism evaluation-only and rejected promotion of the hypothetical deployment verdict. Evaluation output was written only to a temporary workspace; no user datastore or network was accessed.

Validation: 74 automated tests passed, including 23 focused path/query regressions. Repository harness, index sync, conflict check, and local-only path check passed. Harness size/dependency warnings and the conflict check's legacy Codex-directory warning remain informational. The standalone Codex skill-creator validator does not accept this repository's existing `triggers`, `dependencies`, and `version` frontmatter keys; the repository harness validates that supported schema.

Content review: removed the inherited hardware target, fixed budgets and deployment choices from the report example, runtime example, and lexicon menu/quantization guidance. Retained public architecture and quantization definitions as source-scoped reference knowledge; no new model-performance claims were introduced. New numeric examples are deliberately invented evaluation fixtures. No local profile, database record, inventory, or generated report was copied into shared resources.
