# Investigathon 2026 — Reward Hacking

Proyecto para el track de **Reward Hacking** de Investigathon 2026 (Y-Hat). La idea es tomar el paper *Terminal Wrench* como base y contrastarlo con el incidente en que agentes de OpenAI hackearon Hugging Face (2026).

## Contenido

- `Material-Papers/`:
  - `Reward Hacking-Investigathon.pdf` / `.txt`: consigna del track, con los criterios de evaluación.
  - `paper-Terminal Wrench.pdf` / `.md`: paper de Terminal Wrench ([arXiv:2604.17596](https://arxiv.org/abs/2604.17596)) y su versión en Markdown.
  - `EvilGenie Benchmark reward hacking.pdf` / `.md`: paper de EvilGenie ([arXiv:2511.21654](https://arxiv.org/abs/2511.21654)), el benchmark que usamos para las evaluaciones.
- `notas/definicion-sondeo.md`: definición operativa de "sondeo" y métricas por trayectoria.
- `notas/bibliografia.md`: análisis de las referencias del paper y bibliografía que falta.
- `notas/ideas-y-preguntas-mentor.md`: preguntas de investigación posibles, preguntas para el mentor y tareas pendientes.
- `CLAUDE.md`: contexto del proyecto y del dataset para Claude Code.

## Dataset

El dataset **no está incluido** en este repo. Hay que clonarlo dentro de la carpeta del proyecto:

```
git clone https://github.com/few-sh/terminal-wrench.git
```

Este repo ignora la carpeta `terminal-wrench/`.
