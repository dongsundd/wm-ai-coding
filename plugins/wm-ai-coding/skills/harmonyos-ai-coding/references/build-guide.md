# hvigor 编译参数详解

> 基于实际使用经验。

## hvigor 基础

hvigor 是 HarmonyOS 的构建工具，基于 Gulp + Node.js。

**项目根目录**：`hvigorfile.ts` 所在目录（项目根目录）

**重要**：hvigorw.bat 是 Windows 批处理文件，必须通过 `cmd.exe` 调用。

## 常用命令

### assembleApp（推荐）

完整打包应用（.hap + .app），包含签名。

```bash
# ✅ Git Bash / Windows 命令行
hvigorw assembleApp
```

**输出**：
- `products/default/build/default/outputs/default/app/default-default.hap`
- 已签名则生成 `default-default.app`

### assembleHap

打包 HAP（不包含完整签名，用于开发阶段快速验证）。

```bash
hvigorw assembleHap
```

### 查看可用任务

```bash
hvigorw tasks
```

输出示例：
```
Hook tasks
-------------
assembleApp - Assemble the task for the packaged app.

Sign tasks
-------------
SignApp - Sign the app package.
```

### --analyze 参数

```bash
hvigorw assembleApp --analyze=detail
```

| 级别 | 输出量 | 适用场景 |
|-----|-------|---------|
| 默认 | 关键信息 | 日常开发 |
| `--analyze=detail` | 全部日志 | 排查构建问题 |

## 环境变量

| 变量名 | 用途 | 说明 |
|-------|------|------|
| `DEVECO_SDK_HOME` | SDK 根目录 | **必须设置**。hvigorw 不会自动从自身路径推导 SDK，不设置会报 `SDK component missing`。固定路径：`D:\Program Files\Huawei\command-line-tools\sdk` |

**重要**：使用 `--no-daemon` 避免 daemon 进程导致 IDE Build 模式卡住：

```cmd
call hvigorw.bat --no-daemon assembleApp
```

> 注意：`--no-daemon` 禁用 daemon，每次编译会稍慢（~37s），但确保编译结束后 Build 模式自动结束。

### SDK 路径发现

**Windows cmd**：`where hvigorw` 是 Windows cmd 原生命令

```cmd
where hvigorw
# 输出: D:\Program Files\Huawei\command-line-tools\hvigor\bin\hvigorw.bat
```

**注意**：PowerShell 中 `where` 是 `Where-Object` 别名，不会搜索 PATH。在 PowerShell 中应使用 `cmd /c "where hvigorw"`。

## 模块编译（更快）

项目有模块结构，可以单独编译某个模块：

```bash
hvigorw assembleHap --analyze=normal
```

**说明**：
- 模块编译与完整编译速度差异不大（因项目较小）
- `--analyze=normal` 减少日志输出，加快构建

## 常见错误

### SDK Component Missing

```
hvigor ERROR: 00303168 Configuration Error
Error Message: SDK component missing.
```

**原因**：`DEVECO_SDK_HOME` 未设置或 SDK 版本与项目要求不匹配。

**解决**：

```bash
# 确认 hvigorw 可用
which hvigorw   # Linux
hvigorw --version
```

### Device Not Connected

```
[Fail] [ERR_HDC_CONNECTION_FAILED]...
```

**原因**：hvigor 需要连接设备或模拟器。

**解决**：

```bash
# 方式1：仅做静态分析（不需要设备）
hvigorw assembleHap

# 方式2：启动模拟器
hdc shell am start -a ohos.samples.launcher
```

### 签名配置错误

```
[Fail] [ERR_SIGNING_CONFIG_ERROR]...
```

**检查**：`build-profile.json5` 的 `signingConfigs` 配置。

当前项目未配置签名，构建时会跳过签名步骤。

```bash
# 查看签名状态
hvigorw buildInfo
```

### Clean 后重新编译

**使用 `--no-daemon` 简化流程：**

```cmd
call hvigorw.bat --no-daemon assembleApp
```

> 优点：无需手动停止 daemon，编译结束后自动退出，IDE Build 模式不会卡住。

## 构建产物

```
products/default/build/default/outputs/
└── default/
    ├── app/
    │   └── default-default.hap     ← assembleApp 输出
    └── hap/
        └── default-default-unsigned.hap  ← assembleHap 输出（未签名）
```

**注意**：项目的输出在 `products/default/build/` 而不是项目根目录的 `build/`。

## 编译速度优化

| 优化手段 | 效果 |
|---------|------|
| 增量编译（保留 build 目录） | 减少 40-60% 构建时间 |
| `--analyze=normal` 替代默认 | 减少 20-30% 日志开销 |
| 禁用实时预览 | 减少 10-20% 资源占用 |
