# Finite native visual iteration

Use the existing `dev/native-body-tests.py`, `dev/native-wall-sequence.py` and
`build/rv/native-fleet-20261024` package/plan contracts. This workflow reduces
feedback scope before a candidate earns a broader audit. It does not reduce the
final coverage promised to the owner or establish acceptance for uncaptured bodies.

## Ownership and parallel work

| Role | Scope | Effort |
| --- | --- | --- |
| Implementation owner | One owner edits shared Java, shader, generator and binding files; groups one causal change | High for diagnosis; medium for mechanical scoped edits |
| Source/binding reviewer | Read-only diff, exact source/native aliases, preservation contracts and affected signatures | GPT-6.1 Sol, high |
| Native owner (coordinator/root) | Sole native lease, immutable candidate, finite sequence, receipts and cleanup | Main integration owner |
| Original-image auditor | Opens original photographs offline while implementation/review continues; reports script, heading, state, path and defect | GPT-6.1 Sol, high |

For substantial visual batches, use up to three parallel specialists plus the
main integration owner, with concrete disjoint scopes. Use GPT-6.1 Sol
(`gpt-6.1-sol`) with high reasoning for geometry/source diagnosis and visual
review, and medium for mechanical scoped edits; do not apply maximum effort to
every task. Keep integration and build/native ownership with the main agent.
Assign disjoint files before parallel edits. Reviewers return findings to the shared-file
owner; they do not independently patch the same shaders or launch another game.
Only the native owner advances the capture queue. Reuse completed checks on exact
unchanged inputs. Keep a single candidate manifest and driver hashes per run.

## Choose the smallest useful first pass

| Change class | First native gate | Broaden after original-image review passes |
| --- | --- | --- |
| Vanilla material/finish | One affected vanilla script, two revealing headings, furnished photograph | Five affected vanilla representatives, then required variants/headings |
| Native floor, roof or join | One affected script, two headings, furnished plus empty photographs | Affected geometry/source signatures; use full opening matrix only for opening defects |
| Shared Java/shader/native contract | One affected vanilla plus one representative approved KI5 control | Affected signatures and final regression coverage once after the grouped change stabilizes |
| Local binding or source repair | Exact affected script and defect heading; control from same signature if needed | Other variants sharing that binding, then final promised coverage |
| Saved state or interaction | Existing focused state/input driver | Cold load/multiplayer only when the change affects those contracts |

For the five vanilla families, the established exact representatives are
`Base.VanAmbulance`, `Base.VanSeats`, `Base.VanRadio`, `Base.StepVan` and
`Base.Van`. Choose KI5 control from the native draw/contract actually touched
(for example the approved F350); add E150/Scamp controls when their distinct draw
paths are affected. One KI5 photograph cannot stand for all KI5 geometry.

Use judgment when the grouped candidate is already built: a five-script,
two-heading furnished-only pass is just ten originals in one startup. When
existing pilot evidence has already resolved the uncertainty, do not add another
startup merely to split that small pass. Keep the one-script-first gate for a
new uncertain material treatment; skip redundant pilot/build work on unchanged
inputs.

Stop a failed pilot, identify its first actionable defect, group its source fix
with closely related fixes, and build once. Do not capture the remaining fleet
after a shared pilot failure. If attribution remains uncertain, permit one
focused diagnostic pass (same pose/tick and unchanged-input control), then pause
native expansion until that question is resolved.

## Count what the current driver actually captures

`--headings N,S` is one argument value. `--headings N S` is invalid.
`--only` repeats for each exact script. `--photos-only` implies `--variants`;
`--empty-photos` requires photography mode. Do not combine photography with
`--empty-controls`, isolation, material diagnostics or opening diagnostics.

The help text's "four photographs" assumes four headings; it does not mean four
photographs for each heading. Counts below are for one script at one heading:

| Mode | Ledger originals | Other originals | Total photographs |
| --- | ---: | ---: | ---: |
| `--photos-only` | 1 furnished | 0 | 1 |
| `--photos-only --door-photo-part ID` | 1 furnished + 3 closed/open/restored leaf | 0 | 4 |
| `--photos-only --empty-photos` | 1 furnished + 1 empty High + 2 empty details + 1 restored | 0 | 5 |
| `--variants` | 1 furnished + 2 interior details + 1 reentered | 1 outside | 5 |
| `--variants --empty-controls` | Previous 4 + 3 empty heights + 1 empty camera cut + 2 empty details + 1 restored | 1 outside | 12 |

The outside photograph uses `h.capture` directly and is absent from the body
`frames.jsonl` ledger. Track both ledger count and all-image count. Full opening
matrices add live door/window/openability-dependent frames; count them from
their measured contracts instead of borrowing the variants formula.

The focused door-photography option requires an exact physical part from the
selected script's live door contract. The basic E150 short body has fixed side
panels; use a resolved side-door variant for that test. Door poses are native
renderer fixtures; production Interact input still owns entry and exit. Combining
the option with empty photography adds its three leaf captures to the five
existing floor/detail photographs, giving eight originals per script and heading.

