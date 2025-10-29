# Jetson Benchmark Setup Guide

Complete guide for running the token-length vs. quality benchmark on Jetson Orin Super (8GB).

---

## Overview

This benchmark measures how input token length (L0→L1→L2→L3→P) affects:
- **Inference quality** (via LLM-as-Judge)
- **Latency** (milliseconds per inference)
- **Energy consumption** (Joules per inference)
- **Output token length** (tokens generated)

**Models tested:** `qwen1.5-1.8B`, `gemma-2-2B`, `phi-3.5-mini`, `qwen3-4B`

---

## Phase 1: Preparation (On Your PC)

### Step 1.1: Generate Hierarchical Prompts

✅ Already completed! You have `generated_prompts.xlsx` with 5 prompt levels.

### Step 1.2: Convert Excel to CSV

```bash
python convert_excel_to_csv.py \
  --excel generated_prompts.xlsx \
  --outdir data \
  --split
```

This creates category-specific CSV files in the `data/` directory:
- `writing_prompts_hierarchical.csv`
- `roleplay_prompts_hierarchical.csv`
- `reasoning_prompts_hierarchical.csv`
- `math_prompts_hierarchical.csv`
- `coding_prompts_hierarchical.csv`
- `extraction_prompts_hierarchical.csv`
- `stem_prompts_hierarchical.csv`
- `humanities_prompts_hierarchical.csv`

### Step 1.3: Download GGUF Models

Download Q6_K quantized models (best quality for benchmarking):

```bash
# Create models directory
mkdir -p models

# Download models (example using wget or huggingface-cli)
# Qwen 1.5 1.8B
wget https://huggingface.co/Qwen/Qwen1.5-1.8B-Chat-GGUF/resolve/main/qwen1_5-1_8b-chat-q6_k.gguf -O models/qwen1.5-1.8b-chat-q6_k.gguf

# Gemma 2 2B
wget https://huggingface.co/lmstudio-community/gemma-2-2b-it-GGUF/resolve/main/gemma-2-2b-it-Q6_K.gguf -O models/gemma-2-2b-it-Q6_K.gguf

# Phi 3.5 Mini
wget https://huggingface.co/bartowski/Phi-3.5-mini-instruct-GGUF/resolve/main/Phi-3.5-mini-instruct-Q6_K.gguf -O models/Phi-3.5-mini-instruct-Q6_K.gguf

# Qwen 3 4B
wget https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q6_K.gguf -O models/Qwen3-4B-Q6_K.gguf
```

### Step 1.4: Prepare Files for Transfer

```bash
# Create a transfer package
mkdir jetson_benchmark_package

# Copy scripts
cp *.py jetson_benchmark_package/
cp question.jsonl jetson_benchmark_package/

# Copy data and models
cp -r data/ jetson_benchmark_package/
cp -r models/ jetson_benchmark_package/

# Create results directory
mkdir jetson_benchmark_package/results

# Create tarball
tar -czf jetson_benchmark.tar.gz jetson_benchmark_package/
```

### Step 1.5: Transfer to Jetson

```bash
# Using scp (replace with your Jetson IP)
scp jetson_benchmark.tar.gz jetson@<JETSON_IP>:~/

# Or use USB drive, network share, etc.
```

---

## Phase 2: Setup on Jetson

### Step 2.1: Extract Files

```bash
ssh jetson@<JETSON_IP>

cd ~
tar -xzf jetson_benchmark.tar.gz
cd jetson_benchmark_package
```

### Step 2.2: Set Performance Mode

```bash
# Set to maximum performance mode
sudo nvpmodel -m 0

# Lock clocks to maximum
sudo jetson_clocks

# Verify settings
sudo nvpmodel -q
```

### Step 2.3: Install Dependencies

```bash
# Update pip
pip3 install --upgrade pip

# Install required packages
pip3 install llama-cpp-python pandas openpyxl requests

# Verify tegrastats is available
which tegrastats
# Should output: /usr/bin/tegrastats
```

**Note:** If `llama-cpp-python` installation is slow, you can build with CUDA support:

```bash
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip install llama-cpp-python
```

### Step 2.4: Test Power Monitoring

