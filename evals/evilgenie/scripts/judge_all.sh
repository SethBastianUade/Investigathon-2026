#!/usr/bin/env bash
# Lanza el juez post-hoc (GLM-5.3 por NVIDIA) sobre varias corridas en paralelo, en el servidor.
# Cada corrida de 154 problemas se parte en 2 procesos (--shard). Lo ya juzgado no se repite.
# Uso, desde ~/investigathon/eg_team: scripts/judge_all.sh
# Necesita runs_judge/<run_id>/ con un enlace al .eval de cada corrida.
set -uo pipefail
cd ~/investigathon/eg_team
M=${JUDGE_MODEL:-openai-api/nvidia/z-ai/glm-5.3}
mkdir -p ~/investigathon/judge_logs

launch() {
  local log=~/investigathon/judge_logs/$1${2:+_${2/\//de}}.log
  setsid nohup ~/.local/bin/uv run --no-sync python -m records.judge_posthoc "runs_judge/$1" --model "$M" ${2:+--shard "$2"} \
    >> "$log" 2>&1 < /dev/null &
  disown
}

for r in run_154_oss20b_fix run_154_oss20b_fix_p2 run_154_oss20b run_154_oss20b_p2; do
  launch "$r" 0/2
  launch "$r" 1/2
done
for r in run_50_oss20b run_20_oss20b_fix run_05_oss20b run_05_oss20b_fix run_05_nemotron run_05_nemotron_t2 run_05_30b run_05 run_20_think_t3600; do
  launch "$r"
done
echo "lanzados $(date -u +%T)"
