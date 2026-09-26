from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import os
from pathlib import Path
import socket
import tempfile
import time
from typing import Any


RUNTIME_VERSION = "fap.browser.runtime.1.0.01.v1"
TERMINAL_STATES = frozenset({"completed", "login_timeout"})
VALID_STATES = frozenset(
    {
        "created",
        "browser_starting",
        "browser_ready",
        "login_required",
        "chatgpt_ready",
        "running",
        "completed",
        "failed",
        "login_timeout",
    }
)


@dataclass(frozen=True)
class BrowserRuntimeState:
    version: str
    state: str
    branch: str
    goal_sha256: str
    updated_unix: float
    pid: int
    host: str
    cdp_url: str
    last_url: str = ""
    last_error: str = ""
    restart_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class RuntimeStateStore:
    """Atomic, non-secret state for restart-safe browser operation."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, state: BrowserRuntimeState) -> None:
        if state.state not in VALID_STATES:
            raise ValueError(f"invalid runtime state: {state.state}")
        payload = json.dumps(
            state.to_dict(),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        ) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=self.path.name + ".",
            suffix=".tmp",
            dir=str(self.path.parent),
        )
        tmp = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, self.path)
        finally:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def read(self) -> BrowserRuntimeState | None:
        if not self.path.is_file():
            return None
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            state = BrowserRuntimeState(**payload)
        except Exception:
            return None
        if state.version != RUNTIME_VERSION or state.state not in VALID_STATES:
            return None
        return state


class RuntimeLock:
    """Single-controller lock with stale-process recovery."""

    def __init__(
        self,
        path: str | Path,
        *,
        stale_after_sec: float = 43_200.0,
    ) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.stale_after_sec = float(stale_after_sec)
        self.acquired = False
        if not 60 <= self.stale_after_sec <= 604_800:
            raise ValueError("stale_after_sec must be in [60, 604800]")

    def acquire(self) -> None:
        if self.acquired:
            return
        record = {
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "created_unix": time.time(),
        }
        data = (json.dumps(record, sort_keys=True) + "\n").encode("utf-8")

        for _ in range(2):
            try:
                fd = os.open(
                    self.path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                )
            except FileExistsError:
                if self._clear_if_stale():
                    continue
                current = self._read_record()
                pid = current.get("pid", "?") if current else "?"
                raise RuntimeError(
                    f"another FAP browser controller is active (pid={pid})"
                )
            else:
                with os.fdopen(fd, "wb") as handle:
                    handle.write(data)
                    handle.flush()
                    os.fsync(handle.fileno())
                self.acquired = True
                return
        raise RuntimeError("could not acquire FAP browser runtime lock")

    def release(self) -> None:
        if not self.acquired:
            return
        current = self._read_record()
        if current and int(current.get("pid", -1)) == os.getpid():
            self.path.unlink(missing_ok=True)
        self.acquired = False

    def __enter__(self) -> "RuntimeLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()

    def _read_record(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
            return value if isinstance(value, dict) else {}
        except Exception:
            return {}

    def _clear_if_stale(self) -> bool:
        record = self._read_record()
        pid = int(record.get("pid", -1) or -1)
        created = float(record.get("created_unix", 0.0) or 0.0)
        age = max(0.0, time.time() - created) if created else self.stale_after_sec + 1

        same_host = str(record.get("host") or "") == socket.gethostname()
        dead_local_pid = same_host and pid > 0 and not _pid_alive(pid)
        expired = age > self.stale_after_sec
        malformed = not record

        if malformed or dead_local_pid or expired:
            self.path.unlink(missing_ok=True)
            return True
        return False


class BrowserRuntimeJournal:
    """Records only operational metadata; prompts and page text are excluded."""

    def __init__(
        self,
        runtime_dir: str | Path,
        *,
        branch: str,
        goal: str,
        cdp_url: str,
    ) -> None:
        self.runtime_dir = Path(runtime_dir).expanduser().resolve()
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.store = RuntimeStateStore(self.runtime_dir / "state.json")
        self.lock = RuntimeLock(self.runtime_dir / "controller.lock")
        self.branch = str(branch or "").strip()
        self.goal_sha256 = sha256(
            str(goal or "").encode("utf-8", errors="replace")
        ).hexdigest()
        self.cdp_url = str(cdp_url or "").strip()
        self.restart_count = 0

    def __enter__(self) -> "BrowserRuntimeJournal":
        self.lock.acquire()
        previous = self.store.read()
        if (
            previous is not None
            and previous.branch == self.branch
            and previous.goal_sha256 == self.goal_sha256
            and previous.state not in TERMINAL_STATES
        ):
            self.restart_count = int(previous.restart_count) + 1
        self.update("created")
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc is not None:
            self.update(
                "failed",
                error=f"{type(exc).__name__}: {exc}",
            )
        self.lock.release()

    def update(
        self,
        state: str,
        *,
        url: str = "",
        error: str = "",
    ) -> BrowserRuntimeState:
        if state not in VALID_STATES:
            raise ValueError(f"invalid runtime state: {state}")
        record = BrowserRuntimeState(
            version=RUNTIME_VERSION,
            state=state,
            branch=self.branch,
            goal_sha256=self.goal_sha256,
            updated_unix=time.time(),
            pid=os.getpid(),
            host=socket.gethostname(),
            cdp_url=self.cdp_url,
            last_url=_safe_url_metadata(url),
            last_error=str(error or "")[:2000],
            restart_count=self.restart_count,
        )
        self.store.write(record)
        return record


def default_runtime_dir() -> Path:
    local = os.getenv("LOCALAPPDATA", "").strip()
    if local:
        return Path(local).expanduser() / "FAP" / "browser-runtime"
    return Path.home() / ".fap" / "browser-runtime"


def _safe_url_metadata(url: str) -> str:
    value = str(url or "").strip()
    if not value:
        return ""
    # Avoid persisting query strings/fragments that may contain sensitive data.
    try:
        from urllib.parse import urlsplit, urlunsplit

        parts = urlsplit(value)
        if parts.scheme not in {"http", "https"}:
            return ""
        return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
    except Exception:
        return ""


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if pid == os.getpid():
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        # Windows and restricted environments can reject the probe even when
        # the process exists. Prefer treating it as active unless the lock ages
        # out, avoiding two controllers fighting over one browser.
        return True
    return True