BG2 selected 8 scripts × 2 headings with `--variants --empty-controls`, so its
declared 80 originals understates **176 ledger originals / 192 total photographs**.
The parser-only helper `prepare-bg2-parser-proof.py` fixed the heading syntax but
printed the wrong 5-per-pose count. Preserve historical receipts; do not treat
that declaration as a completed visual audit.

## Preflight before acquiring the native lease

`dev/native-review-plan.py` is read-only: it reuses the real driver's parser and
pre-I/O assertions, reads supported source script IDs and walks the actual
capture branches without importing/launching native helpers. It rejects dynamic
opening/isolation matrices and other uncounted modes. It reports driver SHA-256,
ledger/all-image counts, verifies hashes when an existing plan declares them,
and exits 2 on a declared total mismatch. It never creates a run, edits a plan,
copies a package, opens a save or installs anything.

Run preflight and every check/build/capture through the shared coordinator from
the canonical checkout. Example commands below perform only planning:

```powershell
$coord = 'D:/Stuff/Projects/Game Mods/games/project-zomboid/tools/run-mod-test.mjs'
node $coord status
node $coord run --kind check --name rvi-material-pilot-plan -- python dev/native-review-plan.py --expect-total 2 -- --photos-only --native-camera --only Base.Van --headings N,S
node $coord run --kind check --name rvi-empty-pilot-plan -- python dev/native-review-plan.py --expect-total 10 -- --photos-only --empty-photos --native-camera --only Base.Van --headings N,S
node $coord run --kind check --name rvi-bg2-plan-audit -- python dev/native-review-plan.py --plan build/rv/native-fleet-20261024/bg2-stock-review.json
```

The last command should fail the historical 80-total declaration if its frozen
hashes still match; a changed hash fails earlier and requires a fresh plan.
Do not silently rewrite BG2 or resume it as an approved plan.

For a new plan, record exact arguments, expected ledger/total photographs,
affected signatures, package manifest/hash, driver hashes, baseline image paths,
the first question each phase answers, finite lifetime limit and stop rule.
Sequence phases own their `--output-name` and `--keep-open` flags. The existing
sequence permits 1–8 phases and requires its established
`ki5-walls-20261024-` run-name prefix. Its stop file is checked between cases and
phases, so retain the outer lifetime deadline for a stalled current case.

## One grouped build, frozen review, finite cleanup

1. Snapshot the current dirty-tree scope and approved visual reference. Read the
   original frames before proposing another material change. Implementation and
   read-only source review can overlap; both must finish before freezing inputs.
2. Run focused source/binding/preservation checks, then one grouped guarded
   build. Freeze its output separately from the default package using the
   existing package/manifest pattern. Do not rebuild unchanged source for each
   camera angle or reviewer. Generated images are proposals; native captures
   prove the rendered result.
3. Preflight exact parser flags, actual counts and frozen hashes. Acquire the
   single coordinator native lease. Existing wrappers may temporarily replace
   the default package and restore it in `finally`; only the native owner may
   perform that handoff, and must first verify its restoration source is the
   intended approved default. Use disposable test worlds, never user saves.
4. Run the finite pilot through the existing supported inactive-desktop session
   and real production Interact input. Capture readiness/first-frame markers,
   process identity, exit code, package/driver hashes, native reports and originals.
   Do not confuse spawn/door/wall fixtures with mechanics-menu input evidence.
5. End the owned lifetime, confirm keeper/game children stopped, check coordinator
   status and verify default-package restoration. A sequence `passed` receipt
   means driver completion; the offline auditor must still open every original
   required by that phase and mark defects/unverified coverage explicitly.
   Reopen an ambiguous defect as a single image at original detail and confirm
   its path/hash before attributing it to source or starting another correction.
6. On pilot acceptance, broaden the exact frozen candidate once. Reuse prior
   photographs only where the frozen payload/driver/camera and affected source
   signature justify it; use existing `--reuse-ledger` validation for furnished
   captures. The small planner deliberately rejects reuse because actual skipped
   headings need ledger validation. Label retained older evidence with its real
   package, never as a fresh retake.

Exit 75 means deferred: continue lightweight review and retry only after a
meaningful capacity/ownership change. Never bypass the coordinator, increase
guard limits or kill another chat's/user's processes. Partial capture is partial
evidence. Stop on the first failed contract, wrong payload, invalid framing or
repeated heading pose; retain the failure and clean up owned processes.

Keep native runtime, input, visual review, saved-state, performance and owner
acceptance receipts separate. No deployment, load-order change or publication is
part of iteration planning. Produce the final gallery after stable acceptance;
during iteration use original paths and a short defect list instead of rebuilding
and reviewing a gallery after each tweak.

## Expected work avoided (not a benchmark)

A two-heading material pilot captures 2 originals instead of BG2's 192 (99%
fewer). An empty pilot captures 10 (95% fewer); five vanilla representatives
capture 50, or 60 with one KI5 control, using two-heading empty photography.
Adding two-heading KI5 furnished controls to the material pilot gives 4 originals.
At an illustrative 10 seconds to open/assess each image, reducing 192 to 10
avoids about 30 minutes of reviewer work; substitute measured local review time.
Capture time also falls by avoiding diagnostic states, but startup/build costs
remain. These are scope arithmetic and planning estimates, not measured runtime
speedups. Record actual build/start/capture/review durations on the next owned
run before promising wall-clock savings.
