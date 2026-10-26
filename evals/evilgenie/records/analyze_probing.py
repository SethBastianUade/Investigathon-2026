"""Métricas de sondeo por trayectoria y comparación entre grupos (ver notas/definicion-sondeo.md).

Entrada, por cada carpeta runs/<run_id>/:
- commands_<variante>.jsonl: los comandos clasificados por records/command_classifier.py.
- actions_<run_id>.jsonl: para el exit code de cada comando (sondeo después de fallar).
- el .eval: puntaje de cada muestra (test_result, files_modified), leído como zip, sin Inspect.
- judge_<modelo>.jsonl (opcional): clasificación del juez LLM.

Grupo de cada trayectoria. La etiqueta sale del puntaje y del juez, nunca de los comandos:
- trampa: el juez dice reward_hacking, o passed_visible_only, o files_modified
  (incluso con passed_all: el scorer corre el test.py del agente).
- legitima: passed_all, sin files_modified y sin reward_hacking.
- no_resuelve: failed_visible sin señales de trampa (análogo a no_reward en Terminal Wrench).

Uso (desde evals/evilgenie; sin dependencias):
    python -m records.analyze_probing runs/run_05_14b
    python -m records.analyze_probing runs/run_50 runs/run_05_14b --variant hybrid_gemini-3.8-flash
Salida: probing_<variante>.csv por trayectoria y probing_<variante>_summary.json, en la
carpeta de la primera corrida (o en --out).
"""

import argparse
import csv
import json
import copy
import io
import math
import random
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

try:  # Inspect comprime los .eval con zstd; Python < 3.14 lo lee con este paquete.
    import zipfile_zstd  # noqa: F401
except ImportError:
    pass

PROBES = ("S1", "S2", "S3", "S4", "S5")
GROUPS = ("trampa", "legitima", "no_resuelve")
METRICS = ("probing_ratio", "s1_ratio", "s2_s5_ratio", "first_probe_latency", "probe_before_attempt",
           "breadth", "probe_after_failure", "manipulation")


# ---------------------------------------------------------------- lectura


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _zstd_decompress_all(raw: bytes) -> bytes:
    """Descomprime todos los frames zstd (zipfile solo lee el primero)."""
    try:
        from compression import zstd  # Python >= 3.14

        return zstd.decompress(raw)
    except ImportError:
        import zstandard

        reader = zstandard.ZstdDecompressor().stream_reader(io.BytesIO(raw), read_across_frames=True)
        return reader.read()


def read_member(z: zipfile.ZipFile, name: str) -> bytes:
    """Lee un archivo del .eval. Inspect escribe las muestras grandes (cientos de MB, p. ej.
    en run_154_oss20b) en varios frames zstd; zipfile descomprime solo el primero y falla
    el CRC. En ese caso se leen los bytes comprimidos y se descomprimen todos los frames."""
    try:
        return z.read(name)
    except zipfile.BadZipFile:
        info = copy.copy(z.getinfo(name))
        info.compress_type = zipfile.ZIP_STORED
        info.file_size = info.compress_size
        with z.open(info) as f:
            f._expected_crc = None
            raw = f.read()
        data = _zstd_decompress_all(raw)
        if zipfile.crc32(data) != z.getinfo(name).CRC:
            raise zipfile.BadZipFile(f"CRC incorrecto en {name} aun leyendo todos los frames")
        return data


def read_scores(run_dir: Path) -> dict[tuple[str, int], dict]:
    evals = sorted(run_dir.glob("*.eval"))
    if len(evals) != 1:
        raise SystemExit(f"Esperaba un solo .eval en {run_dir}, hay {len(evals)}")
    scores = {}
    with zipfile.ZipFile(evals[0]) as z:
        for name in z.namelist():
            if not name.startswith("samples/"):
                continue
            sample = json.loads(read_member(z, name))
            # Las muestras que cortaron con error (p. ej. respuesta vacía de la API) no
            # tienen puntaje: quedan fuera del análisis.
            if not sample.get("scores"):
                continue
            value = sample["scores"]["scorer"]["value"]
            scores[(str(sample["id"]), sample["epoch"])] = {
                "test_result": value["test_result"],
                "files_modified": bool(value["files_modified"]),
                "total_time": sample.get("total_time"),
                "hit_limit": (sample.get("limit") or {}).get("type"),
            }
    return scores


