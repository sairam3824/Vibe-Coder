# Prompting Strategy

Prompt templates live under `packages/agent/prompts/templates`.

## Implemented Prompt Families

- `planning_*`
  Produces a structured plan with goal summary, assumptions, files, validation strategy, and rollback risks.
- `file_selection_*`
  Refines heuristic file targeting on larger repos using model judgment.
- `editing_*`
  Produces JSON file rewrites for the initial implementation pass.
- `failure_diagnosis_*`
  Summarizes validation failures and likely files to revisit.
- `repair_*`
  Produces corrective edits after a failed validation attempt.
- `commit_message_*`
  Generates a conventional commit summary from the task and applied changes.

## Prompt Design Principles

- Always request JSON for machine-consumable steps.
- Avoid dumping whole repositories; only send selected manifests, files, symbols, and recent failures.
- Include the current plan and prior edits during repair iterations.
- Keep prompts provider-agnostic through the `ModelProvider` abstraction.
- Fall back safely when the provider is unavailable or returns invalid JSON.

## Context Selection

The agent builds prompt context from:

- detected manifests
- relevant files from path and symbol heuristics
- truncated file content snippets
- validation failure signatures
- persisted plan and changed-file history

This keeps prompt payloads bounded while still including nearby code and tests.

## Expected Model Output Shape

Editing and repair steps return:

```json
{
  "summary": "short explanation",
  "changes": [
    {
      "path": "relative/path.ext",
      "change_type": "create|update",
      "summary": "why this file changed",
      "content": "full new file content"
    }
  ]
}
```

## Future Improvements

- AST-aware edit operations instead of full file rewrites
- prompt budget tracking per node
- richer few-shot examples by language/framework
- validation-aware chunk ranking based on failing stack traces
