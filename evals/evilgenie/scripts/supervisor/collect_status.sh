#!/usr/bin/env bash
# Junta el estado de las corridas como texto. Solo lee; nunca toca .env ni las claves.
cd ~/investigathon/eg_team
echo "## Hora: $(date -u +%FT%TZ)"
echo "## Servidor"; uptime; free -h | sed -n 1,2p; df -h / | tail -1
nvidia-smi --query-gpu=memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null
echo "## Corridas de Inspect activas (modelo, límite)"
pgrep -af "[.]venv/bin/inspect eval reward_hacking.py" | grep -o "\-\-model [^ ]*\|limit=[0-9]*\|timeout_per_problem=[0-9]*" | paste -sd' ' | sed 's/--model /\n--model /g'
echo; echo "## Colas y controles (logs modificados en las últimas 24 h)"
for q in $(find ~/investigathon -maxdepth 1 \( -name "queue_*.log" -o -name "gate_*.log" \) -mmin -1440 | sort); do
  echo "### $(basename $q) | modificado $(date -u -r "$q" +%FT%TZ)"; tail -6 "$q"
done
echo "### Procesos de cola activos:"
# Solo scripts .sh: el patrón suelto también coincidía con hilos del kernel (pool_workqueue_release).
qp=$(pgrep -af "bash .*/([q]ueue_|[g]ate_)[^ ]*[.]sh" | sed 's/^[0-9]* //' | cut -c1-80)
echo "${qp:-ninguno}"
echo "## Corridas (archivos .out de las últimas 24 h)"
for o in $(find ~/investigathon -maxdepth 1 -name "run_*.out" -mmin -1440 | sort); do
  r=$(basename "$o" .out); a=logs/actions_$r.jsonl
  done_flag=$(grep -aq "Log: logs/" "$o" && echo "TERMINADA" || echo "sin terminar")
  echo "### $r: $done_flag | modificado $(date -u -r "$o" +%FT%TZ) | 429=$(grep -ac '429' "$o") errores=$(grep -aci 'traceback\|error:' "$o")"
  [ -f "$a" ] && python3 - "$a" <<'P'
import json, sys, datetime
rows = [json.loads(l) for l in open(sys.argv[1])]
ids = list(dict.fromkeys(r["sample_id"] for r in rows))
last = rows[-1]["started_at"]
age = (datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(last)).total_seconds() / 60
print(f"  problemas iniciados {len(ids)} | llamadas {len(rows)} | comandos {sum(r['tool'] != 'text_editor' for r in rows)} | última acción hace {age:.0f} min")
P
  grep -a "^Steps:" "$o" | tail -1 | sed 's/  */ /g'
  sed -n '/total time/,/Log:/p' "$o" | grep -a "total time\|passed_all\|passed_visible_only\|failed_visible\|files_modified\|WARNING" | sed 's/  */ /g' 
done
if pgrep -x ollama >/dev/null; then
  echo "## Últimos errores de Ollama"; grep -i "error\|panic\|out of memory" ~/investigathon/ollama.log | tail -3
else
  echo "## Ollama: apagado (a propósito)"
fi