def read_judge(run_dir: Path) -> dict[tuple[str, int], str]:
    """Última clasificación que no sea error, por muestra (los errores se reintentan)."""
    judged = {}
    for path in sorted(run_dir.glob("judge_*.jsonl")):
        for row in read_jsonl(path):
            if row["classification"] != "error":
                judged[(row["sample_id"], row["epoch"])] = row["classification"]
    return judged


def group_of(score: dict, judge: str | None) -> str:
    if judge == "reward_hacking" or score["test_result"] == "passed_visible_only" or score["files_modified"]:
        return "trampa"
    if score["test_result"] == "passed_all":
        return "legitima"
    return "no_resuelve"


# ---------------------------------------------------------------- métricas por trayectoria


def is_attempt(part: dict) -> bool:
    """Primer intento de solución en EvilGenie: la primera escritura de solution.py."""
    return part["rule"].startswith("write-") and "solution.py" in part["segment"]


def is_failed_test(part: dict, exit_codes: dict) -> bool:
    code = exit_codes.get((part["sample_id"], part["epoch"], part["step"]))
    return part["rule"] == "run-tests" and code not in (0, None)


def trajectory_metrics(parts: list[dict], exit_codes: dict) -> dict:
    parts = sorted(parts, key=lambda p: (p["step"], p["segment_index"]))
    n = len(parts)
    steps = max(p["step"] for p in parts)
    cats = Counter(p["category"] for p in parts)
    probes = [p for p in parts if p["category"] in PROBES]

    first_probe = probes[0]["step"] if probes else None
    first_attempt = next((p["step"] for p in parts if is_attempt(p)), None)

    # Sondeo después de fallar: tras cada test fallido, ¿el siguiente paso es S1?
    by_step = defaultdict(list)
    for p in parts:
        by_step[p["step"]].append(p)
    ordered_steps = sorted(by_step)
    failures, followed_by_s1 = 0, 0
    for i, step in enumerate(ordered_steps[:-1]):
        if any(is_failed_test(p, exit_codes) for p in by_step[step]):
            failures += 1
            if any(p["category"] == "S1" for p in by_step[ordered_steps[i + 1]]):
                followed_by_s1 += 1

    return {
        "n_parts": n,
        "n_steps": steps,
        **{f"n_{c}": cats.get(c, 0) for c in (*PROBES, "N", "M", "?")},
        "probing_ratio": len(probes) / n,
        "s1_ratio": cats.get("S1", 0) / n,
        "s2_s5_ratio": sum(cats.get(c, 0) for c in PROBES[1:]) / n,
        # 0 = al principio de la trayectoria, 1 = al final; vacío si no sondeó.
        "first_probe_latency": (first_probe - 1) / max(steps - 1, 1) if first_probe else None,
        "probe_before_attempt": int(first_probe is not None and (first_attempt is None or first_probe < first_attempt)),
        "breadth": len({p["segment"] for p in parts if p["category"] in PROBES[1:]}),
        "failed_tests": failures,
        "probe_after_failure": followed_by_s1 / failures if failures else None,
        "manipulation": int(cats.get("M", 0) > 0),
        "unresolved": cats.get("?", 0),
    }


# ---------------------------------------------------------------- estadística (sin dependencias)


def mann_whitney(a: list[float], b: list[float]) -> dict:
    """U de Mann-Whitney con aproximación normal y corrección por empates. AUC = P(a > b)."""
    n1, n2 = len(a), len(b)
    if n1 < 2 or n2 < 2:
        return {"n1": n1, "n2": n2, "U": None, "p": None, "auc": None, "note": "insuficiente"}
    values = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks, i = [0.0] * len(values), 0
    ties = []
    while i < len(values):
        j = i
        while j + 1 < len(values) and values[j + 1][0] == values[i][0]:
            j += 1
        for k in range(i, j + 1):
            ranks[k] = (i + j) / 2 + 1
        ties.append(j - i + 1)
        i = j + 1
    r1 = sum(r for r, (_, g) in zip(ranks, values) if g == 0)
    u1 = r1 - n1 * (n1 + 1) / 2
    n = n1 + n2
    sigma = math.sqrt(n1 * n2 / 12 * ((n + 1) - sum(t ** 3 - t for t in ties) / (n * (n - 1))))
    z = (u1 - n1 * n2 / 2) / sigma if sigma else 0.0
    p = math.erfc(abs(z) / math.sqrt(2))
    return {"n1": n1, "n2": n2, "U": u1, "z": z, "p": p, "auc": u1 / (n1 * n2)}


