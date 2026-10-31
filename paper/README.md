# Paper: sondeo del entorno y reward hacking

Esqueleto del paper sobre la investigación del Investigathon 2026 (2.º puesto, track Reward Hacking). Está en **inglés**, porque el destino principal es arXiv y LessWrong / Alignment Forum; la versión para Substack puede ser una adaptación en español.

## Archivos

```
paper/
├── main.tex              ← documento principal (incluye las secciones)
├── refs.bib              ← referencias; las de abajo del todo hay que verificarlas
├── sections/             ← una sección por archivo, para editar en paralelo
│   ├── 00_abstract.tex
│   ├── 01_introduction.tex
│   ├── 02_related_work.tex
│   ├── 03_method.tex
│   ├── 04_experimental_setup.tex
│   ├── 05_results.tex
│   ├── 06_human_validation.tex
│   ├── 07_limitations.tex
│   ├── 08_conclusion.tex
│   └── A_appendix.tex
└── figures/              ← figuras del repo (evals/terminal_wrench/results/)
```

## Cómo compilar

- **Overleaf** (lo más simple): subir la carpeta `paper/` completa como proyecto y compilar `main.tex`.
- **Local**: `latexmk -pdf main.tex` desde `paper/` (necesita una distribución de LaTeX, p. ej. MiKTeX en Windows).

Lo pendiente está marcado en rojo con `\todo{...}`. Antes de enviar, buscar `TODO` en todos los archivos.

## Qué falta antes de publicar

1. **Validación humana** (sección 6): completar las planillas de `evals/terminal_wrench/review/` y correr `review_commands.py matrix` y `review_sample.py matrix`.
2. **Clasificador**: corregir los dos errores de la auditoría de la tarea 1018 (`/dev/null` como archivo propio; comandos que la consigna pide literalmente) y regenerar `probing_todas.csv` y `robustness_todas.json`. Los números de las secciones 5 y 7 pueden cambiar un poco.
3. **Juez GLM**: sus resultados quedaron en la L4 (`runs_judge/`), que está apagada. Recuperarlos o volver a correr `scripts/judge_all.sh`, y revisar a mano cada `reward_hacking` y `heuristic`.
4. **Sondeo en EvilGenie**: correr `command_classifier` y `analyze_probing` sobre las corridas de gpt-oss con parche.
5. **Referencias**: verificar las marcadas en `refs.bib` y agregar trabajo relacionado.
6. **Autores y afiliación** en `main.tex`.
7. **Repo público**: antes de hacerlo público, escanear el historial de git en busca de claves.

## De dónde sale cada número

| Número | Fuente |
|---|---|
| 8.641 trayectorias, grupos, 309.656 partes, 6,4 % `?` | `evals/terminal_wrench/results/probing_todas.csv`, salida de `probing_tw.py` |
| Leyó el verificador (76 / 93 / 5 %, etc.) | `probing_todas.csv` (columna `n_S1`), figura `fig_matriz_s1` |
| Media por categoría y grupo | `fig_mapa_categorias`, `poster_figures.py` |
| AUC, largo controlado, test de signos | `results/robustness_todas.json`, `robustness_tw.py` |
| Efecto del parche (29–30 → 54–60, etc.) | `notas/corridas.md`, corridas `run_154_oss20b*` |
| 1 trampa en 333 intentos, `lcb_abc392_f` | `notas/corridas.md` ("Pasadas completas de gpt-oss-20b") |
| 0,2 % → 3,7 % (OpenAI) | Figura 2, p. 21 del informe técnico de OpenAI (lectura de la curva) |
| Citas textuales de OpenAI (pp. 20–22) | Informe técnico de OpenAI |

## Dónde publicar

1. **arXiv** (cs.AI o cs.LG): es lo que se cita. La primera vez hace falta un *endorsement* de alguien que ya publicó en esa categoría.
2. **LessWrong / Alignment Forum**: la comunidad de AI safety; ahí publicaron METR y Redwood su análisis del incidente.
3. **Substack**: versión corta y accesible, con link al preprint.
