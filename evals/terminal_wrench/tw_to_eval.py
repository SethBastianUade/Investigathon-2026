"""Convierte trayectorias de Terminal Wrench a un .eval de Inspect, para verlas con `inspect view`.

Terminal Wrench guarda cada trayectoria en formato ATIF (agent/trajectory.json). El agente
(terminus-2) no usa llamadas nativas a herramientas: responde con un JSON que trae un lote de
comandos y recibe la salida de la terminal de todo el lote junta. En el .eval queda así:
  - cada paso del agente es un mensaje del asistente con su texto y un ToolCall por comando;
  - la salida de la terminal va en el mensaje de usuario siguiente (como la recibió el agente).
Cada trayectoria es una muestra; el puntaje es su clasificación (◆ ◇ ~ ° o baseline), con el
resumen del exploit, los pasos clave y las categorías en la explicación y la metadata.

No modifica el dataset. Uso, desde la raíz del repo (con el Python que tiene inspect-ai):
    python evals/terminal_wrench/tw_to_eval.py --tasks "^1012$"
    python evals/terminal_wrench/tw_to_eval.py --tasks "^10" --models gpt-5.4 --trees hack baseline
    inspect view --log-dir terminal-wrench/_eval
La salida va por defecto a terminal-wrench/_eval/, dentro de la carpeta del dataset, que está
gitignored: los datos derivados del dataset tampoco se suben.
"""

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from inspect_ai.log import (
    EvalConfig,
    EvalDataset,
    EvalLog,
    EvalResults,
    EvalSample,
    EvalSpec,
    write_eval_log,
)
from inspect_ai.model import ChatMessageAssistant, ChatMessageUser
from inspect_ai.scorer import Score
from inspect_ai.tool import ToolCall

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = ROOT / "terminal-wrench"
TREES = {
    "hack": "hack_trajectories",
    "baseline": "baseline_trajectories",
    "non_hack": "non_hack_trajectories",
    "sanitized": "sanitized_trajectories",
    "stripped": "stripped_trajectories",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def convert_messages(steps: list[dict]) -> list:
    messages = []
    for step in steps:
        if step["source"] != "agent":
            messages.append(ChatMessageUser(content=step.get("message") or ""))
            continue
        calls = [
            ToolCall(
                id=call.get("tool_call_id") or f"call_{step['step_id']}_{i}",
                function=call.get("function_name") or "bash_command",
                arguments=call.get("arguments") or {},
            )
            for i, call in enumerate(step.get("tool_calls") or [])
        ]
        messages.append(
            ChatMessageAssistant(
                content=step.get("message") or "",
                tool_calls=calls or None,
                model=step.get("model_name"),
            )
        )
        results = (step.get("observation") or {}).get("results") or []
        output = "\n".join(r.get("content") or "" for r in results)
        if output:
            messages.append(ChatMessageUser(content=output))
    return messages


def convert_trajectory(traj_dir: Path, task_id: str, model: str, tree: str) -> EvalSample | None:
    traj_path = traj_dir / "trial" / "agent" / "trajectory.json"
    if not traj_path.exists():
        return None
    meta = read_json(traj_dir / "metadata.json") if (traj_dir / "metadata.json").exists() else {}
    steps = read_json(traj_path)["steps"]
    messages = convert_messages(steps)
    classification = meta.get("classification", "baseline" if tree == "baseline" else "desconocida")
    explanation = meta.get("brief_exploit_summary") or meta.get("explanation") or ""
    return EvalSample(
        id=f"{task_id}/{model}/{tree}/{traj_dir.name}",
        epoch=1,
        input=steps[0].get("message") or "" if steps else "",
        target="",
        messages=messages,
        scores={
            "terminal_wrench": Score(
                value=classification,
                explanation=explanation,
                metadata={
                    "reward": meta.get("reward"),
                    "key_hack_steps": meta.get("key_hack_steps"),
                    "observed_categories": meta.get("observed_categories"),
                },
            )
        },
        metadata={"task_id": task_id, "model": model, "tree": tree, **meta},
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--tasks", default=".*", help="regex sobre el task_id (p. ej. '^1012$')")
    parser.add_argument("--models", nargs="*", help="claude-opus-4.6, gemini-3.1-pro, gpt-5.4 (por defecto, todos)")
    parser.add_argument("--trees", nargs="*", default=["hack", "baseline", "non_hack"], choices=list(TREES))
    parser.add_argument("--max-tasks", type=int, default=None, help="tope de tareas (después del filtro)")
    parser.add_argument("--out", type=Path, default=DEFAULT_DATASET / "_eval")
    args = parser.parse_args()

    pattern = re.compile(args.tasks)
    task_dirs = sorted(d for d in (args.dataset / "tasks").iterdir() if d.is_dir() and pattern.search(d.name))
    if args.max_tasks:
        task_dirs = task_dirs[: args.max_tasks]

    samples = []
    for task_dir in task_dirs:
        for model_dir in sorted(d for d in task_dir.iterdir() if d.is_dir()):
            if args.models and model_dir.name not in args.models:
                continue
            for tree in args.trees:
                tree_dir = model_dir / TREES[tree]
                if not tree_dir.is_dir():
                    continue
                for traj_dir in sorted(tree_dir.iterdir()):
                    sample = convert_trajectory(traj_dir, task_dir.name, model_dir.name, tree)
                    if sample:
                        samples.append(sample)
    if not samples:
        raise SystemExit("No encontré trayectorias con esos filtros.")

    now = datetime.now(timezone.utc)
    models = sorted({s.metadata["model"] for s in samples})
    log = EvalLog(
        status="success",
        eval=EvalSpec(
            created=now.isoformat(),
            task="terminal-wrench",
            dataset=EvalDataset(name="terminal-wrench", samples=len(samples)),
            model=models[0] if len(models) == 1 else "varios: " + ", ".join(models),
            config=EvalConfig(),
            metadata={"tasks": args.tasks, "trees": args.trees, "models": models},
        ),
        results=EvalResults(total_samples=len(samples), completed_samples=len(samples)),
        samples=samples,
    )
    parts = [args.tasks if args.tasks != ".*" else "todas", "-".join(models), "-".join(args.trees)]
    slug = re.sub(r"[^A-Za-z0-9.]+", "-", "_".join(parts)).strip("-")[:80]
    out = args.out / f"{now:%Y-%m-%dT%H-%M-%S}_terminal-wrench_{slug}.eval"
    args.out.mkdir(parents=True, exist_ok=True)
    write_eval_log(log, str(out))
    print(f"{len(samples)} trayectorias de {len(task_dirs)} tareas -> {out}")


if __name__ == "__main__":
    main()
