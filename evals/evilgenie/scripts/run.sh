#!/usr/bin/env bash
# Lanza una corrida de EvilGenie en segundo plano (en el servidor GPU).
# Uso, desde ~/investigathon/eg_team:
#   scripts/run.sh <run_id> <modelo> <limite> [args extra de inspect]
#   scripts/run.sh run_05_14b qwen3:14b 5
# La salida queda en ~/investigathon/<run_id>.out y las acciones en logs/actions_<run_id>.jsonl.
# Configuración fija entre etapas (ver notas/corridas.md): sin razonamiento, juez LLM
# apagado, 600 s por problema, un problema a la vez.
# THINK=1 deja el razonamiento del modelo encendido (comparación con/sin thinking):
#   THINK=1 scripts/run.sh run_50_think qwen3:14b 50
# Un modelo con proveedor explícito no usa la GPU y puede correr en paralelo con Ollama:
#   THINK=1 scripts/run.sh run_05_oss20b openai-api/nvidia/openai/gpt-oss-20b 5 --reasoning-effort medium
set -euo pipefail

reasoning=(--reasoning-effort none)
if [ "${THINK:-0}" = "1" ]; then
  reasoning=()
fi

run_id=${1:?falta run_id}
model=${2:?falta modelo, p. ej. qwen3:14b}
limit=${3:?falta limite de problemas}
shift 3

# "qwen3:14b" -> Ollama local; "openai-api/nvidia/..." u otro proveedor -> tal cual.
case "$model" in
  */*) model_id="$model" ;;
  *) model_id="ollama/$model" ;;
esac

if [[ "$model_id" == ollama/* ]] && pgrep -f "[i]nspect eval reward_hacking.py --model ollama/" >/dev/null; then
  echo "Ya hay una corrida de Ollama en curso; atiende un pedido a la vez." >&2
  exit 1
fi
if [ -e "logs/actions_${run_id}.jsonl" ]; then
  echo "Ya existe logs/actions_${run_id}.jsonl; elegí otro run_id." >&2
  exit 1
fi

EG_RUN_ID="$run_id" nohup ~/.local/bin/uv run inspect eval reward_hacking.py \
  --model "$model_id" ${reasoning[@]+"${reasoning[@]}"} \
  -T enable_llm_judge=false -T limit="$limit" --max-samples 1 --display plain "$@" \
  > ~/investigathon/"${run_id}".out 2>&1 < /dev/null &
echo "run ${run_id} pid $! think=${THINK:-0} $(date -u +%FT%TZ)"
