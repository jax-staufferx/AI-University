"""Sandboxed code execution for Ship-it sessions. Time-limited, memory-limited, no network.

Isolation is best-effort for a local single-user tool: resource limits (CPU time, address
space, process count, file size) are always enforced via rlimits; network isolation uses a
Linux network namespace via `unshare --net` when available, and is flagged in the result when
it falls back to an unsandboxed-network subprocess so callers can be honest about the guarantee.
"""

import os
import resource
import shutil
import subprocess
import tempfile
from dataclasses import dataclass

TIMEOUT_SECONDS = 10
MEMORY_LIMIT_BYTES = 256 * 1024 * 1024  # 256 MB
CPU_LIMIT_SECONDS = 10
MAX_OUTPUT_CHARS = 5000


@dataclass
class SandboxResult:
    stdout: str
    stderr: str
    return_code: int | None
    timed_out: bool
    network_sandboxed: bool


def _limit_resources() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (CPU_LIMIT_SECONDS, CPU_LIMIT_SECONDS))
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (32, 32))
    resource.setrlimit(resource.RLIMIT_FSIZE, (10 * 1024 * 1024, 10 * 1024 * 1024))


def run_python(code: str) -> SandboxResult:
    with tempfile.TemporaryDirectory() as tmpdir:
        script_path = os.path.join(tmpdir, "submission.py")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(code)

        unshare = shutil.which("unshare")
        network_sandboxed = False
        if unshare:
            # New network namespace with no interfaces configured => no network reachability.
            cmd = [unshare, "--net", "-r", "python3", "submission.py"]
            network_sandboxed = True
        else:
            cmd = ["python3", "submission.py"]

        env = {"PATH": "/usr/bin:/bin", "HOME": tmpdir, "PYTHONDONTWRITEBYTECODE": "1"}

        try:
            proc = subprocess.run(
                cmd,
                cwd=tmpdir,
                env=env,
                capture_output=True,
                text=True,
                timeout=TIMEOUT_SECONDS,
                preexec_fn=_limit_resources,
            )
            return SandboxResult(
                stdout=proc.stdout[-MAX_OUTPUT_CHARS:],
                stderr=proc.stderr[-MAX_OUTPUT_CHARS:],
                return_code=proc.returncode,
                timed_out=False,
                network_sandboxed=network_sandboxed,
            )
        except subprocess.TimeoutExpired as e:
            stdout = (e.stdout or "")[-MAX_OUTPUT_CHARS:] if isinstance(e.stdout, str) else ""
            stderr = (e.stderr or "")[-MAX_OUTPUT_CHARS:] if isinstance(e.stderr, str) else ""
            return SandboxResult(
                stdout=stdout,
                stderr=stderr + f"\n[timed out after {TIMEOUT_SECONDS}s]",
                return_code=None,
                timed_out=True,
                network_sandboxed=network_sandboxed,
            )
