针对已分析的兼容性问题，在本地 Ascend/pytorch 克隆上修改源码，生成 patch 文件，提交后触发 CI 验证。

## 前置条件

- 已通过 `/analyze-failure` 明确了受影响文件和 API 变化
- 已通过 `/report-issue` 创建了对应的 issue 文档

## 执行步骤

### 第一步：确认本地克隆可用

```bash
ls /root/ascend_pytorch_tmp/  # 检查是否已克隆
```

若不存在，重新克隆：
```bash
git clone --depth=1 https://github.com/Ascend/pytorch.git /root/ascend_pytorch_tmp
```

> **注意**：本地克隆可能已包含前序 patch 的修改（通过 Edit 工具直接编辑），这是正常的。
> `git diff` 会将所有未提交的改动都打入 patch，确认 diff 范围只涵盖本次要修复的文件。

### 第二步：理解新旧 API 差异

在 PyTorch nightly 头文件中找到变更后的接口定义：

```bash
TORCH_INCLUDE=/usr/local/lib/python3.12/dist-packages/torch/include
# 搜索相关类/结构体
grep -rn "<类名>" $TORCH_INCLUDE --include="*.h" | grep -v "\.pyc"
# 读取具体头文件
cat $TORCH_INCLUDE/<路径>/<文件>.h
```

对比 Ascend/pytorch 源码，明确：
- 删除了哪些字段/方法 → 需要移除引用或用替代方案
- 新增了哪些纯虚函数 → 必须在子类中实现
- 签名变化了的虚函数 → 更新 override 声明

### 第三步：修改源码（最小改动原则）

直接使用 Edit 工具修改 `/root/ascend_pytorch_tmp/` 下的受影响文件：

**常见修复模式：**

| 错误类型 | 修复方式 |
|----------|----------|
| 结构体成员被删除，原用于跨调用缓存 | 在 `.cpp` 文件模块级别引入 `static` map + mutex 替代 |
| 结构体成员重命名（如 `blocks` → `blocks_`） | 全局替换引用，或重命名 Ascend 侧冲突的同名类型 |
| 基类新增纯虚函数 | 在 `.hpp` 子类中添加 override 实现（若无对应 NPU 语义，返回 0 或抛 TORCH_CHECK） |
| 虚函数签名新增参数 | 更新 override 签名，将 Ascend 侧的原有逻辑提取为私有方法，新签名转发到私有方法 |
| 类型名遮蔽（inherited typedef 与 local struct 同名） | 重命名 Ascend 侧的 local struct，避免与 base class typedef 冲突 |

### 第四步：生成 patch 文件

```bash
cd /root/ascend_pytorch_tmp

# 确认 diff 范围正确（只包含本次要修复的文件）
git diff --stat

# 生成 patch（只 diff 本次涉及的文件）
git diff <文件1> <文件2> > /root/pytorch-npu/patches/NNNN-fix-<模块>-<描述>.patch
```

命名规则：`NNNN-fix-<受影响模块>-<问题简述>.patch`（NNNN 为四位序号，接续已有 patch）

检查 patch 内容是否符合预期：
```bash
cat /root/pytorch-npu/patches/NNNN-xxx.patch
```

### 第五步：更新 issue 文档

确认对应 `issues/YYYY-MM-DD-NNN-xxx.md` 中的 `对应 patch` 字段已填写正确的 patch 文件名。

### 第六步：提交

```bash
cd /root/pytorch-npu
git add patches/NNNN-xxx.patch issues/YYYY-MM-DD-NNN-xxx.md
git commit -m "Add patch and issue for <问题简述>"
git push
```

> workflow 中已有自动 patch 应用步骤，**无需手动更新 workflow 文件**。
> CI 会按文件名顺序遍历 `patches/*.patch`，逐个执行 `git apply --directory=ascend_pytorch`。

### 第七步：触发构建并观察结果

```bash
gh workflow run nightly-build.yml --repo kerer-ai/pytorch-npu
sleep 5
gh run list --repo kerer-ai/pytorch-npu --limit 3
```

构建约需 **50-60 分钟**。观察规律：
- 若运行时长比上次**更长**，说明本次 patch 生效，构建推进到了更深处
- 若在同一位置失败，说明 patch 未正确应用（检查 `Apply compatibility patches` 步骤日志）
- 若出现新的失败文件，说明上一个问题已修复，暴露了下一个兼容性问题 → 重新运行 `/analyze-failure`

## 注意事项

- **不要修改 workflow 文件**：`patches/` 目录下的 `.patch` 文件会被 CI 自动发现并应用
- **每个 patch 对应一个独立问题**：不要将多个不相关的修复合并到一个 patch
- **patch 退役**：当 `Apply compatibility patches` 步骤显示某 patch `❌ FAILED`（apply 失败），说明上游已合入该修复，可将对应 patch 文件删除并提交
- **本地克隆的状态**：`/root/ascend_pytorch_tmp` 中已应用的修改会在下次处理新问题时继续累积，`git diff` 始终反映相对于原始 HEAD 的全部变更
