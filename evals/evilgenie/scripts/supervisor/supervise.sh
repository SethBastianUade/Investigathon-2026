#!/usr/bin/env bash
# Supervisor de solo lectura: junta el estado y le pide a Kiro (headless, sin herramientas) un informe.
set -uo pipefail
D=~/investigathon/supervisor
export PATH="$HOME/.local/bin:$PATH"
export KIRO_API_KEY=$(cat ~/.config/kiro-supervisor/key)
cd "$D"
status=$("$D/collect_status.sh" 2>&1 | head -c 20000)
report=$( { cat "$D/prompt.md"; echo "$status"; } | timeout 600 kiro-cli chat --no-interactive 2>&1 | grep -v "ksk_")
{
  echo "==================== $(date -u +%FT%TZ) ===================="
  echo "$report"
  echo
} >> "$D/supervisor.log"
echo "$report" > "$D/latest.md"
echo "$status" > "$D/latest_status.txt"
