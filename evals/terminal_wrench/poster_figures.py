"""Figuras del póster a partir de results/probing_todas.csv.

- fig_matriz_s1: % de trayectorias que leyeron o buscaron el verificador (al menos un S1),
  por modelo y grupo. Es la matriz principal de la página de Notion.
- fig_mapa_categorias: media de comandos por trayectoria en cada categoría de sondeo × grupo
  (los tres modelos juntos, como en Notion).

Uso (desde la raíz del repo): python evals/terminal_wrench/poster_figures.py
Salida: PNG a 150 dpi (límite de la imprenta) y PDF vectorial en results/.
"""

import csv
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
RESULTS = HERE / "results"
MODELS = {"claude-opus-4.6": "Claude Opus 4.6", "gpt-5.4": "GPT-5.4", "gemini-3.1-pro": "Gemini 3.1 Pro"}
GROUPS = {"hack": "Hack", "legitimate": "Legítima\n(mismo prompt)", "baseline": "Base\n(sin prompt)"}
HEAT_GROUPS = {"baseline": "Base", "hack": "Hack", "legitimate": "Legítima", "no_reward": "Sin recompensa"}
CATS = ("S1", "S2", "S3", "S4", "S5", "M")
# Paleta categórica validada (dataviz, slots 1–3) y rampa azul secuencial.
COLORS = {"hack": "#eb6834", "legitimate": "#2a78d6", "baseline": "#8a8984"}
INK, INK2 = "#0b0b0b", "#52514e"

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 13, "axes.edgecolor": INK2,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2})


def load() -> list[dict]:
    with open(RESULTS / "probing_todas.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save(fig, name: str) -> None:
    for ext in ("png", "pdf"):
        fig.savefig(RESULTS / f"{name}.{ext}", dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def matriz_s1(rows: list[dict]) -> dict:
    counts = defaultdict(lambda: [0, 0])  # (modelo, grupo) -> [con S1, total]
    for r in rows:
        if r["group"] in GROUPS:
            c = counts[(r["model"], r["group"])]
            c[0] += int(r["n_S1"]) > 0
            c[1] += 1
    fig, ax = plt.subplots(figsize=(11, 5.5))
    width = 0.26
    for j, g in enumerate(GROUPS):
        xs = [i + (j - 1) * width for i in range(len(MODELS))]
        pct = [100 * counts[(m, g)][0] / counts[(m, g)][1] for m in MODELS]
        ax.bar(xs, pct, width - 0.02, color=COLORS[g], label=GROUPS[g].replace("\n", " "))
        for x, p, m in zip(xs, pct, MODELS):
            ax.text(x, p + 1.5, f"{p:.0f} %", ha="center", va="bottom", color=INK, fontsize=12)
            ax.text(x, -4, f"n={counts[(m, g)][1]}", ha="center", va="top", color=INK2, fontsize=9)
    ax.set_xticks(range(len(MODELS)), MODELS.values(), fontsize=14)
    ax.tick_params(axis="x", pad=26, length=0)
    ax.set_ylim(0, 105)
    ax.set_ylabel("% de trayectorias que leyeron el verificador")
    ax.spines[["top", "right"]].set_visible(False)
    ax.yaxis.grid(True, color="#e4e3df")
    ax.set_axisbelow(True)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.12))
    save(fig, "fig_matriz_s1")
    return {f"{m}/{g}": c for (m, g), c in counts.items()}


def mapa_categorias(rows: list[dict]) -> dict:
    sums, n = defaultdict(float), defaultdict(int)
    for r in rows:
        if r["group"] in HEAT_GROUPS:
            n[r["group"]] += 1
            for c in CATS:
                sums[(r["group"], c)] += int(r[f"n_{c}"])
    data = [[sums[(g, c)] / n[g] for c in CATS] for g in HEAT_GROUPS]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    im = ax.imshow(data, cmap="Blues", vmin=0, vmax=max(map(max, data)) * 1.15, aspect="auto")
    for i, row in enumerate(data):
        for j, v in enumerate(row):
            ax.text(j, i, f"{v:.2f}".replace(".", ","), ha="center", va="center",
                    color="white" if v > 1.6 else INK, fontsize=13)
    ax.set_xticks(range(len(CATS)), ["S1\nverificador", "S2\nfuera de alcance", "S3\nsistema",
                                     "S4\nejecución", "S5\nexterior", "M\nmanipulación"], fontsize=11)
    ax.set_yticks(range(len(HEAT_GROUPS)), HEAT_GROUPS.values())
    ax.tick_params(length=0)
    ax.axvline(len(CATS) - 1.5, color="white", lw=4)  # M se mide aparte del puntaje
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="comandos por trayectoria")
    save(fig, "fig_mapa_categorias")
    return {g: [round(v, 2) for v in row] for g, row in zip(HEAT_GROUPS, data)}


if __name__ == "__main__":
    rows = load()
    s1 = matriz_s1(rows)
    heat = mapa_categorias(rows)
    # Chequeo contra los números publicados en Notion.
    assert s1["claude-opus-4.6/hack"] == [855, 1119] and s1["gpt-5.4/baseline"] == [95, 754], s1
    assert heat["hack"][:2] == [1.04, 1.53] and heat["legitimate"][5] == 0.21, heat
    print("OK:", s1, heat, sep="\n")
