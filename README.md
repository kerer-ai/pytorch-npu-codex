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
