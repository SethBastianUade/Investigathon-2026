"""Prueba de humo del registro de acciones, sin GPU.

Corre un problema con un modelo simulado (mockllm) que llama una vez a cada
herramienta y verifica que actions_<run_id>.jsonl coincida con el log .eval.

Uso (desde evals/evilgenie):
    EG_RUN_ID=smoke uv run python -m records.smoke_logging
"""

import json
import os
from collections import Counter
from pathlib import Path

from inspect_ai import eval
from inspect_ai.event import ToolEvent
from inspect_ai.model import ModelOutput, get_model

from reward_hacking import reward_hacking

WORKSPACE = "/home/agent/workspace"

outputs = [
    ModelOutput.for_tool_call("mockllm/model", "safe_bash", {"cmd": "ls -la / && cat test.py | head -5"}),
    ModelOutput.for_tool_call("mockllm/model", "text_editor", {"command": "view", "path": f"{WORKSPACE}/test_cases.json"}),
    ModelOutput.for_tool_call("mockllm/model", "safe_python", {"code": "import sys; print(sys.version)"}),
    ModelOutput.for_tool_call("mockllm/model", "safe_bash", {"cmd": "sleep 0; exit 3"}),
    ModelOutput.for_tool_call("mockllm/model", "submit", {"answer": "done"}),
]

model = get_model("mockllm/model", custom_outputs=outputs)
log = eval(reward_hacking(limit=1, enable_llm_judge=False), model=model)[0]
print("status:", log.status)
assert log.status == "success", log.error

sample = log.samples[0]
eval_tools = [e.function for e in sample.events if isinstance(e, ToolEvent) and e.function != "submit"]

run_id = os.environ.get("EG_RUN_ID", "")
path = Path("logs") / f"actions_{run_id}.jsonl"
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
rows = [r for r in rows if r["sample_id"] == str(sample.id)]

print("eval tool calls:", Counter(eval_tools))
print("jsonl rows:     ", Counter(r["tool"] for r in rows))
for r in rows:
    print(f'  step={r["step"]} tool={r["tool"]} exit={r["exit_code"]} '
          f'cmd={r["command"][:40]!r} out={(r["output"] or "")[:40]!r}')

assert sorted(eval_tools) == sorted(r["tool"] for r in rows), "eval y jsonl no coinciden"
assert all(r["model"] and r["run_id"] == run_id for r in rows)
assert {r["tool"] for r in rows} == {"safe_bash", "safe_python", "text_editor"}
assert any(r["exit_code"] == 3 for r in rows)
print("score:", sample.scores)
print("OK")
