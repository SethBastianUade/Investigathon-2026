
"""Contexto por episodio para registrar acciones del agente."""

from contextvars import ContextVar
from dataclasses import dataclass
from uuid import uuid4
from inspect_ai.solver import Solver, solver


class ActionLoggingError(RuntimeError):
    """Indica que no se pudo persistir un evento de acción."""


@dataclass
class EpisodeContext:
    problem_id: str
    episode_id: str
    # Para cruzar cada acción con el puntaje de la muestra en el log .eval.
    sample_id: str = ""
    epoch: int = 0
    model: str = ""
    step: int = 0
    logging_error: str | None = None

    def next_step(self) -> int:
        """Devuelve el siguiente número de invocación."""
        self.step += 1
        return self.step


current_episode: ContextVar[EpisodeContext | None] = ContextVar(
    "current_episode",
    default=None,
)


def create_episode_context(
    problem_id: str,
    sample_id: str = "",
    epoch: int = 0,
    model: str = "",
) -> EpisodeContext:
    """Crea un contexto nuevo para una ejecución de un problema."""
    return EpisodeContext(
        problem_id=str(problem_id),
        episode_id=str(uuid4()),
        sample_id=str(sample_id),
        epoch=epoch,
        model=model,
    )



@solver
def with_episode_context(inner_solver: Solver) -> Solver:
    """Activa un contexto independiente durante cada muestra."""

    async def solve(state, generate):
        metadata = state.metadata or {}
        problem_id = metadata.get("problem_id")

        if problem_id is None:
            raise ValueError(
                "La muestra no contiene metadata['problem_id']; "
                "no se puede identificar el episodio."
            )

        context = create_episode_context(
            problem_id,
            sample_id=state.sample_id,
            epoch=state.epoch,
            model=str(state.model),
        )
        token = current_episode.set(context)

        try:
            result = await inner_solver(state, generate)

            if context.logging_error is not None:
                raise ActionLoggingError(
                    "Episodio inválido: falló el registro de acciones. "
                    f"Detalle: {context.logging_error}"
                )

            return result

        finally:
            current_episode.reset(token)

    return solve

