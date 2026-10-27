#!/usr/bin/env bash
# Baja los logs de una corrida terminada a runs/<run_id>/ (se corre en la PC, no en el servidor).
# Uso, desde la raíz del repo:
#   evals/evilgenie/scripts/fetch_run.sh <run_id>
# Necesita la clave del equipo en SSH/ (gitignored).
# Por defecto baja del servidor nuevo (L4, clave en SSH/SSH-2/). Para las corridas que
# quedaron en la T4 vieja: EG_SERVER=t4 evals/evilgenie/scripts/fetch_run.sh <run_id>
set -euo pipefail

run_id=${1:?falta run_id}
root=$(cd "$(dirname "$0")/../../.." && pwd)
dest="$root/evals/evilgenie/runs/$run_id"
if [ "${EG_SERVER:-l4}" = "t4" ]; then
  keydir="$root/SSH"; host=ubuntu@3.20.176.109
else
  keydir="$root/SSH/SSH-2"; host=ubuntu@18.190.107.33
fi
ssh_opts=(-o UserKnownHostsFile="$keydir/known_hosts" -o StrictHostKeyChecking=yes -i "$keydir/investigathon-gpu.key")

# El .out termina con "Log: logs/<archivo>.eval" cuando la corrida terminó.
eval_rel=$(ssh "${ssh_opts[@]}" "$host" "grep -a -o 'logs/[^ ]*\.eval' ~/investigathon/${run_id}.out | tail -1") || true
if [ -z "$eval_rel" ]; then
  echo "No encontré el .eval en ~/investigathon/${run_id}.out; ¿terminó la corrida?" >&2
  exit 1
fi

mkdir -p "$dest"
scp -q "${ssh_opts[@]}" \
  "$host:investigathon/eg_team/$eval_rel" \
  "$host:investigathon/eg_team/logs/actions_${run_id}.jsonl" \
  "$host:investigathon/${run_id}.out" \
  "$dest/"
ls -la "$dest"
