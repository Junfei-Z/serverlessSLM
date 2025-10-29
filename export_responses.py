"""
Export Inference Responses to Readable Formats
将推理结果导出为易读的CSV和文本文件，方便复查。
"""

import argparse
import json
import csv
import os
from pathlib import Path
from typing import List, Dict
from collections import defaultdict


def load_inference_results(jsonl_file: str) -> List[Dict]:
    """Load inference results from JSONL."""
    results = []

    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    print(f"Loaded {len(results)} inference results")
    return results


def export_to_csv(results: List[Dict], output_file: str):
    """
    Export all responses to a CSV file.

    CSV columns:
    - question_id
    - model_id
    - category
    - level
    - prompt_tokens
    - completion_tokens
    - latency_ms
    - energy_joule
    - output_text (完整的response)
    """
    print(f"\nExporting to CSV: {output_file}")

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Headers
        writer.writerow([
            'question_id',
            'model_id',
            'category',
            'level',
            'prompt_tokens',
            'completion_tokens',
            'latency_ms',
            'energy_joule',
            'output_text'
        ])

        # Data rows
        for result in sorted(results, key=lambda x: (x['model_id'], x['question_id'], x['level'])):
            writer.writerow([
                result['question_id'],
                result['model_id'],
                result['category'],
                result['level'],
                result['prompt_tokens'],
                result['completion_tokens'],
                round(result['latency_ms'], 2),
                round(result['energy_joule'], 4),
                result['output_text']
            ])

    print(f"  ✓ Saved {len(results)} responses to CSV")


def export_to_text_files(results: List[Dict], output_dir: str):
    """
    Export responses to individual text files organized by model and question.

    Directory structure:
    output_dir/
      qwen1.5-1.8b/
        Q81_L0.txt
        Q81_L1.txt
        ...
      gemma-2-2b/
        Q81_L0.txt
        ...
    """
    print(f"\nExporting to text files: {output_dir}/")

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Organize by model
    by_model = defaultdict(list)
    for result in results:
        by_model[result['model_id']].append(result)

    total_files = 0

    for model_id, model_results in sorted(by_model.items()):
        # Create model directory
        model_dir = os.path.join(output_dir, model_id)
        os.makedirs(model_dir, exist_ok=True)

        for result in sorted(model_results, key=lambda x: (x['question_id'], x['level'])):
            # Create filename: Q{id}_{level}.txt
            filename = f"Q{result['question_id']:03d}_{result['level']}.txt"
            filepath = os.path.join(model_dir, filename)

            # Write response with metadata
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=" * 80 + "\n")
                f.write(f"Question ID: {result['question_id']}\n")
                f.write(f"Model: {result['model_id']}\n")
                f.write(f"Category: {result['category']}\n")
                f.write(f"Prompt Level: {result['level']}\n")
                f.write(f"Prompt Tokens: {result['prompt_tokens']}\n")
                f.write(f"Output Tokens: {result['completion_tokens']}\n")
                f.write(f"Latency: {result['latency_ms']:.2f} ms\n")
                f.write(f"Energy: {result['energy_joule']:.4f} J\n")
                f.write(f"=" * 80 + "\n\n")
                f.write(result['output_text'])
                f.write("\n")

            total_files += 1

        print(f"  ✓ {model_id}: {len(model_results)} files")

    print(f"  ✓ Total: {total_files} text files created")


def export_comparison_markdown(results: List[Dict], output_file: str, question_id: int):
    """
    Export side-by-side comparison for a specific question in Markdown format.

    Creates a markdown file comparing all prompt levels for one question.
    """
    print(f"\nExporting comparison for Q{question_id}: {output_file}")

    # Filter results for this question
    question_results = [r for r in results if r['question_id'] == question_id]

    if not question_results:
        print(f"  ✗ No results found for question {question_id}")
        return

    # Organize by model and level
    by_model = defaultdict(dict)
    for result in question_results:
        by_model[result['model_id']][result['level']] = result

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(f"# Question {question_id} - Comparison Across Prompt Levels\n\n")

        for model_id in sorted(by_model.keys()):
            f.write(f"## Model: {model_id}\n\n")

            levels = ['L0', 'L1', 'L2', 'L3', 'P']

            for level in levels:
                if level not in by_model[model_id]:
                    continue

                result = by_model[model_id][level]

                f.write(f"### {level}\n\n")
                f.write(f"**Metrics:**\n")
                f.write(f"- Prompt Tokens: {result['prompt_tokens']}\n")
                f.write(f"- Output Tokens: {result['completion_tokens']}\n")
                f.write(f"- Latency: {result['latency_ms']:.2f} ms\n")
                f.write(f"- Energy: {result['energy_joule']:.4f} J\n\n")
                f.write(f"**Response:**\n\n")
                f.write(f"```\n{result['output_text']}\n```\n\n")
                f.write("---\n\n")

    print(f"  ✓ Comparison saved for {len(by_model)} model(s)")


