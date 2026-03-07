# pytorch-npu CI

每日自动验证 [Ascend/pytorch](https://github.com/Ascend/pytorch) 在 PyTorch 主干最新 nightly 版本下的编译兼容性。

## 工作原理

- **触发方式**：每天 UTC 02:00（北京时间 10:00）自动触发，或手动触发
- **运行环境**：GitHub Actions 免费 x86 runner（`ubuntu-22.04`）
- **PyTorch 版本**：PyTorch 主干每日 nightly 构建（CPU 版）
- **CANN 依赖**：无需安装 CANN，使用仓库内置的桩库（`third_party/acl/libs/build_stub.sh`）

## 构建流程

1. 安装 PyTorch nightly（从 `download.pytorch.org/whl/nightly/cpu`）
2. 克隆 `Ascend/pytorch`（含 `op-plugin` 子模块）
3. 编译 CANN 桩库（`build_stub.sh`，仅需 GCC）
4. 执行 `python setup.py build bdist_wheel`
5. 上传构建日志和生成的 wheel 包

## 查看结果

- [Actions 页面](../../actions/workflows/nightly-build.yml) 查看每次构建状态
- 每次运行的 Step Summary 包含版本对照表
- 构建失败时可下载 `build-log` artifact 查看详细错误

## 手动触发

在 Actions 页面点击 **Run workflow**，可选填 PyTorch nightly 日期（格式 `YYYYMMDD`），留空使用最新版。

## 问题处理（Claude Code Skills）

本仓库内置了三个 Claude Code slash commands，覆盖从检测到修复的完整流程。在项目目录下启动 Claude Code 后即可使用。

### `/analyze-failure` — 分析 CI 失败原因

CI 构建变红后使用。自动拉取最新失败 run 的日志，过滤关键错误行，输出结构化的根本原因报告，包括受影响文件、API 变化详情和建议修复方向。

```
/analyze-failure
```

### `/report-issue` — 生成 issue 记录

在 `/analyze-failure` 完成后使用。按日期和序号（`YYYY-MM-DD-NNN`）在 `issues/` 目录下创建标准格式的 issue 文档，记录问题现象、根本原因和修复方案。

```
/report-issue
```

生成文件示例：`issues/2026-03-07-001-CachingHostAllocator-HostBlockPool-api-break.md`

### `/gen-patch` — 生成 patch 并接入 CI

有明确修复思路后使用。指导完成以下操作：
1. 对比 PyTorch nightly 头文件与 Ascend/pytorch 源码，确认 API 差异
2. 在本地克隆上修改源码（最小改动原则）
3. 生成标准 `git diff` 格式的 patch 文件到 `patches/` 目录
4. 验证 patch 在干净克隆上可正常应用
5. 确认 CI workflow 已配置自动打 patch
6. 提交并触发新一轮构建验证

```
/gen-patch
```

生成文件示例：`patches/0001-fix-CachingHostAllocator-HostBlockPool-api-compat.patch`

---

### 典型工作流

```
CI 失败
  └─ /analyze-failure    # 定位根因
       └─ /report-issue  # 记录问题
            └─ /gen-patch # 修复并验证
```

> **说明**：patch 打在 CI 临时克隆的 Ascend/pytorch 副本上，不修改官方仓库。
> 当上游合入修复后，`git apply` 会自动失败并跳过，此时可将对应 patch 文件删除。
