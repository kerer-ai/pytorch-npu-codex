#!/usr/bin/env python3
"""Generate .github/workflows/nightly-build.yml for pytorch-npu compatibility CI."""

from __future__ import annotations

import argparse
from pathlib import Path


def build_workflow(
    *,
    python_version: str,
    schedule_cron: str,
    runner: str,
    enable_ccache: bool,
    disable_torchair: bool,
    disable_rpc: bool,
) -> str:
    torchair_value = "TRUE" if disable_torchair else "FALSE"
    rpc_line = "          export DISABLE_RPC_FRAMEWORK=TRUE\n" if disable_rpc else ""
    apt_lines = [
        "            cmake ninja-build \\",
        "            gcc g++ \\",
        "            git \\",
        "            patchelf",
    ]

    ccache_install = ""
    ccache_restore = ""
    ccache_prep = ""
    ccache_hit_output = "          echo \"hit_rate=N/A\" >> $GITHUB_OUTPUT\n"
    ccache_save = ""
    summary_ccache_rows = ""

    if enable_ccache:
        apt_lines[-1] = "            patchelf \\"
        ccache_install = "            ccache\n"
        ccache_restore = """\
      - name: Restore ccache
        id: ccache-restore
        uses: actions/cache/restore@v4
        with:
          path: ~/.ccache
          key: ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ github.ref_name }}-${{ github.run_id }}
          restore-keys: |
            ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ github.ref_name }}-
            ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-

"""
        ccache_prep = """\
          mkdir -p ~/.ccache
          ccache -M 2G
          ccache -z || true
          export CC="ccache gcc"
          export CXX="ccache g++"
          export CCACHE_BASEDIR="${PWD}"
          export CCACHE_DIR="${HOME}/.ccache"
          export CCACHE_COMPRESS=1
          export CCACHE_MAXSIZE=2G

"""
        ccache_hit_output = """\
          CCACHE_HIT_RATE=$(ccache -s | awk -F'[()]' '/Hits:/ {print $2; exit}')
          [ -n "${CCACHE_HIT_RATE}" ] || CCACHE_HIT_RATE="N/A"
          echo "hit_rate=${CCACHE_HIT_RATE}" >> $GITHUB_OUTPUT
          ccache -s || true
"""
        ccache_save = """\
      - name: Save ccache
        if: always()
        uses: actions/cache/save@v4
        with:
          path: ~/.ccache
          key: ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ github.ref_name }}-${{ github.run_id }}

"""
        summary_ccache_rows = """\
          | ccache 命中 | ${{ steps.ccache-restore.outputs.cache-hit == 'true' && '命中' || '未命中' }} |
          | ccache 命中率 | ${{ steps.build.outputs.hit_rate || 'N/A' }} |
"""

    apt_block = "\n".join(apt_lines)

    return f"""name: Ascend/pytorch Nightly Build Validation

on:
  schedule:
    - cron: '{schedule_cron}'
  workflow_dispatch:
    inputs:
      torch_nightly_date:
        description: 'PyTorch nightly 日期 (格式: YYYYMMDD，留空使用最新版)'
        required: false
        default: ''

env:
  PYTHON_VERSION: '{python_version}'

jobs:
  build:
    name: Build torch_npu (x86, PyTorch nightly)
    runs-on: {runner}

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Set up Python ${{{{ env.PYTHON_VERSION }}}}
        uses: actions/setup-python@v5
        with:
          python-version: ${{{{ env.PYTHON_VERSION }}}}

      - name: Install system dependencies
        run: |
          sudo apt-get update -qq
          sudo apt-get install -y --no-install-recommends \\
{apt_block}
{ccache_install.rstrip()}

{ccache_restore}      - name: Install PyTorch nightly (CPU, x86_64)
        id: install_torch
        run: |
          pip install --upgrade pip
          if [ -n "${{{{ github.event.inputs.torch_nightly_date }}}}" ]; then
            DATE="${{{{ github.event.inputs.torch_nightly_date }}}}"
            pip install --pre \\
              "torch==2.11.0.dev${{DATE}}" \\
              --index-url https://download.pytorch.org/whl/nightly/cpu
          else
            pip install --pre torch \\
              --index-url https://download.pytorch.org/whl/nightly/cpu
          fi
          TORCH_VER=$(python -c "import torch; print(torch.__version__)")
          echo "version=${{TORCH_VER}}" >> $GITHUB_OUTPUT
          echo "PyTorch nightly version: ${{TORCH_VER}}"

      - name: Clone Ascend/pytorch (with submodules)
        id: clone_repo
        run: |
          git clone --depth=1 --recurse-submodules \\
            https://github.com/Ascend/pytorch.git ascend_pytorch
          cd ascend_pytorch
          COMMIT=$(git rev-parse HEAD)
          COMMIT_SHORT=$(git rev-parse --short HEAD)
          COMMIT_DATE=$(git log -1 --format='%ci')
          echo "commit=${{COMMIT}}" >> $GITHUB_OUTPUT
          echo "commit_short=${{COMMIT_SHORT}}" >> $GITHUB_OUTPUT
          echo "commit_date=${{COMMIT_DATE}}" >> $GITHUB_OUTPUT
          echo "Ascend/pytorch commit: ${{COMMIT}} (${{COMMIT_DATE}})"

      - name: Install Python build dependencies
        run: |
          cd ascend_pytorch
          pip install pyyaml setuptools auditwheel

      - name: Apply compatibility patches
        id: patch
        run: |
          PATCH_DIR="${{GITHUB_WORKSPACE}}/patches"
          PATCH_APPLIED=""
          PATCH_FAILED=""
          for p in "${{PATCH_DIR}}"/*.patch; do
            [ -f "$p" ] || continue
            echo "Applying patch: $(basename $p)"
            if git apply --directory=ascend_pytorch "$p"; then
              echo "  ✅ OK"
              PATCH_APPLIED="${{PATCH_APPLIED}} $(basename $p)"
            else
              echo "  ❌ FAILED (may already be merged upstream)"
              PATCH_FAILED="${{PATCH_FAILED}} $(basename $p)"
            fi
          done
          echo "applied=${{PATCH_APPLIED}}" >> $GITHUB_OUTPUT
          echo "failed=${{PATCH_FAILED}}" >> $GITHUB_OUTPUT

      - name: Build torch_npu wheel
        id: build
        run: |
          cd ascend_pytorch
{ccache_prep}          export DISABLE_INSTALL_TORCHAIR={torchair_value}
{rpc_line}          export BUILD_WITHOUT_SHA=1
          python setup.py build bdist_wheel 2>&1 | tee /tmp/build.log
          BUILD_STATUS=${{PIPESTATUS[0]}}
{ccache_hit_output}          echo "status=${{BUILD_STATUS}}" >> $GITHUB_OUTPUT
          if [ ${{BUILD_STATUS}} -eq 0 ]; then
            WHL=$(ls dist/*.whl 2>/dev/null | head -1)
            echo "wheel=${{WHL}}" >> $GITHUB_OUTPUT
            echo "Build succeeded: ${{WHL}}"
          fi
          exit ${{BUILD_STATUS}}

{ccache_save}      - name: Upload build log
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: build-log-${{{{ github.run_number }}}}
          path: /tmp/build.log
          if-no-files-found: warn

      - name: Upload wheel
        if: steps.build.outputs.status == '0'
        uses: actions/upload-artifact@v4
        with:
          name: torch_npu-wheel-${{{{ github.run_number }}}}
          path: ascend_pytorch/dist/*.whl
          if-no-files-found: warn

      - name: Build summary
        if: always()
        run: |
          if [ "${{{{ steps.build.outcome }}}}" = "success" ]; then
            STATUS_ICON="✅ SUCCESS"
          else
            STATUS_ICON="❌ FAILED"
          fi

          cat >> $GITHUB_STEP_SUMMARY << EOF
          ## Ascend/pytorch Nightly Build Validation

          | 项目 | 详情 |
          |------|------|
          | 构建时间 | $(date -u '+%Y-%m-%d %H:%M UTC') |
          | PyTorch Nightly | `${{{{ steps.install_torch.outputs.version }}}}` |
          | Ascend/pytorch Commit | [`${{{{ steps.clone_repo.outputs.commit_short }}}}`](https://github.com/Ascend/pytorch/commit/${{{{ steps.clone_repo.outputs.commit }}}}) |
          | Commit 时间 | ${{{{ steps.clone_repo.outputs.commit_date }}}} |
          | 已应用 Patch | ${{{{ steps.patch.outputs.applied || '(无)' }}}} |
{summary_ccache_rows.rstrip()}
          | 构建结果 | ${{STATUS_ICON}} |

          $( [ "${{{{ steps.build.outcome }}}}" = "success" ] && echo "> Wheel: `${{{{ steps.build.outputs.wheel }}}}`" || echo "> 查看 build-log artifact 获取详细错误信息" )
          EOF
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=".github/workflows/nightly-build.yml")
    parser.add_argument("--python-version", default="3.11")
    parser.add_argument("--schedule-cron", default="0 2 * * *")
    parser.add_argument("--runner", default="ubuntu-22.04")
    parser.add_argument("--enable-ccache", dest="enable_ccache", action="store_true", default=True)
    parser.add_argument("--no-enable-ccache", dest="enable_ccache", action="store_false")
    parser.add_argument("--disable-torchair", action="store_true")
    parser.add_argument("--disable-rpc", action="store_true")
    parser.add_argument("--print-only", action="store_true")
    args = parser.parse_args()

    content = build_workflow(
        python_version=args.python_version,
        schedule_cron=args.schedule_cron,
        runner=args.runner,
        enable_ccache=args.enable_ccache,
        disable_torchair=args.disable_torchair,
        disable_rpc=args.disable_rpc,
    )

    if args.print_only:
        print(content)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    print(f"[OK] Wrote workflow: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
