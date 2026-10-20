# Ideas de investigación y preguntas para el mentor

## Decisión tras la primera mentoría (19/10/2026)

El mentor indicó:
- **Pregunta principal:** ¿los reward hacks muestran más sondeo del entorno que las soluciones legítimas, medido solo con los comandos?
- **Pregunta secundaria:** ¿qué tienen en común los verificadores que se pudieron engañar? Se va respondiendo a medida que hagamos las evaluaciones de la pregunta 1, así que hay que **guardar todos los datos**: dataset, prompts, marcas de tiempo, etc.
- **Benchmark para las evaluaciones:** EvilGenie (Gabor et al. 2025), registrando los sondeos del sandbox.

Definición operativa y métricas: [`definicion-sondeo.md`](definicion-sondeo.md).

Notas de diseño que surgieron después:
- En Terminal Wrench todos los hacks se generaron con un prompt que ordena buscar debilidades del verificador. Para no confundir sondeo con obediencia, comparamos hacks contra soluciones legítimas *dentro* de las ejecuciones con ese prompt.
- En EvilGenie la trampa es espontánea, así que complementa a Terminal Wrench.
- En Terminal Wrench todos los verificadores fueron hackeados. Para la pregunta 2 haría falta un grupo de control con tareas no hackeadas de los benchmarks originales. Llevar esto a la próxima mentoría.

Recursos: GPU Tesla T4 (15 GB) compartida por la organización, con horario de apagado a coordinar.

---

*Lo que sigue es el material preparado antes de la mentoría. Se conserva como registro.*

Primera mentoría: lunes 19/10/2026. La presentación dura 4–5 minutos, así que conviene llevar una pregunta de investigación, una hipótesis y estas preguntas.

## Hallazgos del dataset

- **Todos los hacks fueron provocados a propósito.** A los modelos se les agregó un prompt de "Red Team QA Agent" ([`prompts/hack_prompt_v5.md`](https://github.com/few-sh/terminal-wrench/blob/main/prompts/hack_prompt_v5.md)) que les pedía hackear el verificador. El dataset muestra que los modelos *pueden* hacer trampa, no que lo hagan solos. En el incidente, en cambio, la conducta salió del entrenamiento.
- **Las comparaciones entre modelos tienen un sesgo.** Ante el prompt de hackeo, Gemini resolvió la tarea de forma legítima solo 38 veces; Claude, 1.027. Los modelos obedecen el pedido de hacer trampa de forma muy distinta.
- **Las etiquetas vienen de un juez LLM.** Tanto la clasificación (hack serio, no serio, legítimo, sin recompensa) como las categorías de trampa las asignó un modelo, no una persona.

## Terminal Wrench frente al incidente OpenAI → Hugging Face

| | Terminal Wrench | Incidente OpenAI/HF |
|---|---|---|
| ¿De dónde viene el hack? | Se lo pidieron con un prompt | Salió del entrenamiento (recompensas mal puestas) |
| ¿Dónde ocurre? | Dentro del sandbox (tests, binarios, archivos de respuestas) | Afuera: escapa del sandbox |
| ¿Cómo se detecta? | Un LLM juez lee la trayectoria: AUC 0.97 con razonamiento, 0.92 sin él | Se detectó una semana tarde |

Ninguna de las 11 categorías del paper cubre "escapar del entorno". La más cercana es `structural-extraction` (ir a buscar la respuesta donde no debería). Ese hueco puede ser el gancho de la investigación.

## Tres preguntas posibles (elegir una)

### 1. ¿Hay señales previas de escape en Terminal Wrench? (recomendada)
- Buscar en los comandos de las trayectorias si el agente explora fuera de su espacio de trabajo: `find /`, leer `/tests`, `curl`/`pip`, tocar `/usr/lib`.
- Comparar hacks contra soluciones legítimas (baselines).
- **Hipótesis:** los hacks exploran mucho más allá de lo que la tarea necesita, y eso se puede medir sin LLM.
- **Costo:** bajo. No gasta API, solo procesa JSON (`index/trajectories.json` y los `trajectory.json` de cada intento).

### 2. ¿Un monitor barato alcanza cuando el razonamiento no está?
- Correr `monitoring/monitor.py` con un juez chico (`gpt-5.4-nano`) sobre las versiones "stripped" (sin razonamiento).
- Compararlo con un clasificador simple sobre los comandos.
- **Conexión con el incidente:** se detectó tarde, y no siempre se puede leer el razonamiento.
- **Costo:** créditos de API. Conviene trabajar con una muestra.

### 3. Interpretabilidad (probes, SAE)
- Las trayectorias son de modelos cerrados. Solo se puede pasar ese texto por un modelo abierto y entrenar un probe sobre sus activaciones.
- **Limitación:** eso mide si el modelo abierto "reconoce" el hack, no lo que pensaba el modelo que hackeó.
- Es la más vistosa para el póster pero la más arriesgada en dos semanas.

**Recomendación:** hacer la 1 y, si sobra tiempo, agregar la 2. Es acotada, se puede hacer con el cómputo que tenemos y conecta directo con el incidente.

## Preguntas para el mentor

1. ¿Sirve comparar un dataset donde el hack se pidió por prompt con un incidente donde surgió del entrenamiento, o eso invalida la conexión?
2. ¿Conviene ir a monitoreo de comportamiento (lo que hace el agente) o a interpretabilidad, con el cómputo que tenemos?
3. ¿Hay presupuesto de API o GPU? ¿Cuántas trayectorias es razonable analizar?
4. ¿Podemos confiar en las etiquetas del juez LLM (categorías, clasificación) como verdad, o hay que validar una muestra a mano?
5. ¿Proponer una categoría nueva ("escape del entorno") cuenta como aporte, o es demasiado especulativo con una sola fuente pública del incidente?
6. Además de School of Reward Hacks, ¿qué bibliografía es imprescindible? Por ejemplo MacDiarmid et al. 2025 (ver [`bibliografia.md`](bibliografia.md)).
7. ¿El enfoque de seguridad de OpenAI (*deliberative alignment*) falló en el incidente o no aplicaba?

## Para el domingo

- [ ] Leer el informe técnico de OpenAI y el análisis de METR. Anotar qué acciones concretas hicieron los agentes.
- [ ] Instalar Python y sacar 2 o 3 números del índice de trayectorias (hacks por categoría y por modelo).
- [ ] Leer 3 o 4 `hack_summary.md`, por ejemplo `tasks/550`, `tasks/913` y `tasks/765` (el README del dataset los destaca).
- [ ] Armar 3 slides: la pregunta, la hipótesis y las preguntas para el mentor.
