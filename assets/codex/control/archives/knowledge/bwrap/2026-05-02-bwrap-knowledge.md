# bwrap 运行时归档快照

- 归档时间：2026-05-02 00:35:00 +0800
- 归档脚本：`control/scripts/archive-bwrap.sh`

## 摘要

| 项目 | 值 |
| --- | --- |
| bwrap 路径 | `/usr/local/bin/bwrap` |
| 当前 bwrap 版本 | `bubblewrap 0.11.2` |
| /usr/bin/bwrap 版本 | `bubblewrap 0.4.0` |
| /usr/local/bin/bwrap 版本 | `bubblewrap 0.11.2` |
| dpkg bubblewrap 版本 | `0.4.0-1ubuntu4.1` |
| 支持 --perms | `yes` |
| 支持 --size | `yes` |
| 支持 --ro-bind-try | `yes` |
| unprivileged_userns_clone | `1` |
| 当前二进制 SHA256 | `8090db5d782e10ad0832cdeec4ce132ee898f305ffa21c631ced79b91547c140` |

## 知识结论

1. 当前默认 bwrap 已支持 `--perms`，可满足新沙箱参数要求。
2. `/usr/bin/bwrap` 与 `/usr/local/bin/bwrap` 版本不一致，需关注硬编码路径调用风险。
3. 内核允许 unprivileged user namespace，可优先使用非 setuid 模式。

## bwrap 关键 help 片段

```text
    --ro-bind-try SRC DEST       Equal to --ro-bind but ignores non-existent SRC
    --perms OCTAL                Set permissions of next argument (--bind-data, --file, etc.)
    --size BYTES                 Set size of next argument (only for --tmpfs)
```

## 系统信息

```text
NAME="Ubuntu"
VERSION="20.04.6 LTS (Focal Fossa)"
ID=ubuntu
ID_LIKE=debian
PRETTY_NAME="Ubuntu 20.04.6 LTS"
VERSION_ID="20.04"
HOME_URL="https://www.ubuntu.com/"
SUPPORT_URL="https://help.ubuntu.com/"
BUG_REPORT_URL="https://bugs.launchpad.net/ubuntu/"
PRIVACY_POLICY_URL="https://www.ubuntu.com/legal/terms-and-policies/privacy-policy"
VERSION_CODENAME=focal
UBUNTU_CODENAME=focal
```
