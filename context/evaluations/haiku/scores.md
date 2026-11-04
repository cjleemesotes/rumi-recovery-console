# Haiku trial scores

These trials were graded against the sealed key `answer-key-v1.md` (SHA-256 `3b2de3a5…0eb0b1`, re-verified after unsealing, file unchanged) and the frozen `rubric-final.md`. All three trials were VALID:

- model `claude-haiku-5-5` only, with no fallback or substitution
- Read/Glob/Grep only, plus one internal `StructuredOutput` formatter call each
- no held-out or outside reads
- exit 0 with a `success` result
- the 40-file source fingerprint unchanged after every trial

## Erratum: point maxima (an arithmetic error in the sealed key, disclosed rather than hidden)
The headers of the sealed key, and the copies in `rubric-final.md` and `haiku-integration.md` §5, declared maxima of **34 / 30 / 26**. A mechanical recount of the facts actually listed in the key gives **13 / 14 / 10 facts, so the correct maxima are 26 / 28 / 20**.

Nothing else changes: the facts, the [must] markers, the per-fact 0/1/2 scale, the 75% threshold and the headline criteria are all as originally written. The percentages below use the listed facts. The sealed key file itself is left as written, and its hash still matches.

## Results
| Trial | Fact points | [must] ≥ 1 | C1 core | C2 grounding | C3 complete | C4 boundaries | Headline | Critical | Verdict |
|---|---|---|---|---|---|---|---|---|---|
| 1 frontend + HTTP | 26/26 (100%) | 7/7 | 2 | 2 | 2 | 2 | 8/8 | none | **PASS** |
| 2 recovery semantics | 28/28 (100%) | 9/9 | 2 | 2 | 2 | 1 | 7/8 | none | **PASS** |
| 3 extension + verification | 20/20 (100%) | 6/6 | 2 | 2 | 2 | 2 | 8/8 | none | **PASS** |
| **Total** | 74/74 | | | | | | **23/24** | | 3/3 PASS |

**Grading correction (final bounded review):** an earlier version of this table gave trial 1 a C4 of 1 and trial 2 a C4 of 0 (21/24). Those deductions treated "no Read call" as proof that a self-reported guide was never seen. The raw traces show otherwise. Trial 1's successful `Grep` results returned `context/CONTEXT.md` lines, including `:135`, the HTTP limits table, plus `:89` and `:97`. Trial 2's content-mode `Grep` returned root `README.md` lines 1, 3, 31, 50 and 62. Those self-reports are therefore supported by partial-content evidence and are not overclaims. My trace summarizer recorded guide *Reads* only and missed guide content that arrived through Grep; that is my error, now corrected. The rubric is unchanged.

**Citations:** all 128 cited paths exist, and every cited line range lies inside its file (checked mechanically). I also hand-checked a sample against the code: request_handler static map, routes, timeout handling and serve(); server.py exclusive bind; console.js acceptResponse, button wiring and pending rendering; state.py strictness; orchestration.py post-save inspection and timeout; refusal_scenarios and flow_scenarios line references; suite edges-only.

## Deductions (C4 only; every fact was correct)
- **Trial 1, C4 = 2.** No fabricated path or overclaim was found, and the uncertainties were declared. Its `context/CONTEXT.md` self-report is supported by Grep content (`:89`, `:97`, `:135`). Its `backend/` and `frontend/CLAUDE.md` self-reports are plausible automatic loads, because it read files in those folders; they are unprovable, not penalized. Reading `Rumi/rumi-edge` Go files is legitimate, since the files exist.
- **Trial 2, C4 = 1** (one issue): Q8 cites `demo/workers/phases.py:42-43` for the `agent.agent_type != AGENT_TYPE` comparison. The real location is `demo/workers/history.py:42`. This is a misattributed supporting citation; the scored Q8 facts are cited correctly (`contract.py:32-36`, `agent.py:60-62`). Its `README.md` self-report is supported by Grep content (lines 1, 3, 31, 50, 62).
- **Trial 3, C4 = 2.** It explicitly read the root `CLAUDE.md`, `README.md`, `integration/CLAUDE.md` and `integration/README.md` before the integration source, and it declared that the 304 baseline and the ~75 s figure were unverified. Its count reasoning is correct. A B-1 probe adds 1 check from `_create_pending_run` and 10 from the unresolved path of `_check_recovery_refused`, so 11 (304 → 315). Its own sketch adds one more ledger check, so 12 (316). The key's "+10" refers to the helper alone, so this is not penalized.

## Guidance consumption: observed reads versus self-reports
| Trial | Full-file Read (observed) | Partial content via Grep (observed) | Automatic loading (plausible, unprovable) | Self-reported `guidance_files_used` |
|---|---|---|---|---|
| 1 | none | `context/CONTEXT.md` (:89, :97, :135) | root, backend/ and frontend/ CLAUDE.md | backend/CLAUDE.md, frontend/CLAUDE.md, context/CONTEXT.md |
| 2 | none | root `README.md` (1, 3, 31, 50, 62); `demo/README.md:6`; `backend/README.md` (3, 9) | root, demo/ and backend/ CLAUDE.md | CLAUDE.md, demo/CLAUDE.md, README.md, backend/CLAUDE.md |
| 3 | CLAUDE.md, README.md, integration/CLAUDE.md, integration/README.md | (not needed) | backend/CLAUDE.md | the same, plus backend/CLAUDE.md |

The root `CLAUDE.md` is part of every session's startup context, and folder `CLAUDE.md` files load when files in that folder are read. The stream trace cannot show either, so the automatic-loading column is unprovable. Full-file reads and Grep snippets are observed. The results cannot attribute any improvement to the guides, because there was no guideless control.

## Notable correct findings (informational, not scored)
- Trial 1 noticed that ledger table cells render `String(ledgerRow.order_id)` without a null check (`frontend/assets/js/console.js:239`). A null cell would show "null". This is an observation about an out-of-contract response, not a reproduced bug in the supported flow: the ledger columns are NOT NULL, and unknown ledger evidence is represented by null rows/counts rather than nullable cells. No application change was made.
- Trial 2 correctly noted that Rumi's `_results_after` is positional only, and that the demo adds the call-id filter (`demo/workers/history.py:63-79`).

## Usage and duration (from each trial's `summary.json`)
| Trial | Wall time | Duration (API) | Turns | Tool calls | Output tokens | Cost |
|---|---|---|---|---|---|---|
| 1 | 50.4 s | 49.1 s (46.0 s) | 16 | 15 | 8,447 | $0.0151 |
| 2 | 73.2 s | 71.7 s (69.8 s) | 23 | 22 | 14,327 | $0.0184 |
| 3 | 101.9 s | 100.0 s (95.9 s) | 35 | 34 | 20,010 | $0.0287 |

The total cost was $0.0622. No retest was run: no trial was INVALID or failed, and trial 3 observed the guides directly, so the conditional guide-read retest was not needed.
