# Nightly Build Policy

## Defaults

- Workflow filename: `.github/workflows/nightly-build.yml`
- Schedule: `0 2 * * *` (UTC)
- Runner: `ubuntu-22.04`
- Python: `3.11`
- PyTorch source: nightly CPU index (`download.pytorch.org/whl/nightly/cpu`)
- Ascend repo clone: `https://github.com/Ascend/pytorch.git` with submodules
- Patch apply strategy: iterate `patches/*.patch` and apply into `ascend_pytorch`
- Build command: `python setup.py build bdist_wheel`
- Default build flags:
  - `DISABLE_INSTALL_TORCHAIR=FALSE`
  - do not force `DISABLE_RPC_FRAMEWORK=TRUE`
  - `BUILD_WITHOUT_SHA=1`

## ccache

- Install `ccache` in system deps.
- Restore cache before build.
- Use:
  - `CC="ccache gcc"`
  - `CXX="ccache g++"`
  - `CCACHE_DIR=~/.ccache`
  - `CCACHE_MAXSIZE=2G`
- Save cache after build (even on failure).
- Surface cache hit information in summary.

## Summary Status

- Prefer workflow step outcome for success/failure display:
  - success when `steps.build.outcome == 'success'`
  - failed otherwise
- Do not infer status from custom outputs that may be missing on early failures.

## Frequent Failure Modes

1. Build code/API incompatibility:
- Signals: `error:`, `make[2]`, `override` mismatch, missing fields.
- Action: patch Ascend/pytorch compatibility code.

2. Workflow/script failure:
- Signals: `Unable to process file command 'output'`, `Invalid format`, `GITHUB_OUTPUT`.
- Action: fix workflow script/output formatting, not compatibility patch.

## GITHUB_OUTPUT Safety

- Safe (single line):
  - `echo "hit_rate=99.76 %" >> $GITHUB_OUTPUT`
- Unsafe (raw multi-line variable):
  - `echo "stats=${MULTILINE}" >> $GITHUB_OUTPUT`
- If multi-line is required, use heredoc format:
  - `echo "name<<EOF" >> $GITHUB_OUTPUT`
  - `echo "$VALUE" >> $GITHUB_OUTPUT`
  - `echo "EOF" >> $GITHUB_OUTPUT`
