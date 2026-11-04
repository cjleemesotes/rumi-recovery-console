# Haiku code-understanding evaluation

Completed November 4, 2026. The five existing owner sessions researched their areas, proposed guidance and evaluation questions, and reviewed the current code. The coordinator consolidated the guides; the existing Opus integration session ran and graded three fresh, short-lived Haiku Claude Code sessions. The original five sessions and their models were preserved.

## Guidance delivered

| File | Purpose |
| --- | --- |
| [Root CLAUDE.md](../../../CLAUDE.md) | Commands, ownership, architecture, recovery invariants and a small-change workflow |
| [Frontend](../../../frontend/CLAUDE.md) | Screen/DOM map, API handling, uncertainty, rendering and browser checks |
| [Backend](../../../backend/CLAUDE.md) | Routes, body validation, static serving, roots and binding |
| [Demo](../../../demo/CLAUDE.md) | Fresh-process sequence, strict confirmation, identities and extension recipes |
| [Integration](../../../integration/CLAUDE.md) | Independent expectations, isolated checks, process ownership and adding cases |
| [Rumi reference](../../RUMI_GUIDE.md) | Existing API, persistence/cache semantics and crash fixture |

The five CLAUDE.md files are 39–63 lines each. Rumi guidance stays outside the dependency checkout. Draft review corrected the pending-call list shape, the launcher's Rumi import, random-ID persistence wording and the distinction between checking disk for staleness and refreshing an agent's history.

This layout follows Claude Code's documented ancestor/nested instruction loading and short-guide recommendation. See [research notes](RESEARCH.md) and [official memory documentation](https://code.claude.com/docs/en/memory).

## Results

All sessions used the actual model `claude-haiku-5-5` on Claude Code 2.1.318, with no model fallback. They had Read/Glob/Grep plus response-schema formatting, no command execution, no write tools and no MCP tools. The answer key was sealed outside the workspace until all runs ended. All three completed successfully without held-out access.

| Trial | Headline score | Verdict | Wall time |
| --- | --- | --- | --- |
| Frontend and HTTP | 8/8 | PASS | 50.4 s |
| Recovery semantics | 7/8 | PASS | 73.2 s |
| Extension and verification planning | 8/8 | PASS | 101.9 s |
| Total | **23/24** | **3/3 PASS** | **225.5 s** |

All 37 enumerated facts were answered correctly with supporting source evidence. One additional supporting citation put the agent-type comparison in phases.py; the actual check is in workers/history.py. The recovery trial lost one headline point for that misattribution. CLI-reported total cost was approximately $0.0622.

The third trial explicitly opened root/integration guides before the source. The first two consumed documentation snippets through Grep; automatic CLAUDE.md loading is plausible but not proven by those stream logs. Self-reported guide use is distinguished from observed reads in [the detailed scores](scores.md).

The scoring sheet initially misstated the maximum fact points. A mechanical recount corrected the maxima from 34/30/26 to 26/28/20, while preserving the sealed key, every fact, per-fact scale and pass threshold. The detailed scores disclose the erratum and the subsequent correction of two guide-use deductions after checking Grep output. No run was replaced and no retest was needed.

## Practical conclusion and limits

These guides and narrow, source-grounded prompts supported useful comprehension of the console's HTTP behavior, safe recovery sequence and test-extension boundaries. Haiku is a reasonable candidate for bounded tasks here with explicit verification. Check its citations and review any implementation against the same recovery invariants.

This was a three-task comprehension/planning evaluation, not an implementation benchmark or a controlled comparison proving that the guides caused an improvement. No code change proposed by Haiku was applied. A nullable-cell rendering observation was outside the supported response shape and was not treated as a demonstrated product defect.

Application files, runtime data and Rumi's existing local changes were preserved. No application-flow tests were rerun for this documentation-only task; the previously tested application source is byte-identical. The coordinator verified the preserved fingerprints separately.

## Reproducibility

- [Frozen rubric](rubric-final.md), [original sealed key](answer-key-v1.md), [detailed grading](scores.md), and the prompts in prompts/ are published.
- Raw answers, command/model/usage metadata, tool traces, guidance snapshots, machine fingerprints and the local harness remain in the prepared workspace and are excluded from Git. They can contain local paths and process metadata; this repository publishes the reviewed summaries rather than those operational records.