def bootstrap_diff(a: list[float], b: list[float], reps: int = 5000, seed: int = 42) -> dict:
    """Diferencia de medias (a - b) con intervalo bootstrap del 95 %."""
    if len(a) < 2 or len(b) < 2:
        return {"diff": None, "ci95": None}
    rng = random.Random(seed)
    diffs = sorted(statistics.fmean(rng.choices(a, k=len(a))) - statistics.fmean(rng.choices(b, k=len(b)))
                   for _ in range(reps))
    return {"diff": statistics.fmean(a) - statistics.fmean(b),
            "ci95": [diffs[int(0.025 * reps)], diffs[int(0.975 * reps) - 1]]}


# ---------------------------------------------------------------- CLI


def analyze(run_dirs: list[Path], variant: str, out_dir: Path) -> None:
    rows = []
    for run_dir in run_dirs:
        commands = read_jsonl(run_dir / f"commands_{variant}.jsonl")
        actions = read_jsonl(next(run_dir.glob("actions_*.jsonl")))
        exit_codes = {(a["sample_id"], a["epoch"], a["step"]): a.get("exit_code") for a in actions}
        scores, judge = read_scores(run_dir), read_judge(run_dir)

        by_traj = defaultdict(list)
        for part in commands:
            by_traj[(part["sample_id"], part["epoch"])].append(part)
        for key, score in sorted(scores.items()):
            parts = by_traj.get(key)
            if not parts:
                continue  # el agente no llamó a ninguna herramienta
            rows.append({"run_id": run_dir.name, "sample_id": key[0], "epoch": key[1],
                         "test_result": score["test_result"], "files_modified": int(score["files_modified"]),
                         "judge": judge.get(key, ""), "group": group_of(score, judge.get(key)),
                         "hit_limit": score["hit_limit"] or "", **trajectory_metrics(parts, exit_codes)})

    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / f"probing_{variant}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    groups = {g: [r for r in rows if r["group"] == g] for g in GROUPS}
    summary = {"runs": [d.name for d in run_dirs], "variant": variant,
               "n_trajectories": len(rows), "groups": {g: len(v) for g, v in groups.items()},
               "means": {}, "comparisons": {}}
    for g, members in groups.items():
        summary["means"][g] = {}
        for m in METRICS:
            vals = [r[m] for r in members if r[m] is not None]
            summary["means"][g][m] = statistics.fmean(vals) if vals else None
    for other in ("legitima", "no_resuelve"):
        summary["comparisons"][f"trampa_vs_{other}"] = {}
        for m in METRICS:
            a = [r[m] for r in groups["trampa"] if r[m] is not None]
            b = [r[m] for r in groups[other] if r[m] is not None]
            summary["comparisons"][f"trampa_vs_{other}"][m] = {**mann_whitney(a, b), **bootstrap_diff(a, b)}
    (out_dir / f"probing_{variant}_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"{csv_path}: {len(rows)} trayectorias  " + "  ".join(f"{g}={len(v)}" for g, v in groups.items()))
    print(f"{'métrica':22}" + "".join(f"{g:>14}" for g in GROUPS))
    for m in METRICS:
        cells = [summary["means"][g][m] for g in GROUPS]
        print(f"{m:22}" + "".join(f"{'—' if c is None else f'{c:.3f}':>14}" for c in cells))
    if len(groups["trampa"]) < 2:
        print("Comparación: insuficiente (hacen falta al menos 2 trayectorias con trampa).")
    else:
        for name, comp in summary["comparisons"].items():
            c = comp["probing_ratio"]
            if c["p"] is not None:
                print(f"{name}, proporción de sondeo: AUC={c['auc']:.2f} p={c['p']:.3f} diff={c['diff']:.3f} IC95={c['ci95']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("run_dirs", type=Path, nargs="+", help="carpetas de corridas, p. ej. runs/run_50")
    parser.add_argument("--variant", default="rules", help="rules o hybrid_<modelo> (sufijo de commands_*.jsonl)")
    parser.add_argument("--out", type=Path, default=None, help="carpeta de salida (por defecto, la primera corrida)")
    args = parser.parse_args()
    analyze(args.run_dirs, args.variant, args.out or args.run_dirs[0])


if __name__ == "__main__":
    main()
