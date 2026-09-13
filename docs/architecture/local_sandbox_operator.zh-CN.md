# 本地工具沙箱

FinSight 可通过 MCP 服务在隔离的 Docker 容器中执行已批准的工具操作。该服务只监听 `127.0.0.1:18796`，使用服务凭据连接工作台；最终用户身份和操作审批由工作台负责。

## 准备与启动

需要可用的 Docker Engine、已准备的固定镜像，以及包含 `host-settings.json` 和 `container-settings.json` 的设置目录。以下示例中的路径和镜像 ID 需替换为本机实际值：

```powershell
$finSandboxArgs = @('--settings-dir', 'D:/private/finsight-session', '--image-id', 'sha256:YOUR_PREPARED_IMAGE_DIGEST')
python -m scripts.deployment.local_sandbox plan @finSandboxArgs
```

`plan` 检查配置、镜像和端口，展示将要修改的连接字段，不写入配置、不下载镜像、不执行工具。输出不会打印凭据。

停止其他配置写入者后，执行配置和服务启动：

```powershell
python -m scripts.deployment.local_sandbox configure @finSandboxArgs
if ($LASTEXITCODE -eq 0) {
    python -m scripts.deployment.local_sandbox serve @finSandboxArgs
}
```

`configure` 只更新沙箱 URL 和凭据字段，保留其他设置；原件备份到设置目录的 `sandbox-config-backups/`。第二份配置写入失败会恢复第一份，发现冲突则停止。备份也包含敏感字段，应保留在本机受控目录。重复配置不会轮换凭据。

`serve` 在当前终端运行。保持终端开启，使用 Ctrl+C 停止；端口被占用时会报错，不会终止占用者或自动重启工作台。

## 检查连接

在另一个终端中使用同一组参数，将容器名称替换为实际 Agent Server 容器：

```powershell
python -m scripts.deployment.local_sandbox check @finSandboxArgs --container YOUR_AGENT_SERVER_CONTAINER
```

检查包括：宿主端错误或缺失凭据是否被拒绝、正确凭据是否能读取工具目录、原生容器能否读取自己的配置并经 `host.docker.internal` 连接服务。检查不执行工具，也不产生模型调用。

配置文件使用只读挂载时，宿主原子替换文件后应确认容器读取到了新版本。连接失败先区分配置、网络和认证原因；不要通过暴露外网端口或删除数据卷来排错。

## 工作台行为与验证

标准权限模式在用户批准前不执行工具，拒绝时不创建执行容器；批准后在临时隔离容器中运行，并记录结果与清理状态。配置变更应通过新任务验证，不在旧任务中途更换连接。

2026-09-11 的四个实际界面测试覆盖标准拒绝、标准批准及另外两种权限模式：拒绝场景零执行，其他三次返回预设计算结果并清理容器。测试合计 8 次模型请求、45,609 tokens、0 个用量未知请求；它验证有限的本地交互，不代表生产托管或 Hermes 沙箱支持。

## 故障排查与恢复

- Python 无法启动时，先检查解释器路径与虚拟环境配置；此时服务尚未运行，不能据此判断 Docker 或 MCP 失败。
- 配置冲突时保留报错并比较当前文件，不覆盖其他进程的新修改。
- 恢复前停止沙箱服务，核对备份清单和当前文件摘要。若设置已有后续修改，应合并对应连接字段，避免整份回滚覆盖新配置。
- 恢复后重新检查宿主及容器内读取的配置。

[工作台运行说明](../public/quickstart.zh-CN.md) · [系统架构](../public/architecture.zh-CN.md)
