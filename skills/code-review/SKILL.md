---
name: code-review
description: Review code changes for concrete, actionable defects and regressions. Use when asked to review a diff, branch, pull request, commit, patch, or implementation; do not activate for requests that only ask to implement or explain code.
---

# Code Review

Review the requested change as a critic, not as its author. Do not modify code unless the user also asks for fixes.

## Establish the review scope

- Determine the intended comparison from the user's request and repository state. Inspect repository instructions before evaluating code.
- If the base is not specified, use the most defensible local comparison, such as the working tree plus staged changes, or the requested commit against its first parent. State the comparison only when it is not obvious.
- Read enough surrounding code, tests, types, configuration, and call sites to understand changed behavior. Do not review the patch in isolation when correctness depends on nearby code.
- Preserve unrelated user changes and avoid commands that mutate the worktree.

## Evaluate findings

Report only issues introduced by the reviewed change that a reasonable author would want to fix. A finding must identify an observable failure, security problem, data loss risk, incompatible behavior, or meaningful maintainability defect with a concrete consequence.

Before reporting a finding:

1. Verify the claim against actual control flow, data contracts, platform behavior, and relevant call sites.
2. Identify the inputs or runtime conditions that trigger it.
3. Check whether validation, fallback behavior, tests, or surrounding code already prevents it.
4. Prefer a focused test or static check when it can confirm the issue without changing repository state.

Do not report speculative concerns, personal style preferences, pre-existing defects, deliberate product behavior, missing tests without an associated behavioral risk, or tool failures caused only by the local environment. Consolidate findings that share one root cause.

Use these priorities:

- **P0:** Immediate, broadly reproducible catastrophic impact; blocks release or operation.
- **P1:** Serious defect likely to affect normal use, security, or data integrity.
- **P2:** Real defect with narrower inputs, configurations, or impact.
- **P3:** Low-impact correctness or maintainability defect that is still worth fixing.

## Report the review

Lead with findings ordered by priority. For each finding:

- Use a concise title containing the priority and the broken behavior.
- Point to the smallest relevant changed line range.
- Explain the concrete failure and triggering conditions in one compact paragraph.
- Avoid prescribing a full implementation unless it is necessary to make the defect understandable.

Use inline code comments when the review interface supports them. Otherwise provide a short findings list with file and line references.

If there are no actionable findings, say so plainly. Then mention only material residual risks or verification gaps, such as tests that could not run. Keep any summary secondary to the findings.
