from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import subprocess
from typing import Any, Mapping

from fap_interaction.provider import ProviderExecutionError, ProviderTimeoutError


_ENV_ALLOWLIST = (
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "HOME",
    "USERPROFILE",
    "LANG",
    "LC_ALL",
)


@dataclass(frozen=True)
class ProcessProviderSpec:
    executable: str
    fixed_args: tuple[str, ...] = ()
    timeout_s: float = 20.0
    max_input_bytes: int = 2 * 1024 * 1024
    max_output_bytes: int = 16 * 1024 * 1024

    def validate(self) -> "ProcessProviderSpec":
        path = Path(self.executable)
        if not path.is_absolute():
            raise ValueError("provider executable must be an absolute path")
        if path.is_symlink():
            raise ValueError("provider executable symlink is not allowed")
        if not path.is_file():
            raise ValueError("provider executable must be an existing file")
        if not (0.05 <= float(self.timeout_s) <= 120.0):
            raise ValueError("provider timeout out of range")
        if not (1024 <= int(self.max_input_bytes) <= 64 * 1024 * 1024):
            raise ValueError("provider input limit out of range")
        if not (1024 <= int(self.max_output_bytes) <= 64 * 1024 * 1024):
            raise ValueError("provider output limit out of range")
        for arg in self.fixed_args:
            if not isinstance(arg, str) or "\x00" in arg:
                raise ValueError("invalid fixed provider argument")
        return self


class CommandJSONClient:
    """Trusted local provider bridge using shell=False and a bounded JSON protocol."""

    def __init__(self, spec: ProcessProviderSpec):
        self.spec = spec.validate()

    @staticmethod
    def _env() -> dict[str, str]:
        env = {k: os.environ[k] for k in _ENV_ALLOWLIST if k in os.environ}
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        return env

    @staticmethod
    def _canonical_json(payload: Mapping[str, Any]) -> bytes:
        return json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")

    def request(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = self._canonical_json(payload)
        if len(body) > self.spec.max_input_bytes:
            raise ProviderExecutionError("provider request exceeds input limit")

        command = [self.spec.executable, *self.spec.fixed_args]
        try:
            completed = subprocess.run(
                command,
                input=body,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=self.spec.timeout_s,
                check=False,
                shell=False,
                env=self._env(),
            )
        except subprocess.TimeoutExpired as exc:
            raise ProviderTimeoutError("provider timed out") from exc
        except OSError as exc:
            raise ProviderExecutionError("provider process could not start") from exc

        if completed.returncode != 0:
            raise ProviderExecutionError(
                f"provider exited with code {completed.returncode}"
            )
        if len(completed.stdout) > self.spec.max_output_bytes:
            raise ProviderExecutionError("provider response exceeds output limit")
        try:
            decoded = completed.stdout.decode("utf-8", errors="strict")
            result = json.loads(decoded)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ProviderExecutionError("provider returned malformed JSON") from exc
        if not isinstance(result, dict):
            raise ProviderExecutionError("provider response must be a JSON object")
        if "error" in result:
            raise ProviderExecutionError("provider reported an error")
        return result
