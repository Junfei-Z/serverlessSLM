# Jetson Orin Super (8GB) — Token-Length vs. Quality Benchmark

**Goal:**  
Measure how input token length (L0→L3→P) affects *inference quality*, *latency*, *energy consumption*, and *output token length* on **Jetson Orin Super (8GB)**.  
Use 4 SLMs (`qwen1.5-1.8B`, `gemma-2-2B`, `phi-3.5-mini`, `qwen3-4B`) and prompts with 5 hierarchical levels (L0–P).

---

## Environment
```bash
sudo nvpmodel -m 0
sudo jetson_clocks
pip install llama-cpp-python pandas openpyxl requests
```

---

## Script A — `run_llamacpp_collect.py`
Run inference with `llama-cpp-python`, log **latency**, **token counts**, and **energy** per task.

### CLI Example
```bash
python run_llamacpp_collect.py   --models /models/qwen1.5-1.8b-chat-q6_k.gguf /models/gemma-2-2b-it-Q6_K.gguf   /models/Phi-3.5-mini-instruct-Q6_K.gguf /models/Qwen3-4B-Q6_K.gguf   --prompts /data/writing_prompts_hierarchical.csv   --out_jsonl /results/runs_llamacpp.jsonl
```

### Responsibilities
1. Load model (`llama_cpp.Llama`)
2. Measure idle power via `tegrastats`
3. For each (task, level):
   - Start sampling → record `t0`
   - Run inference → record `t1`
   - Integrate energy = ∫(P(t) - P_idle)dt
   - Count `prompt_tokens`, `completion_tokens`
   - Save JSON record

**Output JSONL per run**
```json
{
  "id": 1, "model_id": "gemma-2-2b-it",
  "level": "L2", "prompt_tokens": 350,
  "completion_tokens": 420, "latency_ms": 1830.5,
  "energy_joule": 2.7, "output_text": "..."
}
```

---

## Script B — `tegrastats_sampler.py`
Utility to record and integrate Jetson power usage.

**Functions**
- `start()` → launch `tegrastats --interval 100`
- `stop()` → terminate background thread
- `measure_idle(10s)` → return baseline (mW)
- `integrate_energy(t0, t1, idle_mw)` → trapezoidal ∫ of `(P - P_idle)`

**Returns:** total Joules for one inference.

---

## Script C — `judge_pairs.py`
Score L0–P outputs using external LLM-as-Judge API (GPT-4o compatible).

**CLI**
```bash
python judge_pairs.py   --questions /data/questionset.jsonl.txt   --runs_root /results   --model gpt-4o   --api_url https://api.chatanywhere.tech/v1/chat/completions   --api_key_env MY_JUDGE_KEY   --out /results/scores_mtbench.csv
```

**Rubric Prompt**
```
You are an impartial judge comparing two answers (A,B) to the same prompt.
Rate on: factuality, helpfulness, structure, conciseness.
Return "A", "B", or "Tie".
```

**Output CSV**
```
task_id,category,model_id,pair,winner,judge_model,turn
```

---

## Script D — `aggregate_to_excels.py`
Aggregate raw logs → Excel summaries.

**CLI**
```bash
python aggregate_to_excels.py   --runs /results/runs_llamacpp.jsonl   --scores /results/scores_mtbench.csv   --outdir /results
```

**Output Workbooks**
| File | Sheets | Description |
|------|---------|-------------|
| `quality_scores.xlsx` | per model | LLM-as-Judge scores |
| `energy_per_run.xlsx` | per model | Energy (J) |
| `latency_per_run.xlsx` | per model | Latency (ms) |
| `output_tokens_per_run.xlsx` | per model | Output token count |

---

## Directory Layout
```
/models/
  qwen1.5-1.8b-chat-q6_k.gguf
  gemma-2-2b-it-Q6_K.gguf
  Phi-3.5-mini-instruct-Q6_K.gguf
  Qwen3-4B-Q6_K.gguf
/data/
  writing_prompts_hierarchical.csv
  roleplay_prompts_hierarchical.csv
  questionset.jsonl.txt
/results/
  runs_llamacpp.jsonl
  scores_mtbench.csv
  *.xlsx
```

---

## Key Metrics
| Metric | Unit | Description |
|---------|------|-------------|
| Latency | ms | time per run |
| Energy | J | ∫(P - P_idle)dt |
| Tokens | count | prompt / output |
| Quality | score | LLM-as-Judge result |

---

✅ **Deliverables**
- `/results/runs_llamacpp.jsonl`
- `/results/scores_mtbench.csv`
- `/results/quality_scores.xlsx`
- `/results/energy_per_run.xlsx`
- `/results/latency_per_run.xlsx`
- `/results/output_tokens_per_run.xlsx`

---

### Notes
- Use `temperature=0.0` for determinism  
- Sequential runs (no parallel)  
- Repeat runs for mean ± std  
- 4 models × 5 prompt levels × N tasks
