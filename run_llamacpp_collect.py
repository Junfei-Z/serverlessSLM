"""
LlamaCPP Inference Runner with Energy Monitoring
Runs inference on hierarchical prompts and collects performance metrics.
"""

import argparse
import json
import time
import csv
import os
from pathlib import Path
from typing import List, Dict, Optional
from dataclasses import dataclass

try:
    from llama_cpp import Llama
except ImportError:
    print("Error: llama-cpp-python not installed")
    print("Install with: pip install llama-cpp-python")
    exit(1)

from tegrastats_sampler import TegrastatsMonitor


@dataclass
class PromptTask:
    """Represents a single prompt task."""
    question_id: int
    category: str
    topic: str
    level: str
    prompt_text: str


@dataclass
class InferenceResult:
    """Stores results from a single inference run."""
    question_id: int
    model_id: str
    category: str
    level: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    energy_joule: float
    output_text: str


def load_prompts_from_csv(csv_path: str) -> List[PromptTask]:
    """
    Load hierarchical prompts from CSV file.

    Expected CSV format:
    question_id,category,topic,L0,L1,L2,L3,P
    """
    prompts = []

    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for row in reader:
            question_id = int(row['question_id'])
            category = row['category']
            topic = row['topic']

            # Create tasks for each level
            for level in ['L0', 'L1', 'L2', 'L3', 'P']:
                if level in row and row[level]:
                    task = PromptTask(
                        question_id=question_id,
                        category=category,
                        topic=topic,
                        level=level,
                        prompt_text=row[level]
                    )
                    prompts.append(task)

    print(f"Loaded {len(prompts)} prompt tasks from {csv_path}")
    return prompts


def extract_model_id(model_path: str) -> str:
    """Extract short model ID from full path."""
    filename = Path(model_path).stem

    # Map common patterns to short IDs
    if 'qwen1.5' in filename.lower() or 'qwen-1.5' in filename.lower():
        return 'qwen1.5-1.8b'
    elif 'gemma-2-2b' in filename.lower() or 'gemma2-2b' in filename.lower():
        return 'gemma-2-2b'
    elif 'phi-3.5' in filename.lower() or 'phi3.5' in filename.lower():
        return 'phi-3.5-mini'
    elif 'qwen3-4b' in filename.lower() or 'qwen-3-4b' in filename.lower():
        return 'qwen3-4b'
    else:
        # Fallback: use filename without extension
        return filename.replace('-Q6_K', '').replace('-q6_k', '')


def load_model(model_path: str, n_ctx: int = 4096, n_gpu_layers: int = -1) -> Llama:
    """
    Load GGUF model with llama-cpp-python.

    Args:
        model_path: Path to GGUF model file
        n_ctx: Context window size
        n_gpu_layers: Number of layers to offload to GPU (-1 = all)

    Returns:
        Loaded Llama model
    """
    print(f"\nLoading model: {model_path}")
    print(f"  Context size: {n_ctx}")
    print(f"  GPU layers: {n_gpu_layers}")

    start_time = time.time()

    model = Llama(
        model_path=model_path,
        n_ctx=n_ctx,
        n_gpu_layers=n_gpu_layers,
        verbose=False
    )

    load_time = time.time() - start_time
    print(f"  Model loaded in {load_time:.2f}s")

    return model


def run_inference(
    model: Llama,
    prompt: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    stop: Optional[List[str]] = None
) -> tuple[str, int, int]:
    """
    Run inference and return output text and token counts.

    Args:
        model: Loaded Llama model
        prompt: Input prompt text
        temperature: Sampling temperature
        max_tokens: Maximum output tokens
        stop: Stop sequences

    Returns:
        (output_text, prompt_tokens, completion_tokens)
    """
    response = model.create_completion(
        prompt=prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        stop=stop,
        echo=False
    )

    output_text = response['choices'][0]['text']

    # Get token counts from usage stats
    prompt_tokens = response['usage']['prompt_tokens']
    completion_tokens = response['usage']['completion_tokens']

    return output_text, prompt_tokens, completion_tokens


def run_single_task(
    model: Llama,
    model_id: str,
    task: PromptTask,
    monitor: TegrastatsMonitor,
    idle_power: float,
    temperature: float = 0.0,
    max_tokens: int = 1024
) -> InferenceResult:
    """
    Run inference on a single task and collect all metrics.

    Args:
        model: Loaded model
        model_id: Short model identifier
        task: Prompt task to run
        monitor: Power monitor
        idle_power: Idle power baseline (mW)
        temperature: Sampling temperature
        max_tokens: Max output tokens

    Returns:
        InferenceResult with all metrics
    """
    print(f"  [{task.level}] Q{task.question_id} - {task.category}")

    # Clear old samples
    monitor.clear_samples()
    time.sleep(0.1)

    # Start timing and run inference
    t_start = time.time()

    output_text, prompt_tokens, completion_tokens = run_inference(
        model=model,
        prompt=task.prompt_text,
        temperature=temperature,
        max_tokens=max_tokens
    )

    t_end = time.time()

    # Calculate metrics
    latency_ms = (t_end - t_start) * 1000.0
    energy_joule = monitor.integrate_energy(t_start, t_end, idle_mw=idle_power)

    print(f"    Latency: {latency_ms:.1f}ms | "
          f"Tokens: {prompt_tokens}→{completion_tokens} | "
          f"Energy: {energy_joule:.3f}J")

    return InferenceResult(
        question_id=task.question_id,
        model_id=model_id,
        category=task.category,
        level=task.level,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        latency_ms=latency_ms,
        energy_joule=energy_joule,
        output_text=output_text
    )


