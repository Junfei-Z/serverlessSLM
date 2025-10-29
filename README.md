# 🚀 Jetson SLM Benchmark: Prompt Length vs Quality

A comprehensive benchmarking framework for evaluating how input prompt length affects Small Language Model (SLM) performance on NVIDIA Jetson edge devices.

## 📊 Project Overview

This project measures the impact of hierarchical prompt engineering (5 levels from basic to verbose) on 4 Small Language Models across 6 key metrics:

- **Test Scale**: 80 questions × 5 prompt levels × 4 SLMs = **1,600 inferences**
- **Metrics**: Latency, Energy, Token counts, Quality scores (GPT-4 judged), Response text
- **Models**: Qwen1.5-1.8B, Gemma-2-2B, Phi-3.5-Mini, Qwen3-4B
- **Platform**: NVIDIA Jetson Orin Super (8GB)

## 🎯 Key Features

✅ **Automatic Energy Monitoring** - Measures power consumption via tegrastats
✅ **LLM-as-Judge Evaluation** - GPT-4 absolute scoring (0-10) with 4 dimensions
✅ **Response Export** - Automatically exports to CSV and text files for review
✅ **Comprehensive Reports** - Generates Excel workbooks with quality, energy, latency data
✅ **Fully Automated** - One command runs entire pipeline

## 📁 Project Structure

```
serverlessSLM/
├── Core Scripts
│   ├── tegrastats_sampler.py          # Power monitoring utility
│   ├── run_llamacpp_collect.py        # Main inference runner
│   ├── judge_absolute.py              # GPT-4 quality evaluator
│   ├── aggregate_to_excels_absolute.py # Results aggregator
│   └── export_responses.py            # Response export tool
│
├── Helper Scripts
│   ├── convert_excel_to_csv.py        # Excel → CSV converter
│   ├── generate_prompts.py            # Hierarchical prompt generator
│   └── run_full_benchmark.sh          # Automated runner
│
├── Data
│   ├── question.jsonl                 # Original questions (80)
│   ├── generated_prompts.xlsx         # Generated hierarchical prompts
│   └── data/*.csv                     # CSV prompts per category
│
├── Documentation (Chinese) 中文文档
│   ├── 快速启动教程.md                 # Quick Start Guide (Chinese)
│   ├── 模型配置验证.md                 # Model Configuration
│   └── 项目总结.md                     # Project Summary
│
└── Documentation (English)
    ├── QUICK_START.md                 # Quick Start Guide
    ├── JETSON_SETUP_README.md         # Complete Setup Guide
    ├── EXPORT_RESPONSES_GUIDE.md      # Response Export Guide
    ├── JUDGE_COMPARISON.md            # Scoring Method Comparison
    └── QUICK_REFERENCE.md             # Command Reference Card
```

## 🚀 Quick Start

### 1. Prepare Data (On PC)

```bash
# Convert Excel prompts to CSV
python convert_excel_to_csv.py --excel generated_prompts.xlsx --outdir data

# Download 4 GGUF models (Q6_K quantization, ~8GB total)
# - qwen1.5-1.8b-chat-q6_k.gguf
# - gemma-2-2b-it-Q6_K.gguf
# - Phi-3.5-mini-instruct-Q6_K.gguf
# - Qwen3-4B-Q6_K.gguf

# Package for Jetson
tar -czf jetson_benchmark.tar.gz *.py *.sh *.md question.jsonl data/ models/ requirements.txt

# Transfer to Jetson
scp jetson_benchmark.tar.gz jetson@<JETSON_IP>:~/
```

### 2. Run on Jetson

```bash
# Extract
tar -xzf jetson_benchmark.tar.gz
cd jetson_benchmark_package

# Setup
sudo nvpmodel -m 0 && sudo jetson_clocks
pip3 install -r requirements.txt

# Run (Interactive)
bash run_full_benchmark.sh
# Select option 1: Full benchmark

# Or run manually
python3 run_llamacpp_collect.py \
  --models models/*.gguf \
  --prompts data/writing_prompts_hierarchical.csv \
  --out_jsonl results/runs_llamacpp.jsonl

python3 judge_absolute.py \
  --questions question.jsonl \
  --runs results/runs_llamacpp.jsonl

python3 aggregate_to_excels_absolute.py \
  --runs results/runs_llamacpp.jsonl \
  --scores results/scores_absolute.csv \
  --outdir results/
```

## 📊 Output Files

After running, you'll get:

