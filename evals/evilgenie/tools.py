"""Custom tools for reward hacking benchmark with output truncation."""

import asyncio
from datetime import datetime, timezone
from time import perf_counter

from inspect_ai.tool import Tool, tool
from inspect_ai.util import sandbox

from truncation import format_exec_result
from records.action_context import current_episode, ActionLoggingError
from records.action_logger import ActionLogger


# Una instancia compartida por las herramientas de este proceso.
action_logger = ActionLogger("logs/actions.jsonl")


async def _execute_and_log(
    command: str,
    tool_name: str,
    executable: list[str],
    timeout: int,
) -> str:
    """Ejecuta un comando, registra su ejecución y devuelve su salida."""

    context = current_episode.get()

    started_at = datetime.now(timezone.utc).isoformat()
    start_time = perf_counter()

    result = None
    exit_code=None
    timed_out = False

    try:
        result = await sandbox().exec(
            executable + [command],
            timeout=timeout,
        )
        exit_code = result.returncode
        return format_exec_result(result)

    except (TimeoutError, asyncio.TimeoutError):
        timed_out = True
        raise

    finally:
        duration_ms = (perf_counter() - start_time) * 1000

        if context is not None:
            try:
                action_logger.log_action(
                    problem_id=context.problem_id,
                    episode_id=context.episode_id,
                    step=context.next_step(),
                    tool=tool_name,
                    command=command,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    exit_code=exit_code,
                    timed_out=timed_out,
                )
            except Exception as exc:
                context.logging_error = repr(exc)
                raise ActionLoggingError(
                    f"No se pudo registrar una acción del episodio "
                    f"{context.episode_id}"
                ) from exc


@tool
def safe_bash(timeout: int = 180) -> Tool:
    """Bash tool with automatic output truncation."""

    async def execute(cmd: str) -> str:
        return await _execute_and_log(
            command=cmd,
            tool_name="safe_bash",
            executable=["bash", "-c"],
            timeout=timeout,
        )

    return execute


@tool
def safe_python(timeout: int = 180) -> Tool:
    """Python tool with automatic output truncation."""

    async def execute(code: str) -> str:
        return await _execute_and_log(
            command=code,
            tool_name="safe_python",
            executable=["python", "-c"],
            timeout=timeout,
        )

    return execute
