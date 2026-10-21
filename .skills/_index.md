# Skills Index

Kit version: see `.skills/_meta.yml` (optional metadata only). Human-facing copies also appear in root `README.md` and `AGENTS_skills.md`; bump them with the **kit-release** skill and validate with `check.sh`.

Load a skill only when the task clearly requires it.
Read the full `SKILL.md` only at that point — never preemptively.

| name | description | triggers |
|------|-------------|----------|
| caveman-commit | When the user wants to write or generate a git commit message — ultra-terse Conventional Commits (subject ≤50 chars, why over what). | write a commit, commit message, generate commit, caveman commit, /commit, /caveman-commit |
| caveman-review | Formats code-review findings as terse, actionable comments when the user requests caveman review, terse review, or one-line review comments. General code/PR reviews and /review or /codereview alone do not select this style. | caveman review, terse code review, one-line review comments, /caveman-review |
| caveman | When the user wants terse or compressed replies without losing technical accuracy — ultra-compressed caveman output mode with lite/full/ultra/wenyan levels (~75% fewer tokens). | caveman mode, talk like caveman, use caveman, less tokens, be brief, compress output, /caveman |
| harness-subtree | Install or update the skills-harness kit in a consumer repo as a git subtree at .skills-harness/. | deploy harness as subtree, install harness as subtree, vendor skills-harness, update vendored harness, subtree pull skills-harness, skills harness subtree, add skills-harness subtree, migrate manual install to subtree, convert harness install to subtree |
| harness-upgrade | Upgrade a skills-harness install to the latest version with native IDE discovery. | upgrade harness, update harness, migrate harness, add native discovery, enable IDE symlinks, update skills system |
| kit-release | Bump skills-harness kit semver; keep CHANGELOG, README, AGENTS_skills.md, _meta.yml in sync. | bump kit version, bump harness version, release skills harness, cut a harness release, skills-harness version, kit release |
| skill-author | Creates and registers new harness skills. Load when the user asks to write, author, add, or register a skill. | write a skill, new skill, register a skill |
| skill-catalog-maintainer | Audits and optimizes skills under .skills/_skills/ for overlap, routing, context cost, dependencies, and index drift; edits require dry-run and confirmation. | skill inventory, catalog health, duplicate skill triggers, skill overlap, split this skill, skill catalog audit, reduce skill context, condense this skill, trim skill tokens |
| skill-conflicts | Detect conflicts between repo-managed skills and same-named skills/slash-commands in the user's IDE config. | detect skill conflicts, skill conflict, conflicting skills, skill name collision, check skill conflicts, does my config conflict with repo skills |
| skill-export | Exports a skill to another repository by PR, adding target-only upstream lineage without modifying the source repo. | export skill, publish skill, share skill to another repo |
| skill-import | Imports or refreshes a vendored skill from another repository with upstream lineage and security review. | import skill, vendor skill, pull skill from repo, update vendored skill |
| skill-reviewer | Reviews specific Agent Skills (SKILL.md and bundled resources) for quality, security, and layout. Use for a direct skill review or a skill-scoped check assigned by an authoring or repo review workflow. General code/PR reviews and /review or /codereview remain host-led; this skill only contributes scoped findings. | review skill, skill review, audit SKILL.md, review skill changes, skill security review, review this skill |
| skill-talker | Answers read-only questions about repo skills and maps goals to entries in the harness catalog. Load when users ask what a skill does, which skill fits, why routing occurred, or how a skill would approach a task; it may offer an explicit handoff but never executes another skill without authorization. | what does this skill do, how does this skill work, when does this skill trigger, why did this skill trigger, why did this skill not trigger, which skill should I use, do we have a skill for this, how would I do this with a skill, how would the harness handle this, compare these skills |
| skill-template | Documents the canonical SKILL.md layout and refactor guide for converting rules or docs into skills. Load when the user needs format guidance, reformatting, or conversion — not when authoring a new skill from scratch. | skill format, reformat skill, convert rule, skill layout, refactor to skill |
| toon-export | Encode or validate agent-facing TOON from JSON, YAML, CSV, or emitter output using a JSON hub, the official CLI, and strict decode. | export TOON, validate TOON, JSON to TOON, write a .toon file, TOON emitter, token-efficient structured data |

Add a row here whenever a new skill is added to `.skills/_skills/`.
