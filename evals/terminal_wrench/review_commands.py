"""Validación humana del clasificador de sondeo, comando por comando (Terminal Wrench).

Muestra estratificada por la categoría que puso el clasificador (25 de cada S1–S5, 20 M, 55 N;
semilla 42). Cada parte de comando la etiquetan 2 de los 3 revisores, rotando pares. Ciega: el
revisor ve el comando, el anterior, el directorio de trabajo y la consigna, pero no la etiqueta
del clasificador ni si la trayectoria fue hack. La clave se regenera con la semilla.

Uso, desde la raíz del repo (necesita results/segments_todas.jsonl, que genera probing_tw.py):
    python evals/terminal_wrench/review_commands.py sample
    python evals/terminal_wrench/review_commands.py matrix
Planillas: evals/terminal_wrench/review/comandos/revisor_<nombre>.csv (columna categoria:
S1, S2, S3, S4, S5, N, M o ?). Las consignas de las tareas de la muestra, en consignas.md.
"""

import argparse
import csv
import json
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from review_sample import DELIM, kappa  # noqa: E402

SEGMENTS = ROOT / "evals" / "terminal_wrench" / "results" / "segments_todas.jsonl"
DATASET = ROOT / "terminal-wrench"
OUT = ROOT / "evals" / "terminal_wrench" / "review" / "comandos"
STRATA = {"S1": 25, "S2": 25, "S3": 25, "S4": 25, "S5": 25, "M": 20, "N": 55}
CATS = ("S1", "S2", "S3", "S4", "S5", "N", "M", "?")
PROBE = {"S1", "S2", "S3", "S4", "S5"}


def draw_sample(seed: int, reviewers: list[str]) -> list[dict]:
    rng = random.Random(seed)
    by_cat, prev = defaultdict(list), {}
    with SEGMENTS.open(encoding="utf-8") as f:
        for line in f:
            r = json.loads(line)
            r["prev"] = prev.get(r["trajectory"], "")
            prev[r["trajectory"]] = r["segment"]
            if r["category"] in STRATA and len(r["segment"].strip()) > 1:
                by_cat[r["category"]].append(r)
    picked = []
    for cat, n in STRATA.items():
        picked += rng.sample(by_cat[cat], n)
    rng.shuffle(picked)
    pairs = [(reviewers[i], reviewers[(i + 1) % 3]) for i in range(3)]
    return [{"review_id": f"C{i + 1:03d}", "reviewers": pairs[i % 3], **r} for i, r in enumerate(picked)]


def pretty(segment: str) -> str:
    """Deshace las comillas que agrega shlex a los operadores: 2 '>' /dev/null -> 2> /dev/null."""
    segment = re.sub(r"'(>>?|<<?|>&|&>|\|)'", r"\1", segment)
    return re.sub(r"\b([12]) (>&?)", r"\1\2", segment)


def raw_step(trajectory: str, step: int) -> str:
    """Lo que tipeó el agente en ese paso, completo (incluye los cuerpos de los heredoc)."""
    from probing_tw import TREES, read_json

    task_id, model, tree, label = trajectory.split("/")
    steps = read_json(DATASET / "tasks" / task_id / model / TREES[tree] / label / "trial" / "agent" / "trajectory.json")["steps"]
    agent_steps = [s for s in steps if s.get("source") == "agent"]
    calls = agent_steps[step - 1].get("tool_calls") or [] if 0 < step <= len(agent_steps) else []
    return "".join((c.get("arguments") or {}).get("keystrokes", "") for c in calls).strip()


def scope_info(trajectory: str) -> tuple[str, str]:
    from probing_tw import build_scope

    task_id, model = trajectory.split("/")[:2]
    model_dir = DATASET / "tasks" / task_id / model
    instruction = model_dir / "original_task" / "instruction.md"
    return build_scope(model_dir).workspace, instruction.read_text(encoding="utf-8") if instruction.exists() else ""


