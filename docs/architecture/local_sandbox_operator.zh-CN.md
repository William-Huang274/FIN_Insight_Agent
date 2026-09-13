# 本地产品 sandbox 部署与检查

本入口复用已有 Docker 隔离执行器、MCP SDK、Uvicorn，不创建新的服务管理器。
适用本机试用部署；服务凭据是后端到 sidecar 的凭据，不是最终用户身份认证。
只监听 127.0.0.1:18796，不修改防火墙、Codex 权限或现有服务启动方式。

## 当前交接原因

之前写配置并后台启动服务的命令被执行入口以 `blocked by policy` 拒绝。
本脚本提供可审查的操作者入口，不意味着那项拒绝已解除。
Codex 本次仅运行 `plan` 和临时文件/内存测试；真实 `configure`、`serve`
交给已明确同意手动部署的操作者执行，不以改写命令绕过拒绝。

## 操作步骤

在仓库目录打开 PowerShell。以下两个变量分别指向已有两份运行配置所在目录、
已在本机资格验证的固定镜像。此镜像必须已存在；脚本不自动下载镜像。

```powershell
Set-Location D:/FIN_Insight_Agent
$finSandboxArgs = @('--settings-dir', 'Z:/FIN_Insight_Agent_qualification/dell_reference_vertical/report-workbench-20260906-a1', '--image-id', 'sha256:a3ab0b966bc4e91546a033e22093cb840908979487a9fc0e6e38295747e49ac0')
.venv/Scripts/python.exe -m scripts.deployment.local_sandbox plan @finSandboxArgs
```

`plan` 只读：验证两份 JSON 配置、已有连接的一致性、Docker 固定镜像和端口状态。
输出两项明确变更：host-settings.json 连接 127.0.0.1；container-settings.json
连接 host.docker.internal。两者共用新生成的服务凭据，值不打印。

确认没有其他程序正在编辑这两份配置、没有需要保持旧配置的进行中运行后：

```powershell
.venv/Scripts/python.exe -m scripts.deployment.local_sandbox configure @finSandboxArgs
if ($LASTEXITCODE -eq 0) {
    .venv/Scripts/python.exe -m scripts.deployment.local_sandbox serve @finSandboxArgs
} else {
    Write-Error '配置未完成，服务没有启动。请保留上方第一条错误。'
}
```

`configure` 只改两份配置中的 conversation_sandbox_url/token，保留其他字段。
原字节备份到配置目录下 sandbox-config-backups/<唯一编号>/；备份包含已有配置的
敏感字段，和原配置一样留在本机受控目录，不上传 Git。
若第二份写入失败，会恢复本次已写的第一份；发现既有冲突配置时停止，不覆盖。
重复配置不会轮换凭据。两文件不是跨进程事务，安装期间应停止其他配置写入者。

`serve` 前台运行已有 MCP 服务，错误显示在当前终端；保持终端开启，Ctrl+C 停止。
端口已有监听时停止，不杀进程。不会自动重启工作台或 Docker 容器。

如果第一条错误是 `No Python at ...`，Python 尚未启动，配置模块也未执行。
先检查 `.venv/pyvenv.cfg` 的 home 对应解释器在操作者终端是否可用；不要以此诊断
Docker/MCP。2026-09-11 本机发现该启动错误，部署人员终端无法定位 uv 缓存解释器，
而 Codex 子进程可运行，具体会话差异未查明。已将同一 CPython 3.11.14 复制到
项目 `.venv/sandbox-python311`，备份 pyvenv.cfg 后仅修改 home，保留原 site-packages。
该本机修复不上传解释器、不更改系统 Python，也不代表所有其他机器已修复。

在另一个仓库 PowerShell 窗口，重新定义上述 `$finSandboxArgs` 后：

```powershell
.venv/Scripts/python.exe -m scripts.deployment.local_sandbox check @finSandboxArgs --container finsight-dell-report-workbench-langgraph-api-1
```

检查范围：宿主机无凭据/错误凭据均被拒绝、正确凭据列出唯一执行工具；
现有 native 容器读取自己挂载的配置并访问 host.docker.internal，检查凭据与宿主匹配。
不会调用执行工具，不产生模型费用。

如果容器检查失败，先核对是否读到新配置，再区分到宿主的连通性与 MCP 认证问题。
当前部署将 container-settings.json 作为单文件只读挂载；原子替换宿主文件后，
必须验证容器实际读取结果，不能仅凭宿主写入成功认定生效。
不要自动改为 0.0.0.0、放开防火墙或删除重建服务来试错。

## 接入验收与恢复

宿主与容器检查通过后，仍需在真实产品中完成：标准模式拒绝时零执行；批准后
才进入空白离线容器，返回固定计算结果；检查运行记录及其他两档权限。
独立脚本/模拟模型验证不是此前端验收，也不需要用付费金融任务测试连接。
原生对话入口每次构建读取 settings，检查后用新运行验证，不在旧运行中途更换配置。
Hermes 当前工具注册不含 sandbox，不能把 native 接入称为 Hermes 已接入。

恢复时先 Ctrl+C 停止新 sidecar。仅当当前两份配置仍与备份 manifest 中
installed_sha256 一致时，才可恢复对应原件；若其他字段后来已修改，先比较差异，
只移除本次连接字段，避免覆盖后续配置。恢复后同样核对容器挂载读到的版本。

## 本轮验证状态

部署模块使用临时配置验证备份、原字段保留、重复安装、失败回退、冲突拒绝；
ASGI 测试验证正确/错误凭据与工具目录，检查过程不执行代码。
真实本机只读 plan 已通过前置检查，显示 configured=false、port_listening=false。
以上为启动前状态。2026-09-11 操作者手动启动后，宿主与 native 容器 check 均通过；
真实前端四场景（标准拒绝/标准批准/代我批准/完全访问）全部通过。
两次标准模式决策前无容器事件，拒绝零执行，其他三次均返回42并清理临时容器。
8模型请求/45609tokens/未知0/估算¥0.01205。四窗口重新打开后的正文回读通过；
仍需保持服务终端开启，生产托管和 Hermes sandbox 不在该验收范围。
