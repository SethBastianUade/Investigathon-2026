from types import SimpleNamespace

import pytest

from records import provider_fixes
from records.provider_fixes import clean_tool_name, fix_completion

VALID = {"safe_bash", "safe_python", "text_editor"}


@pytest.fixture(autouse=True)
def tmp_log_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(provider_fixes, "LOG_DIR", tmp_path)
    return tmp_path


@pytest.mark.parametrize(
    "name, expected",
    [
        ("safe_bash", "safe_bash"),
        ("safe_python<|channel|>commentary", "safe_python"),
        ("text_editor<|channel|>commentary<|channel|>commentary", "text_editor"),
        # Si lo que queda no es una herramienta, no se toca: el rechazo es del modelo.
        ("submit<|channel|>commentary", "submit<|channel|>commentary"),
        ("apply_patch", "apply_patch"),
    ],
)
def test_clean_tool_name(name, expected):
    assert clean_tool_name(name, VALID) == expected


def _completion(*names):
    calls = [SimpleNamespace(function=SimpleNamespace(name=n)) for n in names]
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(tool_calls=calls))])


def test_fix_completion_renames_and_logs(tmp_log_dir):
    tools = [SimpleNamespace(name=n) for n in VALID]
    completion = _completion("safe_bash<|channel|>commentary", "text_editor")
    fix_completion(completion, tools)
    names = [c.function.name for c in completion.choices[0].message.tool_calls]
    assert names == ["safe_bash", "text_editor"]
    logs = list(tmp_log_dir.glob("provider_fixes_*.jsonl"))
    assert len(logs) == 1 and len(logs[0].read_text().splitlines()) == 1


def test_fix_completion_empty_choices_is_retryable():
    from inspect_ai.model._openai import OpenAIResponseError, openai_should_retry

    with pytest.raises(OpenAIResponseError) as exc:
        fix_completion(SimpleNamespace(choices=None, id="x"), [])
    assert openai_should_retry(exc.value)
