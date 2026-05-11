# Security Notes

## Trust Model

This MVP is intended for local or self-hosted use against trusted repositories.

Assumptions:

- the operator trusts the target repository content
- the operator trusts the Docker daemon on the local machine
- the operator understands that model prompts may include repository code snippets

## Sandbox Limits

Validation runs occur in Docker containers without privileged mode, but this is not a perfect security boundary.

Current sandbox behavior:

- mounts the target repository read-write
- executes user-selected validation commands
- applies timeouts
- captures stdout/stderr

This protects the host less than a full VM or hardened remote executor would.

## Secret Handling

The system avoids intentionally injecting environment secrets into prompts, but secret redaction is only best-effort in this MVP.

Recommended practices:

- run against repos without embedded secrets
- avoid dumping full `.env` or secret config files into agent context
- use separate low-privilege credentials for local testing

## Git Safety

The platform does not auto-commit by default. Commit creation is explicit and can be skipped with `dry_run`.

Operators should still:

- start from a clean branch when possible
- inspect diffs before committing
- review model-authored changes manually on important code paths

## Model Provider

OpenRouter is used as a transport layer for model access. Configure it with:

- `OPENROUTER_API_KEY`
- optional `OPENROUTER_BASE_URL`
- optional `APP_URL` and `APP_NAME` headers

Do not point the system at repositories whose code cannot be sent to the configured model provider.
