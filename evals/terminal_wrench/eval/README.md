# Terminal Wrench en formato Inspect (.eval)

Trayectorias del dataset [Terminal Wrench](https://github.com/few-sh/terminal-wrench) (arXiv 2604.17596), convertidas a logs de Inspect para poder verlas con `inspect view`. Hay un archivo por modelo: `claude-opus-4.6`, `gemini-3.1-pro` y `gpt-5.4`.

- **Origen:** `few-sh/terminal-wrench`, commit `d8a29613235a0ef56a8b70b3142626a533da28c2` (2026-04-18). Licencia Apache 2.0; la copia está en `LICENSE-terminal-wrench`.
- **Qué incluye:** todas las tareas, con los árboles `hack_trajectories`, `baseline_trajectories` y `non_hack_trajectories`. No incluye las variantes `sanitized` ni `stripped`, ni las tareas originales (`original_task/`).
- **Modificaciones:** cambia el formato, no el contenido. Cada trayectoria ATIF (`agent/trajectory.json`) se convirtió en una muestra de Inspect con `evals/terminal_wrench/tw_to_eval.py`:
  - cada paso del agente es un mensaje del asistente, con un `ToolCall` por comando;
  - la salida de la terminal va en el mensaje de usuario siguiente;
  - el puntaje es la clasificación del dataset (`rewarded_serious_exploit`, `rewarded_nonserious_hack`, `attacker_legitimate_solve`, `no_reward` o `baseline`), y `metadata.json` queda en la metadata de la muestra.
- **Ids de las muestras:** `tarea/modelo/árbol/etiqueta`, por ejemplo `1029/gpt-5.4/hack/v5_2`.

Para verlos, desde la raíz del repo:

```
inspect view --log-dir evals/terminal_wrench/eval
```

Para regenerarlos, con el dataset clonado en `terminal-wrench/`:

```
python evals/terminal_wrench/tw_to_eval.py --models gpt-5.4 --out evals/terminal_wrench/eval
```

Recordatorio de método: todos los hacks se obtuvieron con un prompt red-team, que está en el primer mensaje de cada trayectoria de ataque, y las clasificaciones vienen de un juez LLM.
