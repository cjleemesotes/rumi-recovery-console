You are evaluating how well you can plan a change in this workspace by reading its CURRENT source code. This is a read-only planning task: do NOT edit files, start servers or run commands. Describe what you would do.

Answer each question from the code itself. For every claim, give evidence as a repo-relative file path plus line numbers (or a function name). Citing documentation is allowed but does not replace a code citation. If you cannot verify something in code, say so in "uncertainties" instead of guessing.

Scenario: a maintainer wants an automated check proving that a demo run whose ledger contains exactly one payment row with order_id "B-1" and amount 42 is never reported as recovered.

Q1. Before any change: what does the current application do with that ledger today (verdict, error code, HTTP status of the recover request, whether anything is written)? Cite the deciding code.
Q2. Where exactly would you add the new automated check (file and function), and which existing helpers would you reuse to create the run, alter its ledger and assert the refusal? Sketch the call(s) with their arguments.
Q3. Where should the new check's expected values live, and should they be imported from the application's own constants? Explain why, citing code or comments.
Q4. Which command verifies the change, run from where? How does it avoid touching any running console and its saved data? What should the reported check total do?
Q5. List what this change must NOT touch or alter (processes, ports, data, folders, identifiers, contracts), with evidence.
Q6. What does the check command's `--edges-only` option run?

Return the structured output required by the provided JSON schema, with one entry per question id (Q1..Q6).
