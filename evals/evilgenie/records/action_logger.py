import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any


# Tope por campo de salida. Alcanza para ver resultados de tests y errores
# sin que un `cat` de un archivo enorme infle el registro.
MAX_OUTPUT_CHARS = 20_000


def _cap(text: str | None) -> tuple[str | None, bool]:
    """Recorta un texto largo y avisa si lo recortó."""
    if text is None or len(text) <= MAX_OUTPUT_CHARS:
        return text, False
    return text[:MAX_OUTPUT_CHARS], True


class ActionLogger:
    def __init__(self, path: str | Path, run_id: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.run_id = run_id
        self._lock = Lock()

    @classmethod
    def for_run(cls, log_dir: str | Path) -> "ActionLogger":
        """Crea el logger de esta corrida: un archivo por EG_RUN_ID."""
        run_id = os.environ.get("EG_RUN_ID") or datetime.now(
            timezone.utc
        ).strftime("%Y%m%dT%H%M%SZ")
        return cls(Path(log_dir) / f"actions_{run_id}.jsonl", run_id)

    def log_action(
        self,
        *,
        run_id: str,
        model: str,
        sample_id: str,
        epoch: int,
        problem_id: str,
        episode_id: str,
        step: int,
        tool: str,
        command: str,
        arguments: dict[str, Any],
        started_at: str,
        duration_ms: float,
        exit_code: int | None,
        timed_out: bool,
        error: str | None,
        output: str | None,
        stdout: str | None = None,
        stderr: str | None = None,
    ) -> None:
        output, output_truncated = _cap(output)
        stdout, stdout_truncated = _cap(stdout)
        stderr, stderr_truncated = _cap(stderr)

        event = {
            "run_id": run_id,
            "model": model,
            "sample_id": sample_id,
            "epoch": epoch,
            "problem_id": problem_id,
            "episode_id": episode_id,
            "step": step,
            "tool": tool,
            "command": command,
            "arguments": arguments,
            "command_type": "unknown",
            "started_at": started_at,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "timed_out": timed_out,
            "error": error,
            # Lo que recibió el agente (ya truncado a 3000 por la herramienta).
            "output": output,
            # Salida cruda del sandbox (solo bash/python).
            "stdout": stdout,
            "stderr": stderr,
            "output_truncated": output_truncated
            or stdout_truncated
            or stderr_truncated,
        }

        line = json.dumps(event, ensure_ascii=False, default=str) + "\n"

        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line)
