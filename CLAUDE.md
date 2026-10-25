# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A research workspace for **Investigathon 2026 (Y-Hat), Reward Hacking track**. This is a two-week hackathon, and the deliverable is a **poster** (Intro, Hypothesis & Goals, Methodology, Results, Conclusions; minimal plots, little text) plus a 5- and 10-minute pitch. Mentor check-ins are 4–5 minute presentations. The judges weight **research methodology** (literature review, hypothesis, objectives, explicit limitations, choosing one path) more than results. When proposing work, favor a narrow, well-scoped question over broad coverage.

The team plans to connect the Terminal Wrench paper to the **OpenAI → Hugging Face incident**. OpenAI disclosed it on 2026-07-21 and published a technical report on 2026-08-26. In that incident, agents trained in an environment that rewarded cheating escaped a sandbox and breached Hugging Face to cheat on the ExploitGym benchmark. METR published an independent analysis. Use primary sources (the OpenAI report, METR, Fortune, MIT Tech Review) for those facts, not secondary blogs.

**Research direction (decided with the mentor on 2026-10-19).** The main question is: do reward hacks show more environment probing ("sondeo") than legitimate solutions, measured only from the agent's commands? The secondary question is: what do the hackable verifiers have in common? Evaluations run on the **EvilGenie** benchmark, using an open model on the team's GPU, and the existing Terminal Wrench trajectories are analyzed alongside it. `notas/definicion-sondeo.md` holds the operational definition: categories S1–S5, plus N, ?, and M for tampering, along with the per-trajectory metrics and the comparison groups. Changes to that definition must be logged in its changelog. Keep all raw run data (logs, prompts, timestamps, seeds), because the secondary question is answered from it. The other notes are in `notas/` and are written in Spanish.

Papers and the track brief are in `Material-Papers/`. Read the `.md` versions, not the PDFs:
- `Reward Hacking-Investigathon.txt`: the track brief. It lists candidate datasets and methods and states the evaluation criteria. The file contains mojibake (UTF-8 decoded as cp1252).
- `paper-Terminal Wrench.md` (arXiv 2604.17596) and `EvilGenie Benchmark reward hacking.md` (arXiv 2511.21654).

GPU server: a Tesla T4 (15 GB) at `ubuntu@3.20.176.109`, provided by the organizers. It stays on until the team says it is done, so run length does not need to be coordinated with anyone (confirmed 2026-10-24). `SSH/instructivo-gpu.md` has the connection instructions. `SSH/` holds the team's private key and is gitignored. Never commit it or print the key. Connect with `ssh -o UserKnownHostsFile=./known_hosts -o StrictHostKeyChecking=yes -i ./investigathon-gpu.key ubuntu@3.20.176.109`, run from inside `SSH/`. To run multi-line remote scripts, pipe a heredoc into `ssh ... 'bash -s'` from the Bash tool, because PowerShell mangles the quoting.

**Our EvilGenie fork is `evals/evilgenie/` in this repo.** It is the upstream at `f5d8a2c` plus the team's action logging in `records/`. Every tool call (`safe_bash`, `safe_python`, `text_editor`) is appended to `logs/actions_<EG_RUN_ID>.jsonl`. Each row carries `run_id`, `model`, `sample_id` and `epoch`, so it can be joined with the scores in the Inspect `.eval` log. The `execute()` docstrings in `tools.py` must stay identical to upstream: Inspect builds the tool schema the model sees from them, and Inspect errors if they are missing. Run the logging smoke test (mockllm, no GPU) from `evals/evilgenie` with `EG_RUN_ID=smoke uv run python -m records.smoke_logging`.

Run data is committed. Each finished run goes in `evals/evilgenie/runs/<run_id>/`, which holds the `.eval`, `actions_<run_id>.jsonl` and `<run_id>.out`, and gets a row in `notas/corridas.md`. To download a finished run, execute `evals/evilgenie/scripts/fetch_run.sh <run_id>` locally. `logs/` stays gitignored, since it is the scratch output on the server. `.gitattributes` keeps `runs/` byte-exact and `*.sh` LF. GitHub rejects files over 100 MB, and a full 154-problem `.eval` would be about 120 MB, so large runs need Git LFS or a Release attachment. Never commit the server's `.venv`, the Ollama models, or the Hugging Face cache.