```bash
# Test tegrastats monitor
python3 tegrastats_sampler.py

# Expected output:
# Tegrastats monitor started (interval: 100ms)
# Measuring idle power for 5.0 seconds...
# Idle power: 3500.0 mW (from XX samples)
# ...
```

Press Ctrl+C if it hangs. If it works, you're ready!

---

## Phase 3: Run Benchmark on Jetson

### Step 3.1: Run Inference and Collect Metrics

Choose which category to benchmark (or run all):

**Option A: Single Category**

```bash
python3 run_llamacpp_collect.py \
  --models \
    models/qwen1.5-1.8b-chat-q6_k.gguf \
    models/gemma-2-2b-it-Q6_K.gguf \
    models/Phi-3.5-mini-instruct-Q6_K.gguf \
    models/Qwen3-4B-Q6_K.gguf \
  --prompts data/writing_prompts_hierarchical.csv \
  --out_jsonl results/runs_llamacpp.jsonl \
  --temperature 0.0 \
  --max_tokens 1024 \
  --n_ctx 4096
```

**Option B: All Categories (Sequential)**

```bash
# Run each category sequentially
for category in writing roleplay reasoning math coding extraction stem humanities; do
  echo "Running $category benchmark..."

  python3 run_llamacpp_collect.py \
    --models \
      models/qwen1.5-1.8b-chat-q6_k.gguf \
      models/gemma-2-2b-it-Q6_K.gguf \
      models/Phi-3.5-mini-instruct-Q6_K.gguf \
      models/Qwen3-4B-Q6_K.gguf \
    --prompts data/${category}_prompts_hierarchical.csv \
    --out_jsonl results/runs_llamacpp_${category}.jsonl \
    --temperature 0.0 \
    --max_tokens 1024

  echo "Completed $category"
  echo "---"
done

# Merge all results
cat results/runs_llamacpp_*.jsonl > results/runs_llamacpp.jsonl
```

**Expected Duration:**
- ~2-5 seconds per inference
- 4 models × 5 levels × N questions per category
- Example: 10 questions = 200 inferences = ~10-20 minutes per category

### Step 3.2: Monitor Progress

In another terminal:

```bash
# Watch results being written
tail -f results/runs_llamacpp.jsonl

# Check tegrastats live
tegrastats --interval 500
```

---

## Phase 4: Quality Evaluation (Can Run Anywhere)

You can transfer results back to your PC or run this on Jetson if it has internet access.

### Step 4.1: Set API Key

```bash
# For OpenAI-compatible API
export OPENAI_API_KEY="your-api-key-here"

# Or use custom env variable name
export MY_JUDGE_KEY="your-api-key-here"
```

### Step 4.2: Run LLM-as-Judge

```bash
python3 judge_pairs.py \
  --questions question.jsonl \
  --runs_root results/ \
  --model gpt-4o \
  --api_url https://api.openai.com/v1/chat/completions \
  --api_key_env OPENAI_API_KEY \
  --out results/scores_mtbench.csv
```

**Alternative API endpoints:**
- ChatAnywhere: `https://api.chatanywhere.tech/v1/chat/completions`
- OpenRouter: `https://openrouter.ai/api/v1/chat/completions`
- Local LLM: `http://localhost:8080/v1/chat/completions`

**Expected Duration:**
- ~1-2 seconds per comparison
- 4 models × 10 pairwise comparisons × N questions
- Example: 10 questions = 400 API calls = ~10-15 minutes

**Cost Estimate (GPT-4o):**
- ~$0.005 per comparison
- 400 comparisons = ~$2

---

## Phase 5: Generate Reports

### Step 5.1: Aggregate Results to Excel

```bash
python3 aggregate_to_excels.py \
  --runs results/runs_llamacpp.jsonl \
  --scores results/scores_mtbench.csv \
  --outdir results/
```

### Step 5.2: Review Output Files

The following Excel files will be created in `results/`:

1. **`quality_scores.xlsx`**
   - Sheet per model
   - Win rates for each prompt level
   - Comparison statistics

2. **`energy_per_run.xlsx`**
   - Sheet per model
   - Energy consumption (Joules) per task and level
   - Summary statistics (mean, etc.)

