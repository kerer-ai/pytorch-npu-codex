---
name: nightly-build-workflow-generator
description: Generate or update `.github/workflows/nightly-build.yml` for pytorch-npu compatibility CI. Use when users ask to create, regenerate, or standardize nightly build GitHub Actions workflow files with PyTorch nightly install, Ascend/pytorch clone, patch apply, wheel build, artifact upload, and optional ccache acceleration settings.
---

# Nightly Build Workflow Generator

Generate a runnable `nightly-build.yml` from repository policy with deterministic structure and safe GitHub Actions output handling.

## Workflow

1. Read policy defaults from `references/nightly-build-policy.md`.
2. Generate workflow using `scripts/generate_nightly_build.py`.
3. Write to `.github/workflows/nightly-build.yml` (or print for preview).
4. Validate YAML structure with quick checks (`gh workflow view` or CI dry run in PR).
5. If CI fails, classify failure type first:
   - Compatibility/code failure (`error:`, `make[2]`) -> patch flow.
   - Workflow/script failure (`GITHUB_OUTPUT`, `Invalid format`) -> fix workflow generator logic.

## Commands

Generate and write workflow file:

```bash
python3 /root/.codex/skills/nightly-build-workflow-generator/scripts/generate_nightly_build.py \
  --output .github/workflows/nightly-build.yml
```

Preview without writing:

```bash
python3 /root/.codex/skills/nightly-build-workflow-generator/scripts/generate_nightly_build.py \
  --print-only
```

Disable ccache (when explicitly requested):

```bash
python3 /root/.codex/skills/nightly-build-workflow-generator/scripts/generate_nightly_build.py \
  --no-enable-ccache \
  --output .github/workflows/nightly-build.yml
```

Disable torchair or force-disable RPC (only when user explicitly requires):

```bash
python3 /root/.codex/skills/nightly-build-workflow-generator/scripts/generate_nightly_build.py \
  --disable-torchair \
  --disable-rpc \
  --output .github/workflows/nightly-build.yml
```

## Guardrails

- Keep all `$GITHUB_OUTPUT` writes single-line unless using heredoc format.
- Prefer step outcome (`steps.build.outcome`) for summary status to avoid false failure labels.
- Preserve patch application flow (`patches/*.patch` + `git apply --directory=ascend_pytorch`).
- Default to enabling torchair and keeping RPC in default behavior unless user says otherwise.
- Keep ccache enabled by default for repeat-run acceleration.

## Resources

- `scripts/generate_nightly_build.py`: Workflow generator.
- `references/nightly-build-policy.md`: Default policy and troubleshooting notes.
