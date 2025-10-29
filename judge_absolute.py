"""
LLM-as-Judge Absolute Scoring
Evaluates each output independently with a numerical score.
More efficient and intuitive than pairwise comparison.
"""

import argparse
import json
import csv
import os
import time
from typing import List, Dict, Optional
from pathlib import Path
import requests


JUDGE_SYSTEM_PROMPT = """You are an expert evaluator assessing the quality of AI-generated responses.

Evaluate the response based on these criteria:
1. **Factuality** (0-2.5 points): Accuracy and correctness of information
2. **Helpfulness** (0-2.5 points): How well it addresses the user's needs
3. **Structure** (0-2.5 points): Organization, clarity, and logical flow
4. **Conciseness** (0-2.5 points): Efficiency without sacrificing completeness

Return a JSON object with:
- "factuality": score (0-2.5)
- "helpfulness": score (0-2.5)
- "structure": score (0-2.5)
- "conciseness": score (0-2.5)
- "total": sum of all scores (0-10)
- "reasoning": brief explanation (1-2 sentences)

Example output:
{
  "factuality": 2.0,
  "helpfulness": 2.5,
  "structure": 2.0,
  "conciseness": 1.5,
  "total": 8.0,
  "reasoning": "The response is accurate and helpful but somewhat verbose."
}"""