def create_summary_report(results: List[Dict], output_file: str):
    """
    Create a summary report with statistics.
    """
    print(f"\nCreating summary report: {output_file}")

    # Organize by model
    by_model = defaultdict(list)
    for result in results:
        by_model[result['model_id']].append(result)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write("=" * 80 + "\n")
        f.write("INFERENCE RESULTS SUMMARY\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Total Inferences: {len(results)}\n")
        f.write(f"Models Tested: {len(by_model)}\n\n")

        for model_id in sorted(by_model.keys()):
            model_results = by_model[model_id]

            f.write(f"\n{'=' * 80}\n")
            f.write(f"Model: {model_id}\n")
            f.write(f"{'=' * 80}\n\n")

            f.write(f"Total Inferences: {len(model_results)}\n\n")

            # Statistics by level
            by_level = defaultdict(list)
            for result in model_results:
                by_level[result['level']].append(result)

            f.write("Statistics by Prompt Level:\n\n")

            for level in ['L0', 'L1', 'L2', 'L3', 'P']:
                if level not in by_level:
                    continue

                level_results = by_level[level]

                avg_latency = sum(r['latency_ms'] for r in level_results) / len(level_results)
                avg_energy = sum(r['energy_joule'] for r in level_results) / len(level_results)
                avg_prompt_tokens = sum(r['prompt_tokens'] for r in level_results) / len(level_results)
                avg_output_tokens = sum(r['completion_tokens'] for r in level_results) / len(level_results)

                f.write(f"  {level}:\n")
                f.write(f"    Count: {len(level_results)}\n")
                f.write(f"    Avg Prompt Tokens: {avg_prompt_tokens:.1f}\n")
                f.write(f"    Avg Output Tokens: {avg_output_tokens:.1f}\n")
                f.write(f"    Avg Latency: {avg_latency:.2f} ms\n")
                f.write(f"    Avg Energy: {avg_energy:.4f} J\n")
                f.write(f"\n")

    print(f"  ✓ Summary report created")


def main():
    parser = argparse.ArgumentParser(
        description="Export inference responses to readable formats"
    )

    parser.add_argument(
        '--runs',
        required=True,
        help='Path to runs_llamacpp.jsonl'
    )

    parser.add_argument(
        '--outdir',
        default='exported_responses',
        help='Output directory (default: exported_responses)'
    )

    parser.add_argument(
        '--csv',
        action='store_true',
        help='Export to CSV (all responses in one file)'
    )

    parser.add_argument(
        '--txt',
        action='store_true',
        help='Export to individual text files'
    )

    parser.add_argument(
        '--compare',
        type=int,
        metavar='QUESTION_ID',
        help='Create markdown comparison for specific question'
    )

    parser.add_argument(
        '--summary',
        action='store_true',
        help='Create summary report'
    )

    parser.add_argument(
        '--all',
        action='store_true',
        help='Export all formats'
    )

    args = parser.parse_args()

    # Load results
    print("=" * 80)
    print("LOADING INFERENCE RESULTS")
    print("=" * 80)

    results = load_inference_results(args.runs)

    # Create output directory
    os.makedirs(args.outdir, exist_ok=True)

    print("\n" + "=" * 80)
    print("EXPORTING RESPONSES")
    print("=" * 80)

    # Export based on options
    if args.all or args.csv:
        csv_file = os.path.join(args.outdir, 'all_responses.csv')
        export_to_csv(results, csv_file)

    if args.all or args.txt:
        txt_dir = os.path.join(args.outdir, 'responses_by_model')
        export_to_text_files(results, txt_dir)

    if args.all or args.summary:
        summary_file = os.path.join(args.outdir, 'summary_report.txt')
        create_summary_report(results, summary_file)

    if args.compare:
        compare_file = os.path.join(args.outdir, f'comparison_Q{args.compare:03d}.md')
        export_comparison_markdown(results, compare_file, args.compare)

    # If no options specified, export all
    if not any([args.csv, args.txt, args.summary, args.compare, args.all]):
        print("\nNo export format specified, exporting all formats...")

        csv_file = os.path.join(args.outdir, 'all_responses.csv')
        export_to_csv(results, csv_file)

        txt_dir = os.path.join(args.outdir, 'responses_by_model')
        export_to_text_files(results, txt_dir)

        summary_file = os.path.join(args.outdir, 'summary_report.txt')
        create_summary_report(results, summary_file)

    print("\n" + "=" * 80)
    print("EXPORT COMPLETE")
    print("=" * 80)
    print(f"\nOutput saved to: {args.outdir}/")
    print("\nFiles created:")
    for root, dirs, files in os.walk(args.outdir):
        level = root.replace(args.outdir, '').count(os.sep)
        indent = ' ' * 2 * level
        print(f"{indent}{os.path.basename(root)}/")
        subindent = ' ' * 2 * (level + 1)
        for file in sorted(files)[:5]:  # Show first 5 files
            print(f"{subindent}{file}")
        if len(files) > 5:
            print(f"{subindent}... and {len(files) - 5} more files")


if __name__ == "__main__":
    main()
