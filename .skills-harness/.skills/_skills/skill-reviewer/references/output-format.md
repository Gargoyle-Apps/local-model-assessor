# Output format

> Load when returning findings on the **Output** workflow step.

## Delegated pass or caller-specified format

Return scoped findings to the calling review in its required format or schema. Preserve its severity convention, file/line locations, evidence, and coverage requirements. The caller owns the final repository report and overall verdict. Do not replace that report with a skill-only summary, an extra approval footer, or a separate hosted comment. State which skills were checked and any incomplete checks or independent-review requirements when the caller's format permits; otherwise pass that information to the caller separately.

## Direct skill review without a specified format

Return a report in chat using this structure; post to a PR/MR only when authorized:

```
### skill-reviewer findings

**Summary:** <N> finding(s) — <H> HIGH, <M> MEDIUM, <L> LOW
**Risk tier indicators:** <comma-separated list from the heuristic table, or "none">

#### <relative-path>:<line-or-section>

- [<severity>] <short title>
  Evidence: <quoted snippet>
  Why it matters: <1-2 sentences>
  Recommendation: <concrete fix; cite agentskills.io or harness docs when relevant>
  Caveat: <only when applicable>

(repeat per finding)
```

When no findings remain, say: `No findings in the reviewed skill scope.` This reports the result of this pass, not approval of the skill or the repository.

Identify HIGH findings as blocking for the reviewed skill changes. State required independent human review for changes to this rubric or its review pipeline, and identify any unreviewed areas. Submit hosted review actions only when authorized and according to the repository's policy; never auto-approve.
