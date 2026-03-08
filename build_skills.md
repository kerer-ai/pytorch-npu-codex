# build_skills.md

目标：仅根据本文件，自动生成可运行的 `.github/workflows/nightly-build.yml`，用于验证 `Ascend/pytorch` 对 PyTorch nightly 的编译兼容性。

## 1. 输出文件与触发

- 输出文件路径：`.github/workflows/nightly-build.yml`
- workflow 名称：`Ascend/pytorch Nightly Build Validation`
- 触发方式：
  - 定时：`cron: '0 2 * * *'`
  - 手动：`workflow_dispatch`
    - 输入参数：`torch_nightly_date`（可选，格式 `YYYYMMDD`）
- 全局环境变量：`PYTHON_VERSION: '3.11'`

## 2. Job 基础信息

- 单一 job：`build`
- job 名称：`Build torch_npu (x86, PyTorch nightly)`
- runner：`ubuntu-22.04`

## 3. 必须包含的步骤（顺序固定）

1. `actions/checkout@v4`
2. `actions/setup-python@v5`，版本取 `env.PYTHON_VERSION`
3. 安装系统依赖：`cmake ninja-build gcc g++ git patchelf ccache`
4. 恢复 ccache：`actions/cache/restore@v4`
5. 安装 PyTorch nightly（CPU）
6. 克隆 `Ascend/pytorch`（`--depth=1 --recurse-submodules`）
7. 安装 Python 构建依赖：`pyyaml setuptools auditwheel`
8. 应用 `patches/*.patch`（如果有）
9. 构建 wheel：`python setup.py build bdist_wheel`
10. 保存 ccache：`actions/cache/save@v4`
11. 上传构建日志 artifact
12. 成功时上传 wheel artifact
13. 输出 step summary

## 4. Patch 处理规则（关键）

- patch 目录：`${GITHUB_WORKSPACE}/patches`
- 遍历方式：`for p in "${PATCH_DIR}"/*.patch; do ...`
- 行为要求：
  - 若存在 patch 文件：逐个执行 `git apply --directory=ascend_pytorch "$p"`
  - `apply` 成功：记录到 `PATCH_APPLIED`
  - `apply` 失败：记录到 `PATCH_FAILED`（通常表示上游已合入或上下文变化）
- 若没有 patch 文件：正常跳过，不报错
- 必须向 `$GITHUB_OUTPUT` 写出：
  - `applied=...`
  - `failed=...`

## 5. 构建策略

- 默认启用 torchair：`export DISABLE_INSTALL_TORCHAIR=FALSE`
- 不强制禁用 RPC：不要设置 `DISABLE_RPC_FRAMEWORK=TRUE`
- 保留：`export BUILD_WITHOUT_SHA=1`
- 构建日志：`python setup.py build bdist_wheel 2>&1 | tee /tmp/build.log`
- 构建状态：
  - `BUILD_STATUS=${PIPESTATUS[0]}`
  - 写入输出：`status=${BUILD_STATUS}`
  - 成功时写入：`wheel=<dist/*.whl>`

## 6. ccache 规则

- 构建前：
  - `ccache -M 2G`
  - `ccache -z || true`
  - `CC="ccache gcc"`
  - `CXX="ccache g++"`
  - `CCACHE_DIR="${HOME}/.ccache"`
  - `CCACHE_MAXSIZE=2G`
- 构建后：
  - 输出 `ccache -s`
  - 解析命中率为单行字符串（如 `99.76 %`）写入 `$GITHUB_OUTPUT`：`hit_rate=...`
- 缓存 key：
  - `ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ github.ref_name }}-${{ github.run_id }}`
- `restore-keys`：
  - `ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-${{ github.ref_name }}-`
  - `ccache-${{ runner.os }}-py${{ env.PYTHON_VERSION }}-`

## 7. Summary 规则

- summary 必须包含：
  - PyTorch nightly 版本
  - Ascend/pytorch commit（短 hash + commit URL + 时间）
  - 已应用 patch 列表
  - ccache 是否命中
  - ccache 命中率
  - 构建结果（成功/失败）
  - 成功时显示 wheel 路径；失败时提示查看 build-log artifact

## 8. 关键防坑（必须遵守）

1. 不要把多行文本直接写入 `$GITHUB_OUTPUT`
- 错误示例：`echo "stats=${MULTILINE}" >> $GITHUB_OUTPUT`
- 正确做法：只写单行键值（或用 heredoc 多行格式）

2. patch 步骤要容忍“无 patch”场景
- 使用 `[ -f "$p" ] || continue`

3. 日志 artifact 必须 `if: always()`
- 保证失败时也能下载日志

4. wheel 上传必须仅在成功时执行
- `if: steps.build.outputs.status == '0'`

## 9. 最小验收标准

- workflow 可被 GitHub Actions 识别并手动触发
- 无 patch 时可直接编译最新版本
- 有 patch 时会自动应用后再编译
- 构建失败时可下载 `/tmp/build.log`
- 构建成功时可下载 `dist/*.whl`

## 10. 推荐生成提示词（给其他模型）

“请严格按 `build_skills.md` 生成 `.github/workflows/nightly-build.yml`。  
要求：按文档顺序组织 step，保留 patch 自动应用逻辑（有 patch 则 apply，无 patch 则跳过），默认 `DISABLE_INSTALL_TORCHAIR=FALSE` 且不强制禁用 RPC，启用 ccache restore/save，并保证 `$GITHUB_OUTPUT` 仅写合法单行键值。生成后输出完整 YAML。”