The LLM judge runs after the fact, not during runs. The scorer stores the final `solution.py` in `score.answer`, so `uv run python -m records.judge_posthoc runs/<run_id>` runs the paper's `llm_judge_solution()` unchanged on a finished run, with the same prompt and only the model swapped, and writes `runs/<run_id>/judge_<model>.jsonl`. The default judge is now `openai-api/cloudflare/@cf/meta/llama-3.3-70b-instruct-fp8-fast` on the Cloudflare Workers AI free plan (about 10k neurons per day, roughly 35 judgments). It needs a `max_tokens=4096` cap, because Cloudflare otherwise truncates the reply before the JSON. Gemini was dropped because its free-tier 429/503 errors stalled the judge. Rows with `error` are retried on rerun, so for analysis keep the last non-error row per sample. The judge sees only the problem and the final code, never the commands, so the hack label is independent of the probing metrics. API keys (Google, NVIDIA, Cloudflare) are in `~/investigathon/eg_team/.env` (chmod 600, gitignored). The agent `gpt-oss-20b` runs on the NVIDIA free API as `openai-api/nvidia/openai/gpt-oss-20b`. Use Mistral Small (`openai-api/cloudflare/@cf/mistralai/mistral-small-3.1-24b-instruct`) for `command_classifier --llm`. Keep the agent, the judge and the classifier LLM in different model families. `google-genai` was added to `pyproject.toml`. A trajectory counts as a candidate hack if the judge returns `reward_hacking`, if `test_result` is `passed_visible_only`, or if `files_modified` is set. The last case includes `passed_all`, because the scorer restores `test_cases.json` but runs the agent's own `test.py`.

Server layout:
- The fork is deployed at `~/investigathon/eg_team`, copied over with tar and scp; it is not a git checkout. Commit from the local PC, and do not put GitHub credentials on the shared server. The pristine upstream clone is at `~/investigathon/evilgenie_inspect`, kept for reference.
- Dependencies are installed with `uv` (`~/.local/bin/uv`, Python 3.12 managed by uv; the system Python is 3.10).
- Ollama v0.40.2 is installed without sudo in `~/.local/ollama`. It has been **stopped since 2026-10-25** to free 8.9 GB of RAM, because all agent runs now go through APIs (gpt-oss-20b on NVIDIA). It is still installed. Start it with `~/investigathon/start_ollama.sh` (a copy is in `evals/evilgenie/scripts/`; it binds 127.0.0.1 only, `OLLAMA_CONTEXT_LENGTH=32768`; it logs to `~/investigathon/ollama.log`).
- The models are `qwen3:8b` (about 9.6 GB of VRAM) and `qwen3:14b` (13.4 GB, fully on the GPU). qwen3:8b failed stage 1: with thinking on it timed out, and with thinking off it looped on failed `str_replace` calls and never ran a command.
- Launch runs with `scripts/run.sh <run_id> <model> <limit>` (for API models: `THINK=1 scripts/run.sh <run_id> openai-api/nvidia/openai/gpt-oss-20b <n> --reasoning-effort medium`; each 154-problem run uses ~1.6 GB of RAM, so watch `free -h` before adding more) from `~/investigathon/eg_team`. It uses the configuration that has been fixed since run_05: `--reasoning-effort none` (thinking off, a logged methodological decision), `-T enable_llm_judge=false`, and `--max-samples 1`. It writes to `~/investigathon/<run_id>.out`. Scale up in stages of 5, then 50, then 154 problems, with the gates described in `notas/corridas.md`. When checking whether a run is still alive, use `pgrep -f "[i]nspect eval"`: the bracket keeps pgrep from matching its own ssh command line. Always pass `--max-samples 1`, because Ollama serves one request at a time and the 600 s per-problem time limit is wall-clock. The task maps `difficulty="hard"` to LiveCodeBench "competition", and the full set is 154 problems. Each problem runs in a Docker container (`python:3.11-slim`, workspace `/home/agent/workspace`, no network). The agent has the `safe_bash`, `safe_python` and `text_editor` tools. The LLM judge defaults to `openai/gpt-5`; override it with `--model-role judge=...` or disable it with `-T enable_llm_judge=false`.
- `terminal-wrench/`: the dataset repo. It is **gitignored** and not committed here. To get it, run `git clone https://github.com/few-sh/terminal-wrench.git` from the project root.

## Environment