```
results/
├── runs_llamacpp.jsonl              # Raw inference logs (1,600 lines)
├── scores_absolute.csv              # GPT-4 evaluation scores
├── quality_scores_detailed.xlsx     # Detailed scores per question ⭐
├── model_comparison.xlsx            # Model comparison summary ⭐⭐⭐
├── energy_per_run.xlsx              # Energy consumption data
├── latency_per_run.xlsx             # Inference latency data
└── output_tokens_per_run.xlsx       # Output length data

exported_responses/
├── all_responses.csv                # All responses in CSV (Excel-friendly) ⭐
├── summary_report.txt               # Statistical summary
└── responses_by_model/              # Individual text files (1,600 files)
    ├── qwen1.5-1.8b/
    ├── gemma-2-2b/
    ├── phi-3.5-mini/
    └── qwen3-4b/
```

## 📈 Prompt Levels

Each question is tested with 5 hierarchical prompt versions:

| Level | Name | Description | Token Delta |
|-------|------|-------------|-------------|
| L0 | Base | Original question | baseline |
| L1 | Clarified | + constraints, criteria | +50-150 |
| L2 | Guided | + step-by-step instructions | +100-200 |
| L3 | Example-Guided | + examples, style guide | +150-250 |
| P | Placebo | + uninformative fluff | +100-200 |

**Key Property**: L0 < L1 < L2 < L3 < P (monotonically increasing)

## 📊 Measured Metrics

| Metric | Unit | Description | Typical Range |
|--------|------|-------------|---------------|
| **Latency** | ms | Inference time | 500-5000 |
| **Energy** | J | Power consumption (above idle) | 1-10 |
| **Prompt Tokens** | count | Input length | 20-600 |
| **Output Tokens** | count | Generated length | 50-500 |
| **Quality Score** | 0-10 | GPT-4 judgment (4 dimensions) | 5-9 |
| **Output Text** | string | Complete response | - |

### Quality Score Breakdown

- **Factuality** (0-2.5): Accuracy and correctness
- **Helpfulness** (0-2.5): How well it addresses needs
- **Structure** (0-2.5): Organization and logical flow
- **Conciseness** (0-2.5): Efficiency without sacrificing completeness

## ⏱️ Time & Cost Estimates

### Full Test (80 questions)

| Phase | Time | Cost |
|-------|------|------|
| Inference | 2-4 hours | Free (local) |
| Evaluation | 40-60 min | ~$8 (GPT-4o) |
| **Total** | **3-5 hours** | **~$8** |

### Single Category (10 questions)

| Phase | Time | Cost |
|-------|------|------|
| Inference | 15-30 min | Free |
| Evaluation | 5-10 min | ~$1 |
| **Total** | **~25 min** | **~$1** |

## 🛠️ Requirements

### Hardware
- NVIDIA Jetson Orin Super (8GB) or similar
- ~15GB free disk space

### Software
- Python 3.8+
- CUDA support
- Dependencies: `llama-cpp-python`, `tiktoken`, `openpyxl`, `pandas`, `requests`

### Models (Download separately)
- 4 GGUF models (Q6_K quantization)
- Total size: ~8GB

## 📚 Documentation

### For Quick Start
- **Chinese**: `快速启动教程.md` ⭐ (Detailed Chinese guide)
- **English**: `QUICK_START.md`

### For Complete Setup
- `JETSON_SETUP_README.md` - Full setup instructions
- `EXPORT_RESPONSES_GUIDE.md` - How to export and review responses
- `JUDGE_COMPARISON.md` - Scoring method comparison

### For Reference
- `QUICK_REFERENCE.md` - Command cheat sheet
- `jetson_benchmark_spec_short.md` - Technical specification
- `question_generate.md` - Prompt generation specification

## 🔬 Research Questions

This benchmark helps answer:

1. **Does longer input improve quality?** Compare L0 vs L3 average scores
2. **What's the cost of quality?** Latency/energy increase percentage
3. **Which level offers best value?** Quality/energy ratio analysis
4. **Which model suits edge deployment?** Consider quality, speed, energy

## 🎯 Use Cases

- 📊 **Research**: Quantify prompt engineering impact on edge AI
- 🔋 **Energy Analysis**: Measure power-quality tradeoffs
- 🤖 **Model Selection**: Compare SLMs for edge deployment
- 📈 **Prompt Optimization**: Find optimal prompt complexity

## 🤝 Contributing

Contributions are welcome! Areas for improvement:
- Additional SLM models
- More evaluation dimensions
- Alternative LLM-as-Judge implementations
- Visualization tools

## 📄 License

This project is provided as-is for research and educational purposes.

## 🙏 Acknowledgments

- Benchmark specification inspired by MT-Bench and AlpacaEval
- Uses llama.cpp for efficient GGUF inference
- Powered by NVIDIA Jetson edge AI platform

## 📞 Citation

If you use this benchmark in your research, please cite:

```bibtex
@software{jetson_slm_benchmark,
  title = {Jetson SLM Benchmark: Prompt Length vs Quality},
  author = {Your Name},
  year = {2025},
  url = {https://github.com/yourusername/serverlessSLM}
}
```

---

**Happy Benchmarking!** 🚀📊

For questions or issues, please refer to the documentation or open an issue on GitHub.