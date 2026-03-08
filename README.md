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
3. 按序应用 `patches/` 目录下所有兼容性 patch
4. 编译 CANN 桩库（`build_stub.sh`，仅需 GCC）
5. 执行 `python setup.py build bdist_wheel`
6. 上传构建日志和生成的 wheel 包

## 当前 CI 策略（2026-03-08 更新）

- 默认启用 torchair：`DISABLE_INSTALL_TORCHAIR=FALSE`
- 不再强制禁用 RPC：不设置 `DISABLE_RPC_FRAMEWORK=TRUE`
- 启用 `ccache`：构建前 `restore`，构建后 `save`
- Step Summary 额外输出 `ccache` 命中状态与命中率

## 查看结果

- [Actions 页面](../../actions/workflows/nightly-build.yml) 查看每次构建状态
- 每次运行的 Step Summary 包含 PyTorch 版本、Ascend/pytorch commit、已应用 patch 列表和构建结果
- 构建失败时可下载 `build-log` artifact 查看详细编译错误

### 结果判读要点

- `Build torch_npu wheel` 成功且出现 `Build succeeded: dist/*.whl`，说明核心编译成功。
- 如果同一 step 最后报 `Unable to process file command 'output'` / `Invalid format`，通常是 workflow 输出写法错误（`$GITHUB_OUTPUT` 格式）而非编译错误。
- `ccache` 首次冷启动命中率低属正常；第二次开始命中率应显著提升（本仓库实测从 `0.16%` 提升到 `99.76%`）。

## 手动触发

在 Actions 页面点击 **Run workflow**，可选填 PyTorch nightly 日期（格式 `YYYYMMDD`），留空使用最新版。

## Workflow 生成规范（给任意模型）

本仓库提供单文件规范 [`build_skills.md`](build_skills.md)。

用途：
- 让任意模型只根据该文件生成 `.github/workflows/nightly-build.yml`
- 明确“有 patch 则自动 apply、无 patch 则直接编译最新版”的行为
- 固化 ccache、artifact、summary、`$GITHUB_OUTPUT` 安全写法等关键细节

推荐做法：
1. 将 `build_skills.md` 作为唯一约束输入给模型
2. 让模型输出完整 `nightly-build.yml`
3. 提交后手动触发一次 workflow 验证

---

## 问题处理（Claude Code Skills）

本仓库内置三个 Claude Code slash commands，覆盖从检测到修复的完整闭环。在项目目录下启动 Claude Code 后即可使用。

### 典型工作流

```
CI 构建失败
  │
  ├─ /analyze-failure   ← 拉取日志、定位根因、对比 PyTorch 新旧 API
  │
  ├─ /report-issue      ← 按日期编号创建 issues/ 文档
  │
  └─ /gen-patch         ← 修改源码、生成 patch、提交、触发验证
                               │
                        下次构建推进更远？
                          ├─ 是 → 继续 /analyze-failure 处理下一个问题
                          └─ 否 → 检查 patch 是否正确应用
```

---

### `/analyze-failure` — 分析 CI 失败原因

CI 变红后的第一步。执行内容：

1. `gh run list` 找到最新失败 Run
2. `gh run view --log-failed` 拉取失败日志
3. 过滤 `error:`、`make[2]`、`Traceback` 等关键行
4. 读取受影响的 Ascend/pytorch 源文件
5. 在 PyTorch nightly 头文件（`/usr/local/lib/python3.12/dist-packages/torch/include/`）中查找变更后的 API 定义
6. 输出结构化报告：已生效 patch、错误摘要、根本原因、受影响范围、建议修复方向

```
/analyze-failure
```

**关键观察**：构建运行时长比上次更长 → 前序 patch 已生效，本次暴露新问题。

**新增观察（重要）**：先区分“真实编译失败”与“CI 脚本失败”：
- 编译失败：`error:` / `make[2]: ***` / `FAILED` 等 C/C++ 错误
- 脚本失败：`Unable to process file command 'output'`、`Invalid format`、`set-output`/`GITHUB_OUTPUT` 相关报错

---

### `/report-issue` — 创建 issue 记录

在 `/analyze-failure` 完成后使用。按 `YYYY-MM-DD-NNN` 规则编号，在 `issues/` 下创建 Markdown 文档，记录：问题描述、根本原因分析（含错误日志）、修复方案、对应 patch 文件名、前置 patch（如有）。

```
/report-issue
```

示例：`issues/2026-03-07-001-CachingHostAllocator-HostBlockPool-api-break.md`

---

### `/gen-patch` — 生成 patch 并触发验证

执行内容：

1. 确认本地克隆（`/root/ascend_pytorch_tmp`）可用
2. 对比新旧 API，按最小改动原则修改受影响源文件
3. `git diff <文件> > patches/NNNN-fix-<模块>-<描述>.patch` 生成 patch
4. 提交 patch + issue 文档并 push
5. `gh workflow run` 触发新一轮构建
6. 观察构建进度判断 patch 是否生效

```
/gen-patch
```

示例：`patches/0002-fix-NPUSHMEMSymmetricMemory-GroupInfo-api-compat.patch`

**常见修复模式：**

| 错误类型 | 修复方式 |
|----------|----------|
| 结构体成员被删除（原用于缓存） | `.cpp` 模块级引入 `static map + mutex` 替代 |
| 成员重命名（如 `blocks` → `blocks_`） | 重命名 Ascend 侧冲突的同名类型，消除 typedef 遮蔽 |
| 基类新增纯虚函数 | 子类 `.hpp` 中补充 override（无对应语义则返回 0） |
| 虚函数签名新增参数 | 更新 override 签名，原逻辑提取为私有方法 |

---

### Patch 生命周期

```
新增 patch → CI 自动应用（git apply --directory=ascend_pytorch）
                │
     apply 成功 ✅ → 构建推进，问题修复
     apply 失败 ❌ → 上游已合入该修复 → 删除 patch 文件并提交
```

> Patch 打在 CI 临时克隆的副本上，**不修改 Ascend/pytorch 官方仓库**。

---

## ccache 经验沉淀

- 在本仓库场景下，`ccache` 对重复构建有效，建议保留。
- 推荐至少保留以下环境变量：
  - `CC="ccache gcc"`
  - `CXX="ccache g++"`
  - `CCACHE_DIR=~/.ccache`
  - `CCACHE_MAXSIZE=2G`
- 不要把多行文本直接写入 `$GITHUB_OUTPUT`（会触发格式错误并导致 step 失败）。
  - 建议输出单行指标（如 `hit_rate=99.76 %`）。