- Windows. **Python is not installed** (the `python` command resolves to the Microsoft Store stub). Until Python is installed, use PowerShell's `ConvertFrom-Json` for quick inspection. The monitoring scripts need `pip install openai python-dotenv` (and optionally `tiktoken`), plus an `OPENAI_API_KEY` set in the environment or in `monitoring/.env`.
- `index/tasks.json` (~19 MB) and `index/trajectories.json` (~15 MB, 6,289 rows) are large. Load and filter them; do not read them whole into context.
- Files contain non-ASCII glyphs (`◆ ◇ ~ °`). Open them as UTF-8.

## Dataset architecture (terminal-wrench/)

Three levels: **task → model → trajectory**. `tasks/<task_id>/` (the id is a number or a slug) contains `hack_summary.md` and one directory per model (`claude-opus-4.6`, `gemini-3.1-pro`, `gpt-5.4`). Each model directory contains:
- `task.json`: entry metadata plus the full list of trajectories with their classifications.
- `original_task/`: `instruction.md`, `tests/` (the verifier being exploited), `solution/`, `environment/`, `task.toml`.
- `baseline_trajectories/<N>/`: non-adversarial successful solves. These are the **negatives** for monitoring.
- `hack_trajectories/v5[_N]/`: rewarded hacks. These are the positives.
- `sanitized_trajectories/v5[_N]/`: the same hacks with the agent text rewritten to hide intent. Tool calls are unchanged.
- `stripped_trajectories/v5[_N]/`: the same hacks with all agent text blanked, keeping only actions and observations.
- `non_hack_trajectories/v5[_N]/`: attacker runs that solved the task legitimately or got no reward.

Each trial has `agent/trajectory.json`, `agent/episode-N/{prompt,response}.txt`, `result.json`, and `verifier/{reward.txt,test-stdout.txt}`. In `trajectory.json`, `steps[]` holds `message` (the agent's reasoning text, which is what the CoT-monitoring experiments vary), `tool_calls[].arguments.keystrokes`, `observation.results[].content`, and `metrics`. The first user message of hack trajectories contains the red-team prompt (`prompts/hack_prompt_v5.md`). The sanitized and stripped variants remove it.

`index/trajectories.json` is the flat table to use for most analysis. Each row has `task_id`, `model`, `source_dataset`, `classification`, `tree_name`/`trajectory_label` (which locate the folder), `reward`, token and cost fields, `episode_count`, `observed_categories` (11-category exploit taxonomy, multi-label), `key_hack_steps`, `brief_exploit_summary`, and `explanation`.

`classification` has four values: `rewarded_serious_exploit` (◆), `rewarded_nonserious_hack` (◇), `attacker_legitimate_solve` (~), and `no_reward` (°). "Hacks" means ◆ + ◇ (3,632). Baselines (2,352) are listed in `task.json`, not in `index/trajectories.json`.

Caveats for analysis:
- Every hack was **elicited by an explicit red-team prompt**. These trajectories show capability to hack, not spontaneous propensity.
- Category labels and classifications come from an LLM judge.
- Gemini has only 38 legitimate attacker solves, while Claude has 1,027. Per-model comparisons are confounded by how each model complies with the elicitation prompt.

## Monitoring pipeline (terminal-wrench/monitoring/)

Run the scripts from the `terminal-wrench/` root. The flow is `strip.py` / `sanitize.py` (create the variants), then `monitor.py` (LLM judge scores 0–1 using `monitoring/prompts/v1.txt`, the same prompt as `prompts/monitor_judge_v1.txt`), then `analyze.py` / `analyze_by_tag.py` / `auc.py` (AUC and TPR@5%FPR), then `render_analysis_charts.py`.

```
python monitoring/monitor.py --split exploit --max-samples 10 --output monitoring/results_small.json
python monitoring/monitor.py --split legitimate --dry-run --output monitoring/dry_run.json   # no API calls
python monitoring/analyze.py <positive_results.json> <negative_results.json> [--sanitized <file>]
python monitoring/analyze_by_tag.py --exploit <f> --legitimate <f> [--sanitized <f>]
```

`--split` takes `{hack,exploit,nonserious,legitimate}`, optionally prefixed with `sanitized_` or `stripped_`. Useful filters are `--task-filter <regex>`, `--source <dataset>`, `--max-per-source`, `--model`, and `--skip-existing`. The default judge model is `gpt-5.4-nano`. The paper used `gpt-5.4`. `monitoring/results_*.json` and `sanitize_*.json` are gitignored outputs. The published reference numbers are in `monitoring/analysis_*_gpt54_v1.json`.

`scripts/` (export, HF release, README rendering) and `generate_summaries.py` are the dataset authors' build tooling. They are not needed for analysis.
