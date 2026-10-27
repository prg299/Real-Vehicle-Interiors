# Real Vehicle Interiors

Read `README.md`, the affected system documentation and
`docs/visual-iteration-workflow.md` before substantial visual work. Preserve
unrelated dirty files and the existing source/package/save separation. Follow
the owner's and global resource, production-input, artwork and preservation
instructions; this file adds project workflow rules without replacing them.

## Parallel visual work

For substantial visual batches, use parallel subagents with up to three
specialists plus the main integration owner. Assign concrete disjoint scopes:
geometry/source diagnosis, source/binding validation, and original-image review.
Combine or omit roles when the task is small; do not add delegation overhead to
trivial edits. Give each writing agent exclusive file ownership. Read-only
reviewers return findings to that owner instead of editing shared files.

Use **GPT-6.1 Sol** (`gpt-6.1-sol`) with **high** reasoning for geometry/source
diagnosis and visual review. Use **medium** reasoning for mechanical scoped
edits. The main agent owns integration and judgment about when broader review is
needed. Do not default every job to maximum effort. When selecting a different
model/effort from the parent, use a fresh subagent context with a complete task
brief and explicit paths/contracts.

Only one agent owns shared production Java, shaders, generators and bindings for
a grouped change. Only the main integration/native owner may build/freeze the
candidate and acquire the native lease. Other agents must not start competing
builds, alter frozen runtime inputs, replace the default package, or launch PZ.
Offline original-image review and read-only source review may proceed in parallel.

## Finite iteration

Use the shared PZ coordinator at
`D:/Stuff/Projects/Game Mods/games/project-zomboid/tools/run-mod-test.mjs`
for all checks, builds and captures; read that workspace's
`games/project-zomboid/TESTING.md` for admission and ownership. Inspect `status`
before a native handoff. Exit 75 is deferred work, with no bypass or retry loop.
Use a saved `.ps1` and `pwsh -File` for multi-step guarded commands; avoid nested
`-Command` strings with interpolated exit-code or path variables.

Use the existing drivers and package/manifest contracts. Group related changes,
build once, freeze the candidate, preflight actual parser arguments and capture
counts with `dev/native-review-plan.py`, then run a bounded representative pass.
Broaden after its original-image review passes; retain final required coverage
and explicitly identify unverified states. Reuse checks only on unchanged inputs.

For an already-built candidate with prior pilot evidence, prefer one small
grouped capture over an extra startup merely to split the batch. Follow the
workflow document's mode/count tables, stop rules, cleanup and evidence limits.
Review originals during iteration; build the final gallery after stable visual
acceptance. Planning does not authorize deployment, load-order changes or upload.
