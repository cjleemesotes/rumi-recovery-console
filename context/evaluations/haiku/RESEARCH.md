# Haiku guidance and evaluation research

Verified November 4, 2026. Installed Claude Code: 2.1.318 (`claude --version`).

## Instruction layout

Use one short root `CLAUDE.md` for shared commands, architecture and invariants, then guides in frontend/, backend/, demo/ and integration/. The Rumi dependency gets a linked guide in context/ so its checkout is untouched. Avoid importing the long historical reports into every session.

Claude Code loads ancestor instruction files at startup and discovers nested files as their folders are read. Its documentation recommends keeping each guide below 200 lines. A fresh session is appropriate for testing newly written guidance. Source: [Claude Code memory documentation](https://code.claude.com/docs/en/memory).

## Model and execution

The documented current Haiku model ID is `claude-haiku-5-5`. Select it explicitly and record the actual returned model, rather than treating an alias or a different model's answer as a Haiku result. Availability on this account still requires an actual trial. Source: [Model configuration](https://code.claude.com/docs/en/model-config).

Use short-lived Claude Code CLI sessions, separate from the five existing owner sessions. Print mode runs the normal agent loop and can emit streaming JSON with tool calls, the final response and usage metadata. Bare mode disables CLAUDE.md discovery and is unsuitable for this guided evaluation. Source: [Programmatic Claude Code](https://code.claude.com/docs/en/headless).

Local CLI help confirms the tools allow-list, noninteractive permission handling, structured output, explicit model selection, temporary settings and disabled session persistence options. Restrict evaluation tools to Read/Glob/Grep; do not give the trials command execution or write tools. Keep any model or account limitation explicit. Do not change global configuration or the existing owners' models.

## Evaluation scope

Three independent guided code-comprehension trials: frontend/HTTP, recovery semantics, and extension/verification. Freeze prompts and grading criteria before seeing answers. Require source evidence and concrete reasoning. Score correctness and critical safety invariants separately; do not equate a plausible summary with a successful implementation.

These are qualitative guided-comprehension checks, with no unguided control group. They can find missing or misleading guidance; they cannot establish a model ranking or prove that the guidance caused an improvement. No product edits are part of this task.