3. **`latency_per_run.xlsx`**
   - Sheet per model
   - Latency (ms) per task and level
   - Summary statistics

4. **`output_tokens_per_run.xlsx`**
   - Sheet per model
   - Output token counts per task and level
   - Summary statistics

### Step 5.3: Transfer Results Back to PC

```bash
# On your PC
scp -r jetson@<JETSON_IP>:~/jetson_benchmark_package/results ./jetson_results

# Or download via web interface, USB, etc.
```

---

## Troubleshooting

### Power Monitoring Not Working

```bash
# Check if tegrastats exists
which tegrastats

# Try running manually
tegrastats --interval 100

# Check permissions
ls -l /usr/bin/tegrastats

# If permission denied, add to sudoers or run scripts with sudo
```

### Out of Memory Errors

```bash
# Reduce context window
--n_ctx 2048

# Reduce max tokens
--max_tokens 512

# Use smaller models first
```

### llama-cpp-python Installation Issues

```bash
# Install build dependencies
sudo apt-get install build-essential cmake

# Install with CUDA support
CMAKE_ARGS="-DLLAMA_CUBLAS=on" pip3 install llama-cpp-python --no-cache-dir

# Or install pre-built wheel
pip3 install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu121
```

### API Rate Limiting

```bash
# Increase delay in judge_pairs.py (line ~235)
time.sleep(1.0)  # Change from 0.5 to 1.0 seconds

# Or use a local LLM for judging
```

---

## Quick Start Commands

### Full Benchmark (One Category)

```bash
# On Jetson
sudo nvpmodel -m 0 && sudo jetson_clocks

python3 run_llamacpp_collect.py \
  --models models/*.gguf \
  --prompts data/writing_prompts_hierarchical.csv \
  --out_jsonl results/runs_llamacpp.jsonl

# Back on PC (or Jetson with internet)
export OPENAI_API_KEY="your-key"

python3 judge_pairs.py \
  --questions question.jsonl \
  --runs_root results/ \
  --model gpt-4o \
  --api_url https://api.openai.com/v1/chat/completions \
  --api_key_env OPENAI_API_KEY \
  --out results/scores_mtbench.csv

python3 aggregate_to_excels.py \
  --runs results/runs_llamacpp.jsonl \
  --scores results/scores_mtbench.csv \
  --outdir results/
```

---

## Expected Results Structure

```
results/
├── runs_llamacpp.jsonl           # Raw inference logs
├── scores_mtbench.csv             # Judge evaluations
├── quality_scores.xlsx            # Win rates by level
├── energy_per_run.xlsx            # Energy consumption
├── latency_per_run.xlsx           # Inference speed
└── output_tokens_per_run.xlsx    # Output lengths
```

---

## Tips for Best Results

1. **Run benchmarks overnight** - Full benchmark can take several hours
2. **Keep Jetson cool** - Ensure good airflow to prevent throttling
3. **Close other applications** - Minimize background processes
4. **Use wired network** - For stable API calls during judging
5. **Backup results frequently** - Copy JSONL files after each category
6. **Monitor disk space** - Results can be large with many questions

---

## Contact & Support

If you encounter issues:
1. Check `results/` directory for partial results
2. Review error messages in terminal
3. Verify all dependencies are installed
4. Ensure Jetson is in max performance mode

---

## File Manifest

**Scripts:**
- `tegrastats_sampler.py` - Power monitoring utility
- `run_llamacpp_collect.py` - Main inference runner
- `judge_pairs.py` - LLM-as-Judge evaluator
- `aggregate_to_excels.py` - Results aggregator
- `convert_excel_to_csv.py` - Excel to CSV converter
- `generate_prompts.py` - Prompt generation (already run)

**Data:**
- `question.jsonl` - Original questions
- `generated_prompts.xlsx` - Hierarchical prompts
- `data/*.csv` - CSV prompts per category

**Models:**
- `models/*.gguf` - GGUF quantized models

**Results:**
- `results/*.jsonl` - Raw logs
- `results/*.csv` - Scores
- `results/*.xlsx` - Final reports

---

Good luck with your benchmark! 🚀
