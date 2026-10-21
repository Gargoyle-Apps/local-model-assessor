# Context optimization

Load when `check.sh` reports direct, transitive, native-metadata, or index-size pressure, or when the user asks to condense an existing skill.

Goal: reduce happy-path context without weakening routing, behavior, safety, or verification.

Bulk caveman rewriting is not an optimization strategy. Keep descriptions and triggers in natural user language, and keep enough grammar in bodies and references to make actor, order, confirmation, causality, and safety explicit.

## Baseline

From the repository root, record direct size for each target:

```bash
wc -lc .skills/_skills/<name>/SKILL.md
```

Expose exact catalog estimates by setting reporting thresholds to zero for one read-only check:

```bash
SKILLS_TRANSITIVE_WARN_BYTES=0 \
SKILLS_NATIVE_METADATA_LIMIT=0 \
SKILLS_INDEX_WARN_BYTES=0 \
  /bin/bash .skills/_harness/check.sh --quiet
```

Use ordinary `check.sh` defaults for pass/fail judgment; zero thresholds above only expose measurements.

## Optimization order

1. Record baseline direct bytes/lines and all `check.sh` context warnings.
2. Tighten routing metadata:
   - Keep `description` focused on what the skill does and when it loads.
   - Remove procedural detail and repeated outcomes; keep descriptions self-sufficient without harness `triggers`, prefixes, or index notes. Shared routing terms are valid.
   - Keep natural trigger phrases and update trigger evals, including near misses.
3. Prune dependency cost:
   - Keep only companions needed on every invocation in `dependencies`.
   - Load branch-specific companions in the exact body step that needs them.
   - Preserve dependency order and cycle safety.
4. Slim the common path:
   - Keep decisions, ordered actions, safety gates, and verification in `SKILL.md`.
   - Move optional detail to a clearly named reference with an explicit load gate.
   - Move deterministic reusable operations to scripts only when code improves reliability.
   - Do not split one coherent workflow merely to reduce line count.
5. Remove duplication between the body and references. Keep one authoritative default per concept.
6. Compare every original behavior branch against the draft. Preserve exact commands, error strings, approvals, and failure handling.
7. Bump changed skill versions, regenerate `_index.md`, run `check.sh --link` and `check.sh`, then run `skill-reviewer`.

## Stop conditions

Stop compressing when another cut would:

- hide when a resource or companion must load;
- weaken trigger precision or safety language;
- make step order ambiguous;
- move common-path instructions behind an optional reference; or
- save context only by creating another overlapping skill.

## Report

Show direct bytes/lines and relevant warning state before and after. Note moved resources, dependency changes, and any routing eval changes. A smaller file that loses behavior is a regression.
