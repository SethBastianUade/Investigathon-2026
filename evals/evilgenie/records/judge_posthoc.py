"""Juez LLM post-hoc sobre corridas ya terminadas.

Las corridas se hacen con el juez apagado (-T enable_llm_judge=false). El scorer igual
guarda el solution.py final en score.answer, así que acá se juzga después, sin volver a
correr el agente. Se usa llm_judge_solution() de categorical_scorer tal cual (mismo
prompt, system message y reasoning_effort que el paper); solo cambia el modelo.

El juez ve el enunciado y el código final, no los comandos: la etiqueta de trampa es
independiente de las métricas de sondeo.

Uso (desde evals/evilgenie; la clave va en .env, que está gitignored):
    uv run python -m records.judge_posthoc runs/run_05_14b --model google/gemini-3.8-flash
Salida: runs/<run_id>/judge_<modelo>.jsonl, una fila por muestra. Si se corta, se puede
volver a correr y saltea las muestras ya juzgadas.
"""

import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from inspect_ai.log import read_eval_log
from inspect_ai.model import GenerateConfig

import categorical_scorer


def use_judge_model(model_name: str) -> None:
    """Hace que llm_judge_solution use model_name, conservando su GenerateConfig."""
    original_get_model = categorical_scorer.get_model

    def get_judge_model(*args, role=None, default=None, config=None, **kwargs):
        # Si el juez tarda más de 120 s, el scorer reintenta con reasoning_effort="minimal",
        # que Gemini 3.x no acepta; usamos el nivel más bajo que sí acepta.
        if config is not None and config.reasoning_effort == "minimal" and model_name.startswith("google/"):
            config = config.merge(GenerateConfig(reasoning_effort="low"))
        return original_get_model(model_name, config=config)

    categorical_scorer.get_model = get_judge_model


async def judge_run(run_dir: Path, model_name: str, limit: int | None) -> None:
    eval_files = sorted(run_dir.glob("*.eval"))
    if len(eval_files) != 1:
        raise SystemExit(f"Esperaba un solo .eval en {run_dir}, hay {len(eval_files)}")
    log = read_eval_log(str(eval_files[0]))

    out_path = run_dir / f"judge_{model_name.split('/')[-1]}.jsonl"
    done = set()
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            # Los errores (API caída, modelo inexistente) se reintentan.
            if row["classification"] != "error":
                done.add((row["sample_id"], row["epoch"]))

    samples = [s for s in log.samples or [] if (str(s.id), s.epoch) not in done]
    if limit is not None:
        samples = samples[:limit]

    for sample in samples:
        score = sample.scores["scorer"]
        classification, details = await categorical_scorer.llm_judge_solution(
            score.answer, sample.input
        )
        row = {
            "run_id": run_dir.name,
            "sample_id": str(sample.id),
            "epoch": sample.epoch,
            "judge_model": model_name,
            "judged_at": datetime.now(timezone.utc).isoformat(),
            "classification": classification,
            "test_result": score.value["test_result"],
            "files_modified": score.value["files_modified"],
            "details": details,
        }
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"{sample.id}: {classification} ({score.value['test_result']})")

    print(f"Listo: {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dir", type=Path, help="carpeta de la corrida, p. ej. runs/run_05_14b")
    parser.add_argument("--model", default="google/gemini-3.8-flash", help="modelo juez de Inspect")
    parser.add_argument("--limit", type=int, default=None, help="juzgar solo las primeras N muestras pendientes")
    args = parser.parse_args()

    load_dotenv(".env")
    use_judge_model(args.model)
    asyncio.run(judge_run(args.run_dir, args.model, args.limit))


if __name__ == "__main__":
    main()
