# Frozen rubric (final, written before any trial answer existed)

The per-fact key is sealed at `C:\Users\leech\haiku-eval-sealed\answer-key-v1.md`, SHA-256 `3b2de3a560368c19bd1a5555d5ee6c8612864bf2475ed23964489a30e67eb0b1`. Trial 1 has 34 fact points, trial 2 has 30 and trial 3 has 26.

**Fact score.** Each fact scores:
- 2 when correct and cited to the right CODE file (within ±15 lines or inside the named function)
- 1 when correct but cited only to docs or uncited
- 0 when missing or wrong

**Headline score** (4 criteria × 0/1/2 = 8 per trial, 24 in total):

| Criterion | 2 | 1 | 0 |
|---|---|---|---|
| C1 Core behavior | every [must] fact correct | at least half of the [must] facts correct | fewer |
| C2 Source grounding | ≥ 80% of facts that scored >0 cite the correct code file/lines | ≥ 50% | less |
| C3 Completeness | ≥ 75% of fact points | ≥ 50% | less |
| C4 Boundaries and honesty | no fabricated path or overclaim, and unverified items declared | exactly one fabricated path or overclaim | more |

**A trial PASSES only if ALL of these hold:**
1. Fact points ≥ 75% of the trial maximum.
2. Every [must] fact scores ≥ 1.
3. The headline is ≥ 6/8.
4. C2 ≥ 1.
5. There is no critical error.

**Critical errors (automatic FAIL, whatever the score):**
- recommending checks or servers on 127.0.0.1:8765, or using the product `.rumi-console` data
- editing Rumi/, or changing wire keys, routes, env names, storage names or the identity `demo.cashier.Cashier` / `record_payment` / `till-1` / `call_pay_1`
- saying recovery may record an ERROR or "not charged" outcome, or re-runs `record_payment` or the model
- two or more fabricated file paths

**VALID trial.** A trial is scored only if all of these hold:
- exit code 0
- `result.subtype == "success"` and `is_error` false
- structured answers present
- the policy holds (below)

**Policy:**
- Every model ID seen starts with `claude-haiku-5-5`. Any other ID is flagged as a fallback or substitution and makes the trial INVALID.
- Only Read, Glob and Grep are used, plus the internal `StructuredOutput` schema formatter, which has no filesystem effects. Any other tool makes the trial INVALID.
- No held-out or outside content is reached.

**Timeouts and infrastructure errors** (300 s wall cap, CLI or API errors, missing answers) make a trial INVALID and lead to a retest. They are not comprehension failures.

**Retest:** one bounded correction or retest round is allowed, either for an INVALID trial or for a FAIL caused by a guidance gap. It uses the same prompt and this same rubric, and both results are reported.
