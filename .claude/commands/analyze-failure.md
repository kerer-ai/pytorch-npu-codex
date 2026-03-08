分析最新一次失败的 GitHub Actions CI 构建，输出结构化的根本原因报告。

## 执行步骤

### 第一步：找到最近的失败 Run

```bash
gh run list --repo kerer-ai/pytorch-npu --limit 5
```

记录最新一条 `failure` 状态的 Run ID 和触发时间。同时观察**构建进度**（运行时长）：
- 时长很短（< 5 分钟）→ 失败在早期步骤（patch apply、依赖安装等）
- 时长较长（> 30 分钟）→ 编译阶段失败，说明前序 patch 均已生效

### 第二步：拉取失败日志并过滤关键行

```bash
gh run view <run_id> --repo kerer-ai/pytorch-npu --log-failed 2>&1 \
  | grep -E "error:|Error|FAILED|fatal|Traceback|make\[|Applying patch|✅|❌" \
  | head -100
```

同时检查是否属于 **CI 脚本失败**（非编译错误）：

```bash
gh run view <run_id> --repo kerer-ai/pytorch-npu --log-failed 2>&1 \
  | grep -E "Unable to process file command|Invalid format|GITHUB_OUTPUT|set-output" \
  | head -50
```

重点关注：
- `make[2]: *** [...] Error 1` → 定位到具体编译失败的 `.cpp` 文件
- `error: 'struct X' has no member named 'Y'` → 结构体成员被上游删除或重命名
- `error: 'Z' marked 'override', but does not override` → 虚函数签名变更
- `error: invalid new-expression of abstract class type` → 基类新增纯虚函数未实现
- `✅ OK` / `❌ FAILED` → 哪些 patch 成功打入，哪些失败（可能已被上游合入）
- `Unable to process file command 'output'` / `Invalid format` → workflow 输出格式问题，优先修 `.github/workflows/*.yml`

### 第三步：定位受影响源文件，对比新旧 API

确认失败的 `.cpp` / `.hpp` 文件后，读取对应源码：

```bash
# 读取 Ascend/pytorch 源文件（使用本地克隆）
cat /root/ascend_pytorch_tmp/<受影响文件路径>
```

然后在 PyTorch nightly 安装的头文件中查找对应的新 API：

```bash
TORCH_INCLUDE=$(python3 -c "import torch,os; print(os.path.dirname(torch.__file__))")/include
# 按关键词搜索相关头文件
grep -rn "<变更的类名或函数名>" $TORCH_INCLUDE --include="*.h" | head -20
# 读取具体头文件
cat $TORCH_INCLUDE/<相关头文件路径>
```

### 第四步：输出结构化报告

```
## 失败 Run 信息
- Run ID：
- 触发时间：
- 构建进度：（已通过 patch 数量 / 失败所在阶段）

## 已生效的 Patch
（列出 ✅ OK 的 patch，说明本次构建在哪些修复的基础上推进）

## 错误摘要
（3-5 条最关键的编译错误原文）

## 根本原因
（说明是哪个 PyTorch 上游 API 变化导致失败：结构体字段删除 / 函数签名变更 / 新增纯虚函数 等）

## 受影响范围
- 文件：（相对于 Ascend/pytorch 根目录的路径）
- 涉及类/函数：

## 建议修复方向
（最小改动原则：如何调整 Ascend 侧代码适配新 API）
```

## 注意事项

- 若日志量大（> 40KB），`grep` 过滤后重点看 `make[2]` 和第一个 `error:` 出现的位置
- 若日志显示 wheel 已成功生成，但 step 仍失败，优先判断为 CI 脚本问题，而不是 patch 兼容问题
- 每次构建失败通常只暴露**当前最早的**编译错误，修完一个后下次构建才会暴露下一个
- 本地克隆路径：`/root/ascend_pytorch_tmp`（已有则复用，否则 `git clone --depth=1 https://github.com/Ascend/pytorch.git /root/ascend_pytorch_tmp`）
- PyTorch nightly 头文件路径：`/usr/local/lib/python3.12/dist-packages/torch/include/`
