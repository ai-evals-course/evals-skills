---
name: write-code-eval
description: >
  Write deterministic, code-based evaluators (e.g., schema checks, regex,
  execution tests, length limits) for failure modes that need no
  interpretation. Use when a failure mode can be checked without an LLM. Do
  NOT use for subjective criteria like tone or faithfulness; use
  write-judge-prompt instead.
---

# Write Code-Based Evaluator

Write a Pass/Fail code check for one specific failure mode. If code can check it, don't pay an LLM judge to do it. Code checks cost nothing to run and return the same answer every time.

## Prerequisites

- Error analysis is complete. The failure mode is identified.
- The failure mode is objective: two reviewers reading the output would agree on Pass or Fail without debate. If they would need to debate it, use `write-judge-prompt`.

## Common Checks

| Failure Mode | Check |
|-------------|-------|
| Output is not valid JSON or is missing required fields | `json.loads`, then check keys, types, and non-empty values |
| Leaked template variables (`{{name}}`) or canned refusals | Regex for the forbidden pattern |
| Cites a document, ID, or URL that was not retrieved | Extract citations, confirm each is in the retrieved set |
| Generated SQL or Python does not run | `sqlite3` against an in-memory copy of the schema; `ast.parse` for Python |
| Response too long, or tool call has bad arguments | Length limit; check arguments against the tool's schema |

These are starting points, not a complete list. If code can compute the answer, it's a valid check: a database or API lookup, date or number math, a diff against expected output. Derive each check from the failure mode, not from this table.

Stick to the standard library where possible.

## Output Format

Return the same shape as an LLM judge so both kinds of evaluator plug into the same harness:

```python
import json

REQUIRED = {"name", "email", "reason"}

def check_required_fields(output: str) -> dict:
    try:
        data = json.loads(output)
    except json.JSONDecodeError as e:
        return {"critique": f"Output is not valid JSON: {e}", "result": "Fail"}
    if not isinstance(data, dict):
        return {"critique": "Output is JSON but not an object.", "result": "Fail"}
    missing = REQUIRED - data.keys()
    if missing:
        return {"critique": f"Missing required fields: {sorted(missing)}", "result": "Fail"}
    return {"critique": "Valid JSON with all required fields.", "result": "Pass"}
```

The critique names the exact violation, so a reviewer can see why a trace failed without rerunning the check.

## Code First, Judge Second

Some failure modes have an objective part and a subjective part. Split them. Run the code check first. If it fails, the trace fails and the judge call is skipped. Only traces that pass go to the judge.

Example: a support reply must cite a retrieved help article (code check) and must summarize that article accurately (judge).

## Testing

Write unit tests with known Pass and Fail outputs, including borderline cases pulled from your traces. Code checks are deterministic, so they don't need the data splits and TPR/TNR measurement in `validate-evaluator`.

One exception: a code check that stands in for a judgment call, like the keyword check for "usually" and "normally" in `write-judge-prompt`, can still disagree with human reviewers. Spot-check it against a few human-labeled traces before trusting it.

## Anti-Patterns

- **LLM judge for an objective check.** Asking a judge "is this valid JSON?" costs tokens and adds noise. Parse it.
- **One check for several failure modes.** One check per failure mode, same as judges. A combined check can't tell you what broke.
- **Fail with no critique.** A bare Fail leaves reviewers guessing. Name the violation.
- **Regex fit to a handful of examples.** A pattern written against three bad outputs misses the fourth variant and flags good outputs. Run it across the full trace set, not only the examples that inspired it.
