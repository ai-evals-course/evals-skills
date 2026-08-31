---
name: evals-start
description: >
  Entry point for evals. Use when the user asks for help with evals,
  does not know where to begin, or asks for something no other skill
  in this plugin matches. Do NOT use when a more specific skill in
  this plugin already matches; load that skill directly.
---

# Evals Start

This plugin splits eval work into targeted skills. Your job here is small: find the row below that matches the user's situation, tell the user which skill you are loading and why, then load that skill and follow its workflow from start to finish instead of improvising your own version of it.

| Situation | Skill to load |
|---|---|
| Has traces, wants to find failure modes, no established taxonomy yet | `error-discovery` |
| Has an existing eval pipeline and wants to know if it can be trusted | `eval-audit` |
| Has a known failure mode and wants an LLM judge for it | `write-judge-prompt` |
| Has an LLM judge or evaluator and wants to check its quality | `validate-evaluator` |
| Has no traces to review yet | `generate-synthetic-data`, then `error-discovery` |
| Wants a custom annotation interface for some other labeling task | `build-review-interface` |
| Wants to evaluate a RAG pipeline | `evaluate-rag` |

Most requests that mention error analysis with traces in hand mean `error-discovery`. New users with an existing pipeline usually need `eval-audit` first. This file holds only routing. When in doubt about which row fits, ask the user instead of guessing. The workflow lives in the targeted skill.
