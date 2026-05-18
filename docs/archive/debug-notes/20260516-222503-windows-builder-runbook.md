# Windows 构建机 Runbook

本 runbook 用于维护 `llm_tools` 的内网 Windows 构建机。权威目标是 Windows x64 发布。

## 目标边界

- Linux 控制端负责治理门禁、打包源码、下载产物和校验 SHA256。
- Windows 构建机负责生成 Windows x64 EXE 和安装包。
- 默认产物：
1. `sigmastar-flasher-vX.Y.Z-x64.exe`
2. `SigmaStarFlasher-Setup-X.Y.Z-x64.exe`
3. `ota-packager-gui-vX.Y.Z-x64.exe`
- x86 不进入默认发布基线；如需验证，必须显式设置 `WIN_BUILD_X86=1` 并单独记录结果。

## 构建机要求

1. Windows 10/11 或 Windows Server。
2. OpenSSH Server 可用，Linux 控制端可免密 SSH 登录。
3. PowerShell 5.1+。
4. Python launcher `py.exe`。
5. Python 3.10 x64。
6. Inno Setup 6。

检查命令：

```bash
./scripts/windows_builder_doctor.sh
```

## SSH 接入注意事项

- Windows 用户名必须使用 `whoami` 确认，不要按 Linux 用户名猜测。
- 若目标用户属于 Administrators 组，Windows OpenSSH 默认使用：
  `C:\ProgramData\ssh\administrators_authorized_keys`
- 普通用户授权文件为：
  `%USERPROFILE%\.ssh\authorized_keys`
- 授权文件必须是单行公钥，且 ACL 只保留目标用户、SYSTEM、Administrators。
- 手工复制长公钥容易引入换行，建议用 `.pub` 文件安装。

## 远程发布约束

- `scripts/release_windows_remote.env` 是本机私有配置，必须保持 ignored。
- 非默认 SSH key 用 `WIN_IDENTITY_FILE` 指定。
- Windows 工作目录末级必须是 `llm-tool-build`，避免清理脚本误删高层目录。
- Linux 下载 Windows 生成的 `SHA256SUMS.txt` 后必须先去掉 CRLF，再执行 `sha256sum -c`。
- 不要在远程发布脚本中依赖交互式密码、GUI 操作或未记录的构建机状态。

## 已验证发布命令

```bash
./scripts/windows_builder_doctor.sh
./scripts/release_windows_remote.sh X.Y.Z
```

完整 Linux + Windows：

```bash
./scripts/release_all.sh X.Y.Z
```

## 排障结论

- SSH 端口通但 `Permission denied`：优先检查 Windows 实际用户名、管理员组 `administrators_authorized_keys`、授权文件是否为空和 ACL。
- `py -3.10-32` 缺失：只影响实验性 x86，不影响默认 x64 发布。
- PowerShell/SSH 调 `.bat` 时参数含空格容易被重解析：远程 runner 应使用环境变量或 PowerShell 直接调用构建器，避免手拼 `cmd.exe /c`。
- PySide6/PyInstaller 32-bit 发布链不稳定：x86 不进入默认发布目标。
- Inno Setup `.iss` 预处理语法必须与 Inno Setup 6 实测兼容，不使用未验证函数。