def load_question_data(questions_file: str) -> Dict[int, Dict]:
    """Load original questions from JSONL file."""
    questions = {}

    with open(questions_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                data = json.loads(line)
                qid = data['question_id']
                questions[qid] = data

    print(f"Loaded {len(questions)} questions from {questions_file}")
    return questions


def load_inference_results(jsonl_file: str) -> List[Dict]:
    """Load inference results from JSONL file."""
    results = []

    with open(jsonl_file, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    return results


def organize_results_by_model(results: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Organize results by model.

    Returns:
        {model_id: [result_dict, ...]}
    """
    organized = {}

    for result in results:
        model_id = result['model_id']

        if model_id not in organized:
            organized[model_id] = []

        organized[model_id].append(result)

    return organized


def call_judge_api(
    api_url: str,
    api_key: str,
    question: str,
    response: str,
    judge_model: str = "gpt-4o",
    temperature: float = 0.0,
    max_retries: int = 3,
    sleep_time: float = 0.2
) -> Dict:
    """
    Call LLM-as-Judge API to score a single response.

    Args:
        api_url: API endpoint URL
        api_key: API key
        question: Original question
        response: AI response to evaluate
        judge_model: Model to use for judging
        temperature: Sampling temperature
        max_retries: Maximum retry attempts

    Returns:
        Dict with scores: {factuality, helpfulness, structure, conciseness, total, reasoning}
    """
    user_prompt = f"""Question: {question}

Response to evaluate:
{response}

Please evaluate this response and return your assessment as JSON."""

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    payload = {
        "model": judge_model,
        "messages": [
            {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": temperature,
        "max_tokens": 300,
        "response_format": {"type": "json_object"}  # Force JSON output
    }

    for attempt in range(max_retries):
        try:
            response_obj = requests.post(api_url, headers=headers, json=payload, timeout=30)
            response_obj.raise_for_status()

            result = response_obj.json()
            judgment_text = result['choices'][0]['message']['content'].strip()

            # Parse JSON response
            try:
                judgment = json.loads(judgment_text)

                # Validate required fields
                required_fields = ['factuality', 'helpfulness', 'structure', 'conciseness', 'total']
                if all(field in judgment for field in required_fields):
                    return judgment
                else:
                    print(f"Warning: Missing required fields in judgment, using defaults")
                    return {
                        'factuality': 0.0,
                        'helpfulness': 0.0,
                        'structure': 0.0,
                        'conciseness': 0.0,
                        'total': 0.0,
                        'reasoning': 'Parsing error'
                    }

            except json.JSONDecodeError as e:
                print(f"Warning: Failed to parse JSON judgment: {e}")
                print(f"Raw response: {judgment_text[:200]}")

                # Fallback: try to extract total score
                import re
                match = re.search(r'"total":\s*([\d.]+)', judgment_text)
                if match:
                    total = float(match.group(1))
                    return {
                        'factuality': total / 4,
                        'helpfulness': total / 4,
                        'structure': total / 4,
                        'conciseness': total / 4,
                        'total': total,
                        'reasoning': 'Partially parsed'
                    }
                else:
                    raise

        except requests.exceptions.RequestException as e:
            print(f"API request failed (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                raise
        except Exception as e:
            print(f"Unexpected error (attempt {attempt + 1}/{max_retries}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise

    raise RuntimeError(f"Failed to get judgment after {max_retries} attempts")


def judge_all_outputs(
    results: List[Dict],
    questions: Dict[int, Dict],
    api_url: str,
    api_key: str,
    judge_model: str,
    output_csv: str,
    turn_index: int = 0,
    sleep_time: float = 0.2,
    max_retries: int = 3
):
    """
    Judge all outputs with absolute scoring.

    Args:
        results: List of inference results
        questions: Original question data
        api_url: Judge API URL
        api_key: API key
        judge_model: Judge model name
        output_csv: Output CSV file path
        turn_index: Which turn to evaluate (default: 0 = first turn)
    """
    print(f"\nJudging {len(results)} outputs...")

    # Create output directory
    os.makedirs(os.path.dirname(output_csv) or '.', exist_ok=True)

    # Open CSV for writing
    with open(output_csv, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # Write header
        writer.writerow([
            'question_id',
            'category',
            'model_id',
            'level',
            'factuality',
            'helpfulness',
            'structure',
            'conciseness',
            'total_score',
            'reasoning',
            'prompt_tokens',
            'completion_tokens',
            'latency_ms',
            'energy_joule'
        ])

        # Judge each result
        for i, result in enumerate(results, 1):
            question_id = result['question_id']
            model_id = result['model_id']
            level = result['level']
            category = result['category']
            output_text = result['output_text']

            # Get original question
            question_data = questions.get(question_id)
            if not question_data:
                print(f"  Warning: Question {question_id} not found, skipping")
                continue

            # Get question text (first turn)
            if 'turns' in question_data and len(question_data['turns']) > turn_index:
                question_text = question_data['turns'][turn_index]
            else:
                print(f"  Warning: Turn {turn_index} not found for Q{question_id}, skipping")
                continue

            try:
                # Call judge
                print(f"  [{i}/{len(results)}] Judging Q{question_id} - {model_id} - {level}")

                scores = call_judge_api(
                    api_url=api_url,
                    api_key=api_key,
                    question=question_text,
                    response=output_text,
                    judge_model=judge_model,
                    max_retries=max_retries,
                    sleep_time=sleep_time
                )

                # Write result
                writer.writerow([
                    question_id,
                    category,
                    model_id,
                    level,
                    round(scores.get('factuality', 0), 2),
                    round(scores.get('helpfulness', 0), 2),
                    round(scores.get('structure', 0), 2),
                    round(scores.get('conciseness', 0), 2),
                    round(scores.get('total', 0), 2),
                    scores.get('reasoning', ''),
                    result.get('prompt_tokens', 0),
                    result.get('completion_tokens', 0),
                    round(result.get('latency_ms', 0), 2),
                    round(result.get('energy_joule', 0), 4)
                ])

                print(f"    Score: {scores['total']:.1f}/10 - {scores.get('reasoning', '')[:50]}")

                if i % 10 == 0:
                    f.flush()  # Flush to disk periodically

                # Rate limiting
                time.sleep(sleep_time)

            except Exception as e:
                print(f"  Error judging Q{question_id} {model_id} {level}: {e}")

                # Write error row with zeros
                writer.writerow([
                    question_id,
                    category,
                    model_id,
                    level,
                    0, 0, 0, 0, 0,
                    f'Error: {str(e)[:50]}',
                    result.get('prompt_tokens', 0),
                    result.get('completion_tokens', 0),
                    round(result.get('latency_ms', 0), 2),
                    round(result.get('energy_joule', 0), 4)
                ])
                continue

    print(f"\nJudging complete! Results saved to: {output_csv}")


def main():
    parser = argparse.ArgumentParser(
        description="Evaluate LLM outputs using absolute scoring"
    )

    parser.add_argument(
        '--questions',
        required=True,
        help='Path to questions JSONL file (question.jsonl)'
    )

    parser.add_argument(
        '--runs',
        required=True,
        help='Path to inference results JSONL (runs_llamacpp.jsonl)'
    )

    parser.add_argument(
        '--model',
        default='gpt-4o',
        help='Judge model to use (default: gpt-4o)'
    )

    parser.add_argument(
        '--api_url',
        default='https://api.chatanywhere.tech/v1/chat/completions',
        help='Judge API endpoint URL (default: ChatAnywhere)'
    )

    parser.add_argument(
        '--api_key_env',
        default='sk-cSXketBCVpbr4TLY76bmr0cDjRpoOtZyOMUFYollswj3SzhM',
        help='API key OR environment variable name. If starts with "sk-", treated as direct key. (default: hardcoded key)'
    )

    parser.add_argument(
        '--out',
        default='scores_absolute.csv',
        help='Output CSV file path (default: scores_absolute.csv)'
    )

    parser.add_argument(
        '--turn',
        type=int,
        default=1,
        choices=[1, 2],
        help='Which turn to evaluate (1 or 2, default: 1)'
    )

    parser.add_argument(
        '--sleep',
        type=float,
        default=0.2,
        help='Sleep time between API calls in seconds (default: 0.2)'
    )

    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Number of retries per API call (default: 3)'
    )

    args = parser.parse_args()

    # Get API key - support both direct key and env variable
    if args.api_key_env.startswith('sk-'):
        # Direct API key provided
        api_key = args.api_key_env
        print("Using API key provided directly")
    else:
        # Environment variable name provided
        api_key = os.environ.get(args.api_key_env)
        if not api_key:
            print(f"Error: API key not found in environment variable: {args.api_key_env}")
            print(f"Tip: Either set the env variable or pass the API key directly with --api_key_env sk-...")
            exit(1)
        print(f"Using API key from environment variable: {args.api_key_env}")

    # Load data
    print("="*80)
    print("LOADING DATA")
    print("="*80)

    questions = load_question_data(args.questions)
    results = load_inference_results(args.runs)

    print(f"Loaded {len(results)} inference results")

    # Judge all outputs
    print("\n" + "="*80)
    print("JUDGING OUTPUTS (ABSOLUTE SCORING)")
    print("="*80)

    judge_all_outputs(
        results=results,
        questions=questions,
        api_url=args.api_url,
        api_key=api_key,
        judge_model=args.model,
        output_csv=args.out,
        turn_index=args.turn - 1,  # Convert to 0-based index
        sleep_time=args.sleep,
        max_retries=args.retries
    )

    print("\n" + "="*80)
    print("EVALUATION COMPLETE")
    print("="*80)
    print(f"Results saved to: {args.out}")
    print("\nOutput includes:")
    print("  - Individual scores for each criterion (0-2.5)")
    print("  - Total score (0-10)")
    print("  - Brief reasoning")
    print("  - Performance metrics (tokens, latency, energy)")


if __name__ == "__main__":
    main()