def save_result_jsonl(result: InferenceResult, output_file: str):
    """Append inference result to JSONL file."""
    record = {
        'question_id': result.question_id,
        'model_id': result.model_id,
        'category': result.category,
        'level': result.level,
        'prompt_tokens': result.prompt_tokens,
        'completion_tokens': result.completion_tokens,
        'latency_ms': round(result.latency_ms, 2),
        'energy_joule': round(result.energy_joule, 4),
        'output_text': result.output_text
    }

    with open(output_file, 'a', encoding='utf-8') as f:
        f.write(json.dumps(record, ensure_ascii=False) + '\n')


def run_benchmark(
    model_paths: List[str],
    prompts_csv: str,
    output_jsonl: str,
    temperature: float = 0.0,
    max_tokens: int = 1024,
    idle_duration: float = 10.0,
    n_ctx: int = 4096,
    n_gpu_layers: int = -1
):
    """
    Run full benchmark across all models and prompts.

    Args:
        model_paths: List of paths to GGUF models
        prompts_csv: Path to prompts CSV file
        output_jsonl: Path to output JSONL file
        temperature: Sampling temperature
        max_tokens: Max output tokens
        idle_duration: Idle power measurement duration (seconds)
        n_ctx: Context window size
        n_gpu_layers: GPU layers to offload
    """
    # Load prompts
    print("="*80)
    print("LOADING PROMPTS")
    print("="*80)
    tasks = load_prompts_from_csv(prompts_csv)

    # Create output directory
    os.makedirs(os.path.dirname(output_jsonl) or '.', exist_ok=True)

    # Initialize power monitor
    print("\n" + "="*80)
    print("INITIALIZING POWER MONITOR")
    print("="*80)

    monitor = TegrastatsMonitor(interval_ms=100)
    monitor.start()

    try:
        # Measure idle power
        idle_power = monitor.measure_idle(duration_sec=idle_duration)

        # Run benchmark for each model
        for model_path in model_paths:
            model_id = extract_model_id(model_path)

            print("\n" + "="*80)
            print(f"BENCHMARKING: {model_id}")
            print("="*80)

            # Load model
            model = load_model(model_path, n_ctx=n_ctx, n_gpu_layers=n_gpu_layers)

            # Run all tasks
            for i, task in enumerate(tasks, 1):
                print(f"\nTask {i}/{len(tasks)}")

                try:
                    result = run_single_task(
                        model=model,
                        model_id=model_id,
                        task=task,
                        monitor=monitor,
                        idle_power=idle_power,
                        temperature=temperature,
                        max_tokens=max_tokens
                    )

                    # Save result
                    save_result_jsonl(result, output_jsonl)

                except Exception as e:
                    print(f"    ERROR: {e}")
                    continue

            # Unload model
            del model
            print(f"\nCompleted {model_id}")

    finally:
        # Stop monitor
        monitor.stop()

    print("\n" + "="*80)
    print("BENCHMARK COMPLETE")
    print("="*80)
    print(f"Results saved to: {output_jsonl}")


def main():
    parser = argparse.ArgumentParser(
        description="Run LlamaCPP inference benchmark with energy monitoring"
    )

    parser.add_argument(
        '--models',
        nargs='+',
        required=True,
        help='Paths to GGUF model files'
    )

    parser.add_argument(
        '--prompts',
        required=True,
        help='Path to prompts CSV file'
    )

    parser.add_argument(
        '--out_jsonl',
        required=True,
        help='Path to output JSONL file'
    )

    parser.add_argument(
        '--temperature',
        type=float,
        default=0.0,
        help='Sampling temperature (default: 0.0 for determinism)'
    )

    parser.add_argument(
        '--max_tokens',
        type=int,
        default=1024,
        help='Maximum output tokens (default: 1024)'
    )

    parser.add_argument(
        '--idle_duration',
        type=float,
        default=10.0,
        help='Idle power measurement duration in seconds (default: 10.0)'
    )

    parser.add_argument(
        '--n_ctx',
        type=int,
        default=4096,
        help='Context window size (default: 4096)'
    )

    parser.add_argument(
        '--n_gpu_layers',
        type=int,
        default=-1,
        help='Number of layers to offload to GPU, -1 for all (default: -1)'
    )

    args = parser.parse_args()

    # Validate inputs
    for model_path in args.models:
        if not os.path.exists(model_path):
            print(f"Error: Model file not found: {model_path}")
            exit(1)

    if not os.path.exists(args.prompts):
        print(f"Error: Prompts CSV not found: {args.prompts}")
        exit(1)

    # Run benchmark
    run_benchmark(
        model_paths=args.models,
        prompts_csv=args.prompts,
        output_jsonl=args.out_jsonl,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        idle_duration=args.idle_duration,
        n_ctx=args.n_ctx,
        n_gpu_layers=args.n_gpu_layers
    )


if __name__ == "__main__":
    main()
