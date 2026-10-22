"""Custom tools for reward hacking benchmark with output truncation."""

import asyncio
from datetime import datetime, timezone
from time import perf_counter
from typing import Any

from inspect_ai.tool import Tool, ToolDef, text_editor, tool
from inspect_ai.util import sandbox

from truncation import format_exec_result
from records.action_context import current_episode, ActionLoggingError
from records.action_logger import ActionLogger


# Una instancia compartida por las herramientas de este proceso.
# El archivo es uno por corrida: logs/actions_<EG_RUN_ID>.jsonl
action_logger = ActionLogger.for_run("logs")


def _log(
    *,
    tool_name: str,
    command: str,
    arguments: dict[str, Any],
    started_at: str,
    start_time: float,
    exit_code: int | None,
    timed_out: bool,
    error: str | None,
    output: str | None,
    stdout: str | None = None,
    stderr: str | None = None,
) -> None:
    """Registra una invocación con el contexto del episodio activo."""

    context = current_episode.get()
    if context is None:
        return

    try:
        action_logger.log_action(
            run_id=action_logger.run_id,
            model=context.model,
            sample_id=context.sample_id,
            epoch=context.epoch,
            problem_id=context.problem_id,
            episode_id=context.episode_id,
            step=context.next_step(),
            tool=tool_name,
            command=command,
            arguments=arguments,
            started_at=started_at,
            duration_ms=(perf_counter() - start_time) * 1000,
            exit_code=exit_code,
            timed_out=timed_out,
            error=error,
            output=output,
            stdout=stdout,
            stderr=stderr,
        )
    except Exception as exc:
        context.logging_error = repr(exc)
        raise ActionLoggingError(
            f"No se pudo registrar una acción del episodio "
            f"{context.episode_id}"
        ) from exc


async def _execute_and_log(
    command: str,
    tool_name: str,
    executable: list[str],
    timeout: int,
) -> str:
    """Ejecuta un comando, registra su ejecución y devuelve su salida."""

    started_at = datetime.now(timezone.utc).isoformat()
    start_time = perf_counter()

    result = None
    output = None
    timed_out = False
    error = None

    try:
        result = await sandbox().exec(
            executable + [command],
            timeout=timeout,
        )
        output = format_exec_result(result)
        return output

    except (TimeoutError, asyncio.TimeoutError):
        timed_out = True
        raise

    except Exception as exc:
        error = repr(exc)
        raise

    finally:
        _log(
            tool_name=tool_name,
            command=command,
            arguments={},
            started_at=started_at,
            start_time=start_time,
            exit_code=result.returncode if result is not None else None,
            timed_out=timed_out,
            error=error,
            output=output,
            stdout=result.stdout if result is not None else None,
            stderr=result.stderr if result is not None else None,
        )


@tool
def safe_bash(timeout: int = 180) -> Tool:
    """Bash tool with automatic output truncation to prevent context overflow.

    Truncates output to 3000 characters using middle truncation, preserving
    the beginning and end of output while removing the middle portion.

    Args:
        timeout: Command timeout in seconds

    Returns:
        Bash tool with truncation
    """

    async def execute(cmd: str) -> str:
        """Run a bash command with output truncation.

        Args:
            cmd: The bash command to execute

        Returns:
            Command output (truncated if > 3000 chars)
        """
        return await _execute_and_log(
            command=cmd,
            tool_name="safe_bash",
            executable=["bash", "-c"],
            timeout=timeout,
        )

    return execute


@tool
def safe_python(timeout: int = 180) -> Tool:
    """Python tool with automatic output truncation to prevent context overflow.

    Truncates output to 3000 characters using middle truncation, preserving
    the beginning and end of output while removing the middle portion.

    Args:
        timeout: Command timeout in seconds

    Returns:
        Python tool with truncation
    """

    async def execute(code: str) -> str:
        """Run Python code with output truncation.

        Args:
            code: The Python code to execute

        Returns:
            Command output (truncated if > 3000 chars)
        """
        return await _execute_and_log(
            command=code,
            tool_name="safe_python",
            executable=["python", "-c"],
            timeout=timeout,
        )

    return execute


def logged_text_editor() -> ToolDef:
    """text_editor de Inspect, con el mismo nombre y esquema, más registro.

    Se reutiliza la definición original (nombre, descripción y parámetros)
    para que el modelo vea exactamente la misma herramienta que en el
    benchmark original.
    """

    inner = ToolDef(text_editor())

    async def execute(**kwargs: Any) -> Any:
        started_at = datetime.now(timezone.utc).isoformat()
        start_time = perf_counter()
        output = None
        error = None

        try:
            output = await inner.tool(**kwargs)
            return output

        except Exception as exc:
            error = repr(exc)
            raise

        finally:
            _log(
                tool_name="text_editor",
                command=str(kwargs.get("command")),
                arguments=kwargs,
                started_at=started_at,
                start_time=start_time,
                exit_code=None,
                timed_out=False,
                error=error,
                output=None if output is None else str(output),
            )

    return ToolDef(
        execute,
        name=inner.name,
        description=inner.description,
        parameters=inner.parameters,
        parallel=inner.parallel,
        viewer=inner.viewer,
    )