def cmd_sample(args) -> None:
    sample = draw_sample(args.seed, args.reviewers)
    OUT.mkdir(parents=True, exist_ok=True)
    for name in args.reviewers:
        if (OUT / f"revisor_{name}.csv").exists() and not args.force:
            raise SystemExit(f"revisor_{name}.csv ya existe (puede tener respuestas). Usá --force para pisarlo.")
    info = {}
    for s in sample:
        if s["trajectory"] not in info:
            info[s["trajectory"]] = scope_info(s["trajectory"])
    tasks = {}
    for s in sample:
        task_id = s["trajectory"].split("/")[0]
        tasks.setdefault(task_id, info[s["trajectory"]][1])
    for name in args.reviewers:
        mine = sorted((s for s in sample if name in s["reviewers"]), key=lambda s: s["review_id"])
        with (OUT / f"revisor_{name}.csv").open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=DELIM)
            w.writerow(["review_id", "tarea", "directorio_de_trabajo", "comando_anterior", "comando_a_etiquetar",
                        "linea_original_del_paso", "categoria", "nota"])
            for s in mine:
                w.writerow([s["review_id"], s["trajectory"].split("/")[0], info[s["trajectory"]][0],
                            pretty(s["prev"])[:300], pretty(s["segment"])[:500], raw_step(s["trajectory"], s["step"])[:1500], "", ""])
        print(f"comandos/revisor_{name}.csv: {len(mine)} comandos")
    with (OUT / "consignas.md").open("w", encoding="utf-8") as f:
        f.write("# Consignas de las tareas de la muestra\n\nBuscá la tarea por su id (columna `tarea`).\n")
        for task_id in sorted(tasks, key=lambda t: (len(t), t)):
            f.write(f"\n## Tarea {task_id}\n\n{tasks[task_id].strip()}\n")
    with (OUT / "resolucion.csv").open("w", encoding="utf-8-sig", newline="") as f:
        csv.writer(f, delimiter=DELIM).writerow(["review_id", "categoria", "nota"])
    print(f"{len(sample)} comandos de {len(tasks)} tareas -> {OUT}")


def read_labels(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8-sig")
    delim = ";" if text.count(";") >= text.count(",") else ","
    out = {}
    for row in csv.DictReader(text.splitlines(), delimiter=delim):
        v = (row.get("categoria") or "").strip().upper()
        if v in CATS:
            out[row["review_id"].strip()] = v
    return out


def multi_kappa(a: list[str], b: list[str]) -> float | None:
    n = len(a)
    if not n:
        return None
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in CATS)
    return (po - pe) / (1 - pe) if pe < 1 else None


def cmd_matrix(args) -> None:
    sample = draw_sample(args.seed, args.reviewers)
    labels = {n: read_labels(OUT / f"revisor_{n}.csv") for n in args.reviewers}
    resolved = read_labels(OUT / "resolucion.csv")
    for i, a in enumerate(args.reviewers):
        for b in args.reviewers[i + 1:]:
            ids = [s["review_id"] for s in sample if {a, b} == set(s["reviewers"]) and s["review_id"] in labels[a] and s["review_id"] in labels[b]]
            k = multi_kappa([labels[a][r] for r in ids], [labels[b][r] for r in ids])
            kb = kappa(["si" if labels[a][r] in PROBE else "no" for r in ids], ["si" if labels[b][r] in PROBE else "no" for r in ids])
            print(f"kappa {a}-{b}: 8 categorías={'—' if k is None else f'{k:.2f}'}  sondeo sí/no={'—' if kb is None else f'{kb:.2f}'} (n={len(ids)})")

    done, pending, disagree = [], 0, []
    for s in sample:
        votes = [labels[r].get(s["review_id"]) for r in s["reviewers"]]
        if None in votes:
            pending += 1
        elif votes[0] == votes[1]:
            done.append((s, votes[0]))
        elif s["review_id"] in resolved:
            done.append((s, resolved[s["review_id"]]))
        else:
            disagree.append(s["review_id"])
    print(f"\ncompletos {len(done)} | faltan {pending} | desacuerdos sin resolver {len(disagree)}")
    if disagree:
        print("  resolver en comandos/resolucion.csv:", " ".join(disagree))
    if not done:
        return

    print("\nMatriz clasificador (filas) × humanos (columnas)")
    m = Counter((s["category"], h) for s, h in done)
    print("        " + "".join(f"{c:>5}" for c in CATS))
    for rc in STRATA:
        print(f"  {rc:<5} " + "".join(f"{m[(rc, hc)]:>5}" for hc in CATS))
    print("\nPrecisión por categoría del clasificador (humanos coinciden / total):")
    for rc in STRATA:
        tot = sum(m[(rc, hc)] for hc in CATS)
        if tot:
            print(f"  {rc}: {m[(rc, rc)]}/{tot} = {m[(rc, rc)] / tot:.0%}")
    tp = sum(1 for s, h in done if s["category"] in PROBE and h in PROBE)
    fp = sum(1 for s, h in done if s["category"] in PROBE and h not in PROBE)
    fn = sum(1 for s, h in done if s["category"] not in PROBE and h in PROBE)
    tn = sum(1 for s, h in done if s["category"] not in PROBE and h not in PROBE)
    print(f"\nSondeo sí/no — clasificador × humanos: VP={tp} FP={fp} FN={fn} VN={tn}")
    if tp + fp:
        print(f"  precisión={tp / (tp + fp):.2f}", end="")
    if tp + fn:
        print(f"  sensibilidad={tp / (tp + fn):.2f}", end="")
    print("\n  (la muestra está estratificada: la sensibilidad no es la del dataset completo, donde N es el 76 %)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("command", choices=["sample", "matrix"])
    parser.add_argument("--reviewers", nargs=3, default=["A", "B", "C"])
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    {"sample": cmd_sample, "matrix": cmd_matrix}[args.command](args)


if __name__ == "__main__":
    main()
