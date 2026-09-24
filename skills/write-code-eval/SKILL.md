---
name: write-code-eval
description: >
  Write code checks for objective eval failures, such as invalid schemas,
  missing citations, or broken tool calls. Use when code can check a known
  failure mode. For criteria that require interpretation, use
  write-judge-prompt.
---

# Write a code evaluator

Write a Pass/Fail check for one known failure mode. Use code when the rule is precise enough to test. State what the check needs from each trace and what counts as a failure.

## Before you start

- Error analysis is complete. The failure mode is identified.
- The failure mode has a rule you can check with code. Use `write-judge-prompt` when the rule requires interpretation.

## Common checks

| Failure Mode | Check |
|-------------|-------|
| Output is not valid JSON or is missing required fields | `json.loads`, then check keys, types, and non-empty values |
| Leaked template variables (`{{name}}`) or canned refusals | Regex for the forbidden pattern |
| Cites a document, ID, or URL that was not retrieved | Extract citations, confirm each is in the retrieved set |
| Generated SQL does not run, or Python has invalid syntax | Execute SQL against a safe test database; use `ast.parse` to check Python syntax |
| Response too long, or tool call has bad arguments | Length limit; check arguments against the tool's schema |

Derive the check from the failure mode. A lookup, calculation, or comparison with expected output may also work.

## Output format

Return the format your eval harness expects. If it uses the same format as `write-judge-prompt`, return `critique` and `result`:

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

## Combining code and a judge

When a failure mode has both kinds of criteria, check the objective part first. Call the judge only for traces that pass that check.

Example: a support reply must cite a retrieved help article (code check) and must summarize that article accurately (judge).

## Test the check

Test known Pass and Fail traces, including borderline cases. Run the check across the available traces and inspect unexpected results.

If the check uses a proxy for a judgment call, compare its results with human labels. A keyword check for "usually" or "normally" may miss other ways to express the same idea.

Keep each check tied to one failure mode and return the exact reason for a Fail. Test regex patterns on the available traces, including good outputs that look similar to failures.
