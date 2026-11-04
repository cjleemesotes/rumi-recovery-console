You are evaluating how well you can understand this workspace by reading its CURRENT source code. This is a read-only comprehension task: do not propose or make edits, and do not start servers or run commands.

Answer each question from the code itself. For every claim, give evidence as a repo-relative file path plus line numbers (or a function name) from the source file that implements it. Citing documentation is allowed but does not replace a code citation. If you cannot verify something in code, say so in "uncertainties" instead of guessing.

Questions (interrupted tool call recovery):

Q1. Which operating-system process, and which module/function inside it, calls Rumi's `record_recovered_result`? How is that process launched? Does the HTTP server process ever construct the agent itself?
Q2. How is the payments ledger read during recovery (access mode, which rows)? List every possible verdict about the ledger evidence, the condition for each, and the error code / HTTP status / phase each non-matching verdict produces.
Q3. What exact value is passed to Rumi as the recovered result, and what is it built from?
Q4. Why is clicking "Recover result" a second time safe? Point to the code in Rumi that decides this, and say what happens if a different result was already saved.
Q5. How does the demo decide which saved tool results belong to the original request? Is a result with the same call id elsewhere in history counted?
Q6. How strictly is the "recovered" flag on a saved result checked? What state does a run end up in if its stored worker exit code is not the expected crash code?
Q7. After the recovery save, what proves completion before the server reports "recovered"? What happens if the recovery worker times out?
Q8. What agent type, agent id and tool call id does every process use, where are they defined, and why must the agent class never be executed as a script (`__main__`)?

Return the structured output required by the provided JSON schema, with one entry per question id (Q1..Q8).
