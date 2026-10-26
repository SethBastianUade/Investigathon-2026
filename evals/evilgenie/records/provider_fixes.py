"""Correcciones de fallas del proveedor (no del modelo) para gpt-oss servido por NVIDIA.

1. Nombres de herramienta corruptos. NVIDIA deja pegado al nombre un token del formato
   harmony de gpt-oss (p. ej. "safe_python<|channel|>commentary"). Inspect no reconoce la
   herramienta y rechaza la llamada: en run_50_oss20b pasó con el 48 % de las llamadas. Acá
   se corta el nombre en el primer "<|", solo si lo que queda es una herramienta real.
2. Respuestas sin choices. NVIDIA a veces devuelve 200 sin choices y Inspect corta el
   problema con TypeError. Acá se convierte en OpenAIResponseError("server_error"), que
   Inspect reintenta (es lo mismo que hace Inspect con otras respuestas mal formadas).

Cada corrección queda en logs/provider_fixes_<EG_RUN_ID>.jsonl, para poder contarlas.
Los nombres válidos no tienen "<|", así que con otros proveedores no cambia nada.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from inspect_ai.model._openai import OpenAIResponseError
from inspect_ai.model._providers import openai_compatible

LOG_DIR = Path(__file__).parent.parent / "logs"
_lock = Lock()


def _log_fix(kind: str, **fields) -> None:
    run_id = os.environ.get("EG_RUN_ID", "sin_run_id")
    row = {"run_id": run_id, "at": datetime.now(timezone.utc).isoformat(), "kind": kind, **fields}
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with _lock, (LOG_DIR / f"provider_fixes_{run_id}.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def clean_tool_name(name: str, valid_names: set[str]) -> str:
    """Saca el sufijo harmony ("<|channel|>...") si lo que queda es una herramienta real."""
    if "<|" not in name:
        return name
    base = name.split("<|", 1)[0]
    return base if base in valid_names else name


def fix_completion(completion, tools) -> None:
    """Corrige la respuesta cruda antes de que Inspect la parsee."""
    if completion.choices is None:
        _log_fix("empty_choices", response_id=getattr(completion, "id", None))
        raise OpenAIResponseError("server_error", "Respuesta sin choices (falla del proveedor)")
    valid_names = {t.name for t in tools}
    for choice in completion.choices:
        for call in choice.message.tool_calls or []:
            fn = getattr(call, "function", None)
            if fn is None:
                continue
            cleaned = clean_tool_name(fn.name, valid_names)
            if cleaned != fn.name:
                _log_fix("tool_name", original=fn.name, cleaned=cleaned)
                fn.name = cleaned


def install() -> None:
    """Envuelve el parser de respuestas del proveedor OpenAI-compatible (idempotente)."""
    original = openai_compatible.chat_choices_from_openai
    if getattr(original, "_eg_provider_fix", False):
        return

    def patched(completion, tools, *args, **kwargs):
        fix_completion(completion, tools)
        return original(completion, tools, *args, **kwargs)

    patched._eg_provider_fix = True
    openai_compatible.chat_choices_from_openai = patched
