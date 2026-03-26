"""
Prepare additional math datasets for nanochat SFT.
Downloads MATH, AQuA-RAT, and MetaMathQA datasets from HuggingFace
and converts them to nanochat-compatible JSONL conversation format.

Usage:
    python -m scripts.prepare_math_data --output-dir /path/to/nanochat_cache

Or from within the nanochat directory:
    uv run python -m scripts.prepare_math_data --output-dir $NANOCHAT_BASE_DIR

Each output JSONL file contains one conversation per line in the format:
{
  "messages": [
    {"role": "user", "content": "..."},
    {"role": "assistant", "content": "..."}
  ]
}

This is compatible with nanochat's CustomJSON task loader.

Verified dataset details (March 2026):
---------------------------------------
  qwedsacf/competition_math   - train only, 12.5K rows  - fields: problem, level, type, solution
  Chinar/AQuA-RAT             - train only, 97.7K rows  - fields: prompt, completion
  meta-math/MetaMathQA        - train only, 395K rows   - fields: query, response, type, original_question
"""

import json
import os
import argparse
from datasets import load_dataset


def format_math_example(row):
    """
    Format a MATH (competition_math) example into a nanochat conversation.

    Fields: problem, level, type, solution
    The solution contains step-by-step LaTeX derivations with \\boxed{answer}.
    """
    problem = row["problem"].strip()
    solution = row["solution"].strip()

    return [
        {"role": "user", "content": problem},
        {"role": "assistant", "content": solution},
    ]


def format_aqua_example(row):
    """
    Format a Chinar/AQuA-RAT example into a nanochat conversation.

    Fields: prompt (question text), completion (rationale + answer)
    The prompt already contains the question; completion has the rationale.
    """
    prompt = row["prompt"].strip()
    completion = row["completion"].strip()

    return [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": completion},
    ]


def format_metamath_example(row):
    """
    Format a MetaMathQA example into a nanochat conversation.

    Fields: query, response, type, original_question
    The response contains step-by-step reasoning ending with "The answer is: X"
    """
    query = row["query"].strip()
    response = row["response"].strip()

    return [
        {"role": "user", "content": query},
        {"role": "assistant", "content": response},
    ]


def write_jsonl(data, filepath):
    """Write a list of dicts to a JSONL file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        for item in data:
            f.write(json.dumps(item) + "\n")
    print(f"  Wrote {len(data)} examples to {filepath}")


def prepare_math(output_dir, max_train=None):
    """
    Prepare the MATH dataset (qwedsacf/competition_math).

    Only has a train split with 12.5K rows. No test split available.
    We hold out the last 500 rows as a local validation set.
    """
    print("\n=== Preparing MATH dataset (qwedsacf/competition_math) ===")
    ds = load_dataset("qwedsacf/competition_math", split="train")

    # Hold out last 500 for validation since there's no test split
    total = len(ds)
    val_size = 500
    train_size = total - val_size

    train_data = []
    for i in range(train_size):
        train_data.append(format_math_example(ds[i]))
    if max_train and len(train_data) > max_train:
        train_data = train_data[:max_train]

    val_data = []
    for i in range(train_size, total):
        val_data.append(format_math_example(ds[i]))

    write_jsonl(train_data, os.path.join(output_dir, "math_train.jsonl"))
    write_jsonl(val_data, os.path.join(output_dir, "math_val.jsonl"))
    print(f"  MATH: {len(train_data)} train, {len(val_data)} val (held out)")


def prepare_aqua(output_dir, max_train=None):
    """
    Prepare the AQuA-RAT dataset (Chinar/AQuA-RAT).

    Only has a train split with 97.7K rows. No test split available.
    We hold out the last 500 rows as a local validation set.
    """
    print("\n=== Preparing AQuA-RAT dataset (Chinar/AQuA-RAT) ===")
    ds = load_dataset("Chinar/AQuA-RAT", split="train")

    total = len(ds)
    val_size = 500
    train_size = total - val_size

    train_data = []
    for i in range(train_size):
        train_data.append(format_aqua_example(ds[i]))
    if max_train and len(train_data) > max_train:
        train_data = train_data[:max_train]

    val_data = []
    for i in range(train_size, total):
        val_data.append(format_aqua_example(ds[i]))

    write_jsonl(train_data, os.path.join(output_dir, "aqua_train.jsonl"))
    write_jsonl(val_data, os.path.join(output_dir, "aqua_val.jsonl"))
    print(f"  AQuA-RAT: {len(train_data)} train, {len(val_data)} val (held out)")


def prepare_metamath(output_dir, max_train=50000):
    """
    Prepare a subsample of MetaMathQA (meta-math/MetaMathQA).

    Only has a train split with 395K rows. We subsample to keep balanced.
    Default: 50K rows. No separate validation set needed (it augments GSM8K/MATH).
    """
    print("\n=== Preparing MetaMathQA dataset (meta-math/MetaMathQA) ===")
    ds = load_dataset("meta-math/MetaMathQA", split="train")

    train_data = []
    for i in range(len(ds)):
        train_data.append(format_metamath_example(ds[i]))
        if max_train and len(train_data) >= max_train:
            break

    write_jsonl(train_data, os.path.join(output_dir, "metamath_train.jsonl"))
    print(f"  MetaMathQA: {len(train_data)} train (subsampled from {len(ds)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Prepare math datasets for nanochat SFT"
    )
    parser.add_argument("--output-dir", type=str, required=True,
                        help="Directory to write JSONL files (e.g., $NANOCHAT_BASE_DIR)")
    parser.add_argument("--math-max-train", type=int, default=None,
                        help="Max MATH training examples (default: all ~12K)")
    parser.add_argument("--aqua-max-train", type=int, default=25000,
                        help="Max AQuA training examples (default: 25000)")
    parser.add_argument("--metamath-max-train", type=int, default=25000,
                        help="Max MetaMathQA training examples (default: 25000)")
    args = parser.parse_args()

    prepare_math(args.output_dir, args.math_max_train)
    prepare_aqua(args.output_dir, args.aqua_max_train)
    prepare_metamath(args.output_dir, args.metamath_max_train)

    print("\n=== All datasets prepared! ===")
    print(f"Files written to: {args.output_dir}")
    print("\nGenerated files:")
    print(f"  math_train.jsonl     - MATH competition problems (~12K)")
    print(f"  math_val.jsonl       - MATH held-out validation (500)")
    print(f"  aqua_train.jsonl     - AQuA-RAT algebra problems (~97K)")
    print(f"  aqua_val.jsonl       - AQuA-RAT held-out validation (500)")
    print(f"  metamath_train.jsonl - MetaMathQA subsampled ({args.metamath_max_train})")
    print("\nUse these with CustomJSON in your SFT script.")