import json
from pathlib import Path
from threading import Lock


class ActionLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()

    def log_action(
        self,
        *,
        problem_id: str,
        episode_id: str,
        step: int,
        tool: str,
        command: str,
        started_at: str,
        duration_ms: float,
        exit_code: int | None,
        timed_out: bool,
    ) -> None:
        event = {
            "problem_id": problem_id,
            "episode_id": episode_id,
            "step": step,
            "tool": tool,
            "command": command,
            "command_type": "unknown",
            "started_at": started_at,
            "duration_ms": duration_ms,
            "exit_code": exit_code,
            "timed_out": timed_out,
        }

        line = json.dumps(event, ensure_ascii=False) + "\n"

        with self._lock:
            with self.path.open("a", encoding="utf-8") as file:
                file.write(line)
