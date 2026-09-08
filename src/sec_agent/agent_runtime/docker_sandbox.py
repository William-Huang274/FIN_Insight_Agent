"""Host-side Docker adapter for disposable Python work; no host mounts or network.

Docker owns isolation, limits, process lifetime and bounded logs. This adapter
must remain on a trusted host: never expose its daemon socket to an agent.
Image selection is operator configuration, not a model tool parameter.
"""
from dataclasses import dataclass
import json
import re
import subprocess
from uuid import UUID, uuid4


@dataclass(frozen=True)
class SandboxResult:
    operation_id: str
    exit_code: int
    timed_out: bool
    output: str
    output_may_be_truncated: bool
    isolation: dict


class DockerPythonSandbox:
    def __init__(self, *, image_id: str, docker="docker", timeout_seconds=15):
        if not re.fullmatch(r"sha256:[a-f0-9]{64}", image_id):
            raise ValueError("sandbox_requires_pinned_local_image")
        if not 1 <= timeout_seconds <= 60:
            raise ValueError("sandbox_timeout_out_of_range")
        self.image_id, self.docker, self.timeout_seconds = image_id, docker, timeout_seconds

    def _docker(self, *args, timeout=15, check=True):
        result = subprocess.run([self.docker, *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=timeout,
                              check=False, shell=False)
        if check and result.returncode:
            # Do not include the full create command, which carries user code.
            raise RuntimeError(f"sandbox_docker_{args[0]}_failed: {result.stderr[-2000:]}")
        return result

    def execute(self, code: str, *, thread_id: str) -> SandboxResult:
        """Run code in a fresh empty /work. No files are imported or exported."""
        thread_id = str(UUID(thread_id))
        if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > 12000:
            raise ValueError("sandbox_code_size_invalid")
        operation_id = str(uuid4())
        name = "finsight-sandbox-" + operation_id
        container_id = None
        try:
            created = self._docker("create", "--pull", "never", "--name", name,
                "--label", "org.finsight.sandbox=" + operation_id,
                "--label", "org.finsight.thread=" + thread_id,
                "--network", "none", "--read-only", "--cap-drop", "ALL",
                "--security-opt", "no-new-privileges", "--user", "65534:65534",
                "--pids-limit", "32", "--memory", "256m", "--memory-swap", "256m",
                "--cpus", "0.5", "--ulimit", "nofile=128:128",
                "--tmpfs", "/work:rw,noexec,nosuid,nodev,size=64m,mode=1777",
                "--workdir", "/work", "--log-driver", "local",
                "--log-opt", "max-size=64k", "--log-opt", "max-file=1", "--log-opt", "compress=false",
                "--entrypoint", "python", self.image_id, "-I", "-B", "-u", "-c", code)
            container_id = created.stdout.strip()
            if not re.fullmatch(r"[a-f0-9]{64}", container_id):
                raise RuntimeError("sandbox_invalid_container_identity")
            self._docker("start", container_id)
            timed_out = False
            try:
                self._docker("wait", container_id, timeout=self.timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._docker("kill", container_id, check=False)
            inspected = json.loads(self._docker("inspect", container_id).stdout)[0]
            config = inspected["HostConfig"]
            isolation = {"image_id": inspected["Image"], "network": config["NetworkMode"],
                "readonly_root": config["ReadonlyRootfs"], "user": inspected["Config"]["User"],
                "bind_mounts": config.get("Binds") or [], "memory_bytes": config["Memory"],
                "pids_limit": config["PidsLimit"], "cap_drop": config["CapDrop"],
                "security_options": config["SecurityOpt"], "temporary_workspace": config["Tmpfs"]}
            logs = self._docker("logs", "--tail", "200", container_id, check=False)
            output = logs.stdout + logs.stderr
            return SandboxResult(operation_id, inspected["State"]["ExitCode"], timed_out,
                                 output[-16000:], True, isolation)
        finally:
            # Remove only this invocation's container, never volumes/images or
            # name-matched containers belonging to another operation.
            if container_id and re.fullmatch(r"[a-f0-9]{64}", container_id):
                self._docker("rm", "--force", container_id)


def sandbox_tool(sandbox: DockerPythonSandbox, *, thread_id: str):
    """Bind trusted scope before exposing the tool schema to the model."""
    from langchain_core.tools import tool
    from .conversation_agent import GrantedTool
    from dataclasses import asdict
    bound_thread = str(UUID(thread_id))

    @tool
    def run_isolated_python(code: str) -> dict:
        """Run Python in an empty disposable container for this task. No network,
        host files, credentials, package installation or persistent file access.
        Print results; output is bounded and may contain only the final portion.
        Never use this as a substitute for source-bound financial calculation.
        """
        return asdict(sandbox.execute(code, thread_id=bound_thread))

    return GrantedTool(run_isolated_python, "task_artifact_write",
                       "本次任务的空白临时容器；禁网、无宿主挂载；退出后临时文件销毁")
