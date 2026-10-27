"""Controles de robustez del puntaje de sondeo en Terminal Wrench (sobre results/probing_todas.csv).

1. Misma tarea y mismo modelo: para cada par (tarea, modelo) con los dos grupos, se compara la
   mediana del puntaje; se cuenta en cuántos pares gana cada grupo y se aplica un test de signos.
   Así la dificultad de la tarea no puede explicar la diferencia.
2. Control por largo: AUC de Mann-Whitney dentro de cada decil de cantidad de comandos, y el
   promedio ponderado. Si la diferencia desaparece al comparar trayectorias de largo parecido,
   era de largo y no de sondeo.
3. Sensibilidad a los "?": se recalcula todo con los "?" como sondeo (cota alta) y como no
   sondeo (cota baja, que es el puntaje base). Si la conclusión se mantiene, no depende de ellos.
Comparaciones: hack vs. legítima (mismo prompt de ataque) y ataque vs. base (cualquier
trayectoria con el prompt vs. sin él), por modelo.

Uso, desde la raíz del repo:
    python evals/terminal_wrench/robustness_tw.py
Salida: results/robustness_todas.json y un resumen en pantalla.
"""

import csv
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "evals" / "evilgenie"))

from records.analyze_probing import mann_whitney  # noqa: E402

RESULTS = ROOT / "evals" / "terminal_wrench" / "results"
COMPARISONS = {
    "hack_vs_legitimate": ({"hack"}, {"legitimate"}),
    "ataque_vs_base": ({"hack", "legitimate", "no_reward"}, {"baseline"}),
}
VARIANTS = {
    "base": lambda r: r["probe_score"],
    "?_como_sondeo": lambda r: r["probe_score"] + r["n_unknown"],
}


def load() -> list[dict]:
    with (RESULTS / "probing_todas.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in ("probe_score", "n_unknown", "n_segments", "n_S1"):
            r[k] = int(r[k])
    return rows


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return (s[n // 2] + s[(n - 1) // 2]) / 2


def sign_test(wins: int, losses: int) -> float:
    """p bilateral exacto (binomial con p=0.5), sin contar empates."""
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def within_task(rows, pos, neg, value) -> dict:
    by_pair = defaultdict(lambda: ([], []))
    for r in rows:
        key = (r["task_id"], r["model"])
        if r["group"] in pos:
            by_pair[key][0].append(value(r))
        elif r["group"] in neg:
            by_pair[key][1].append(value(r))
    wins = losses = ties = 0
    for a, b in by_pair.values():
        if a and b:
            d = median(a) - median(b)
            wins += d > 0
            losses += d < 0
            ties += d == 0
    return {"pares": wins + losses + ties, "gana_primero": wins, "gana_segundo": losses, "empates": ties,
            "p_signos": sign_test(wins, losses)}


def length_controlled(rows, pos, neg, value, bins: int = 10) -> dict:
    sub = sorted((r for r in rows if r["group"] in pos | neg), key=lambda r: r["n_segments"])
    if not sub:
        return {}
    size = math.ceil(len(sub) / bins)
    aucs, weights = [], []
    for i in range(0, len(sub), size):
        chunk = sub[i:i + size]
        a = [value(r) for r in chunk if r["group"] in pos]
        b = [value(r) for r in chunk if r["group"] in neg]
        if len(a) >= 5 and len(b) >= 5:
            aucs.append(mann_whitney(a, b)["auc"])
            weights.append(min(len(a), len(b)))
    if not aucs:
        return {"auc_ponderado": None, "deciles_usados": 0}
    return {"auc_ponderado": sum(x * w for x, w in zip(aucs, weights)) / sum(weights), "deciles_usados": len(aucs),
            "auc_min": min(aucs), "auc_max": max(aucs)}


def main() -> None:
    rows = load()
    out = {}
    for model in sorted({r["model"] for r in rows}):
        mrows = [r for r in rows if r["model"] == model]
        out[model] = {}
        for comp, (pos, neg) in COMPARISONS.items():
            out[model][comp] = {}
            for vname, value in VARIANTS.items():
                a = [value(r) for r in mrows if r["group"] in pos]
                b = [value(r) for r in mrows if r["group"] in neg]
                out[model][comp][vname] = {
                    "auc_crudo": mann_whitney(a, b)["auc"] if len(a) > 1 and len(b) > 1 else None,
                    "misma_tarea": within_task(mrows, pos, neg, value),
                    "control_largo": length_controlled(mrows, pos, neg, value),
                }
    (RESULTS / "robustness_todas.json").write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("AUC > 0.5: el primer grupo sondea más. 'misma tarea' = pares tarea-modelo donde gana cada grupo (p de signos).")
    for model, comps in out.items():
        print(f"\n== {model}")
        for comp, variants in comps.items():
            for vname, res in variants.items():
                wt, lc = res["misma_tarea"], res["control_largo"]
                lc_txt = f"{lc['auc_ponderado']:.2f} [{lc['auc_min']:.2f}–{lc['auc_max']:.2f}]" if lc.get("auc_ponderado") is not None else "—"
                crude = f"{res['auc_crudo']:.2f}" if res["auc_crudo"] is not None else "—"
                print(f"  {comp:<19} {vname:<14} AUC crudo={crude}  largo controlado={lc_txt}  "
                      f"misma tarea: {wt['gana_primero']}/{wt['gana_segundo']}/{wt['empates']} (p={wt['p_signos']:.2g})")


if __name__ == "__main__":
    main()
