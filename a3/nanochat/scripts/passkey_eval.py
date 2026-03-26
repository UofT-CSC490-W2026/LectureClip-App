"""
Passkey Retrieval Evaluation for nanochat base models.

Tests a model's ability to retrieve a short "passkey" (6-digit number) embedded
at various positions within contexts of different lengths. This is a standard
needle-in-a-haystack evaluation that directly measures effective context utilization.

Designed for BASE models (no SFT): uses completion-style prompts, not instructions.

Usage (single GPU):
    python -m scripts.passkey_eval --model-tag d16_ctx --step 1500

Usage (multi-GPU via torchrun, recommended for speed):
    torchrun --standalone --nproc_per_node=8 -m scripts.passkey_eval -- \
        --model-tag d16_ctx --step 1500

Compare two checkpoints:
    python -m scripts.passkey_eval --model-tag d16_ctx --step 1500 --output ckpt1_results.json
    python -m scripts.passkey_eval --model-tag d16_ctx --step 2500 --output ckpt2_results.json
"""

import os
import json
import time
import random
import argparse
from contextlib import nullcontext

import torch
import torch.nn.functional as F

from nanochat.common import (
    compute_init, compute_cleanup, print0,
    get_base_dir, autodetect_device_type,
)
from nanochat.checkpoint_manager import load_model
from nanochat.tokenizer import get_tokenizer

# =============================================================================
# FILLER TEXT
# =============================================================================
# Repeating filler sentences, styled as boring educational prose.
# Using many distinct sentences reduces the chance of spurious pattern matches.
# This matches the methodology from Mohtashami & Jaggi (2023) "Landmark Attention"
# and Liu et al. (2024) "Lost in the Middle".

FILLER_SENTENCES = [
    "The history of mathematics spans thousands of years and covers many different cultures around the world.",
    "Ancient civilizations developed counting systems to keep track of trade and agricultural production.",
    "The study of geometry was central to the construction of monumental architecture in Egypt and Mesopotamia.",
    "Greek philosophers made significant advances in logic, proof, and abstract reasoning.",
    "The concept of zero as a number was independently developed in several regions.",
    "Algebra emerged as a formal discipline during the Islamic Golden Age.",
    "The invention of calculus in the seventeenth century transformed the physical sciences.",
    "Statistical methods became increasingly important during the industrial revolution.",
    "The development of set theory in the late nineteenth century provided new foundations for mathematics.",
    "Computational methods have opened entirely new areas of mathematical research.",
    "Number theory has applications in modern cryptography and digital security systems.",
    "Linear algebra provides the framework for machine learning and data science algorithms.",
    "Probability theory is essential for understanding uncertainty in complex systems.",
    "Differential equations describe many physical phenomena including heat flow and wave propagation.",
    "Graph theory has applications in network analysis, transportation, and social sciences.",
    "Topology studies properties of spaces that are preserved under continuous deformations.",
    "The field of combinatorics deals with counting, arrangement, and combination of discrete objects.",
    "Mathematical optimization is used extensively in engineering, economics, and operations research.",
    "Fourier analysis decomposes signals into constituent frequencies and has wide applications.",
    "Game theory models strategic interactions between rational decision makers.",
    "Numerical analysis develops algorithms for obtaining approximate solutions to mathematical problems.",
    "Information theory quantifies the amount of information in data and communication channels.",
    "Category theory provides a unified framework for understanding mathematical structures.",
    "Measure theory generalizes the concepts of length, area, and volume to abstract settings.",
    "Functional analysis studies spaces of functions and operators acting on them.",
    "Dynamical systems theory describes how the state of a system evolves over time.",
    "Mathematical logic investigates the foundations and limits of formal reasoning.",
    "Coding theory designs error-correcting codes for reliable data transmission.",
    "Approximation theory studies how functions can be best approximated by simpler functions.",
    "The Riemann hypothesis remains one of the most famous unsolved problems in mathematics.",
    "Complex analysis extends calculus to functions of complex variables with elegant results.",
    "Representation theory studies abstract algebraic structures through linear transformations.",
]


def build_filler_tokens(tokenizer, rng, target_tokens):
    """
    Build a block of filler text that is approximately `target_tokens` tokens long.
    Uses the fixed RNG to shuffle sentences for variety.
    """
    sentences = list(FILLER_SENTENCES)
    rng.shuffle(sentences)

    # Tokenize all sentences and measure lengths
    token_blocks = []
    for s in sentences:
        token_blocks.append(tokenizer(s))

    # Repeat and concatenate until we exceed target
    filler_tokens = []
    idx = 0
    while len(filler_tokens) < target_tokens:
        filler_tokens.extend(token_blocks[idx % len(token_blocks)])
        # Add a space/newline separator token
        filler_tokens.extend(tokenizer(" "))
        idx += 1

    return filler_tokens[:target_tokens]


# =============================================================================
# PROMPT CONSTRUCTION
# =============================================================================

def make_passkey_prompt(tokenizer, rng, target_total_tokens, passkey, needle_depth):
    """
    Construct a single passkey retrieval prompt.

    Format (completion-style for base models):
        [filler A]
        The magic number is {passkey}. Please remember this number.
        [filler B]
        As stated in the text above, the magic number is

    Args:
        tokenizer: nanochat tokenizer
        rng: random.Random instance (seeded)
        target_total_tokens: target total prompt length in tokens
        passkey: string of digits, e.g. "481729"
        needle_depth: float in [0, 1], where 0 = needle at start, 1 = needle at end

    Returns:
        prompt_tokens: list[int] — the full prompt as token IDs (including BOS)
        answer_str: str — the expected answer string
    """
    # Tokenize the needle and query parts
    needle_text = f" The magic number is {passkey}. Please remember this number. "
    query_text = " As stated in the text above, the magic number is"

    needle_tokens = tokenizer(needle_text)
    query_tokens = tokenizer(query_text)
    bos_tokens = tokenizer("", prepend="<|bos|>")  # just BOS

    # Budget for filler = total - bos - needle - query
    overhead = len(bos_tokens) + len(needle_tokens) + len(query_tokens)
    filler_budget = max(target_total_tokens - overhead, 0)

    if filler_budget == 0:
        # Prompt is too short for filler; just use needle + query
        prompt_tokens = bos_tokens + needle_tokens + query_tokens
        return prompt_tokens, passkey

    # Split filler into before-needle and after-needle based on depth
    filler_before_count = int(filler_budget * needle_depth)
    filler_after_count = filler_budget - filler_before_count

    filler_before = build_filler_tokens(tokenizer, rng, filler_before_count)
    filler_after = build_filler_tokens(tokenizer, rng, filler_after_count)

    prompt_tokens = (
        bos_tokens
        + filler_before
        + needle_tokens
        + filler_after
        + query_tokens
    )

    return prompt_tokens, passkey


# =============================================================================
# GENERATION (greedy, no KV cache — simple and robust)
# =============================================================================

@torch.no_grad()
def greedy_generate(model, input_ids, max_new_tokens, device, autocast_ctx):
    """
    Simple greedy autoregressive generation.
    Works with any sequence length (no KV cache, no Engine dependency).
    Slower but guaranteed to work even when seq_len doesn't match training.
    """
    tokens = input_ids.clone()

    for _ in range(max_new_tokens):
        # Truncate to model's max sequence length if needed
        # (the model will handle positional encodings internally)
        logits = model(tokens)
        if isinstance(logits, torch.Tensor):
            next_token_logits = logits[:, -1, :]
        else:
            # In case model returns (logits, loss) tuple
            next_token_logits = logits[0][:, -1, :] if isinstance(logits, tuple) else logits[:, -1, :]

        next_token = torch.argmax(next_token_logits, dim=-1, keepdim=True)
        tokens = torch.cat([tokens, next_token], dim=1)

    return tokens


# =============================================================================
# EVALUATION LOOP
# =============================================================================

def run_passkey_eval(
    model,
    tokenizer,
    device,
    autocast_ctx,
    context_lengths=(128, 256, 384, 512, 768, 1024, 1536, 2048),
    num_samples_per_length=128,
    num_depth_bins=8,
    seed=42,
    max_gen_tokens=12,
    ddp_rank=0,
):
    """
    Run the full passkey retrieval evaluation.

    For each context length, we test `num_samples_per_length` prompts with
    needle placed at evenly-spaced depth positions (0.0, ..., 1.0).

    Returns a dict:
    {
        "context_lengths": [...],
        "accuracy_by_length": {length: accuracy},
        "accuracy_by_length_and_depth": {length: {depth_bin: accuracy}},
        "details": [...]  # per-example results
    }
    """
    rng = random.Random(seed)

    # Pre-compute depth bins
    depth_values = [i / (num_depth_bins - 1) for i in range(num_depth_bins)]
    samples_per_depth = num_samples_per_length // num_depth_bins

    results = {
        "context_lengths": list(context_lengths),
        "accuracy_by_length": {},
        "accuracy_by_length_and_depth": {},
        "details": [],
    }

    for ctx_len in context_lengths:
        print0(f"\n--- Context length: {ctx_len} tokens ---")
        correct = 0
        total = 0
        depth_correct = {d: 0 for d in depth_values}
        depth_total = {d: 0 for d in depth_values}

        t0 = time.time()

        for depth in depth_values:
            for sample_idx in range(samples_per_depth):
                # Generate a deterministic passkey
                passkey = f"{rng.randint(100000, 999999)}"

                # Build prompt
                prompt_tokens, answer = make_passkey_prompt(
                    tokenizer, rng, ctx_len, passkey, needle_depth=depth
                )

                actual_len = len(prompt_tokens)

                # Run model
                input_ids = torch.tensor([prompt_tokens], dtype=torch.long, device=device)

                with autocast_ctx:
                    output_ids = greedy_generate(
                        model, input_ids, max_gen_tokens, device, autocast_ctx
                    )

                # Decode generated tokens (only the new ones)
                gen_tokens = output_ids[0, len(prompt_tokens):].tolist()
                gen_text = tokenizer.decode(gen_tokens).strip()

                # Check if the passkey appears in the generated text
                is_correct = answer in gen_text

                if ddp_rank == 0:
                    results["details"].append({
                        "context_length": ctx_len,
                        "actual_tokens": actual_len,
                        "needle_depth": depth,
                        "passkey": passkey,
                        "generated": gen_text[:50],
                        "correct": is_correct,
                    })

                if is_correct:
                    correct += 1
                    depth_correct[depth] += 1

                total += 1
                depth_total[depth] += 1

        elapsed = time.time() - t0
        accuracy = correct / total if total > 0 else 0.0
        results["accuracy_by_length"][ctx_len] = accuracy

        depth_acc = {}
        for d in depth_values:
            depth_acc[f"{d:.2f}"] = (
                depth_correct[d] / depth_total[d] if depth_total[d] > 0 else 0.0
            )
        results["accuracy_by_length_and_depth"][ctx_len] = depth_acc

        print0(
            f"  Accuracy: {correct}/{total} = {accuracy:.3f} "
            f"({elapsed:.1f}s)"
        )
        for d_str, d_acc in depth_acc.items():
            print0(f"    depth={d_str}: {d_acc:.3f}")

    return results


# =============================================================================
# MAIN
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Passkey Retrieval Evaluation")
    parser.add_argument(
        "--model-tag", type=str, default=None,
        help="nanochat model tag (checkpoint directory name)"
    )
    parser.add_argument(
        "--step", type=int, default=None,
        help="Checkpoint step to load (default: latest)"
    )
    parser.add_argument(
        "--context-lengths", type=str, default="128,256,384,512,768,1024,1536,2048",
        help="Comma-separated context lengths to test"
    )
    parser.add_argument(
        "--samples-per-length", type=int, default=128,
        help="Number of evaluation samples per context length"
    )
    parser.add_argument(
        "--depth-bins", type=int, default=8,
        help="Number of needle depth positions to test"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Random seed for deterministic prompt generation"
    )
    parser.add_argument(
        "--max-gen-tokens", type=int, default=12,
        help="Max tokens to generate after the prompt"
    )
    parser.add_argument(
        "--override-seq-len", type=int, default=2048,
        help="Override model sequence_len to allow testing beyond training length. "
             "Set to 0 to use the model's native sequence_len."
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Path to write JSON results (default: auto-named in base_dir)"
    )
    parser.add_argument(
        "--device-type", type=str, default="",
        help="cuda|cpu|mps (empty = autodetect)"
    )
    args = parser.parse_args()

    context_lengths = [int(x) for x in args.context_lengths.split(",")]

    # --- Setup ---
    device_type = autodetect_device_type() if args.device_type == "" else args.device_type
    ddp, ddp_rank, ddp_local_rank, ddp_world_size, device = compute_init(device_type)
    autocast_ctx = (
        torch.amp.autocast(device_type=device_type, dtype=torch.bfloat16)
        if device_type == "cuda"
        else nullcontext()
    )

    # --- Load model ---
    print0(f"Loading model: tag={args.model_tag}, step={args.step}")
    model, tokenizer, meta = load_model(
        "base", device, phase="eval",
        model_tag=args.model_tag, step=args.step,
    )

    native_seq_len = meta["model_config"]["sequence_len"]
    print0(f"Model native sequence_len: {native_seq_len}")

    # Override sequence_len if requested (needed to test ckpt1 at longer contexts)
    if args.override_seq_len > 0 and args.override_seq_len != native_seq_len:
        print0(
            f"Overriding model sequence_len: {native_seq_len} -> {args.override_seq_len}"
        )
        model.config.sequence_len = args.override_seq_len
        # Re-initialize rotary embeddings for the new sequence length
        # (RoPE frequencies are precomputed; we need them for longer positions)
        if hasattr(model, '_init_rope') or hasattr(model, 'init_rope'):
            # Try to re-init RoPE if the model exposes such a method
            try:
                model.init_weights()  # nanochat re-inits RoPE in init_weights
                # Reload the state dict on top (init_weights randomizes weights)
                from nanochat.checkpoint_manager import load_checkpoint
                base_dir = get_base_dir()
                checkpoint_dir = os.path.join(
                    base_dir, "checkpoints", args.model_tag or ""
                )
                step_to_load = args.step or meta["step"]
                model_data, _, _ = load_checkpoint(
                    checkpoint_dir, step_to_load, device, load_optimizer=False
                )
                model.load_state_dict(model_data, strict=True, assign=True)
                del model_data
                print0("Re-initialized RoPE and reloaded weights for extended context.")
            except Exception as e:
                print0(f"Warning: Could not re-init RoPE: {e}")
                print0("Proceeding with original embeddings (may extrapolate).")

    model_name = f"{args.model_tag or 'default'}_step{meta['step']}"
    print0(f"Evaluating: {model_name}")
    print0(f"Context lengths: {context_lengths}")
    print0(f"Samples per length: {args.samples_per_length}")
    print0(f"Depth bins: {args.depth_bins}")
    print0(f"Seed: {args.seed}")

    # --- Run eval ---
    results = run_passkey_eval(
        model=model,
        tokenizer=tokenizer,
        device=device,
        autocast_ctx=autocast_ctx,
        context_lengths=context_lengths,
        num_samples_per_length=args.samples_per_length,
        num_depth_bins=args.depth_bins,
        seed=args.seed,
        max_gen_tokens=args.max_gen_tokens,
        ddp_rank=ddp_rank,
    )

    # Add metadata
    results["model_tag"] = args.model_tag
    results["step"] = meta["step"]
    results["native_seq_len"] = native_seq_len
    results["override_seq_len"] = args.override_seq_len
    results["seed"] = args.seed
    results["samples_per_length"] = args.samples_per_length
    results["depth_bins"] = args.depth_bins

    # --- Save results ---
    if ddp_rank == 0:
        if args.output:
            output_path = args.output
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
        else:
            base_dir = get_base_dir()
            eval_dir = os.path.join(base_dir, "passkey_eval")
            os.makedirs(eval_dir, exist_ok=True)
            output_path = os.path.join(
                eval_dir, f"passkey_{model_name}.json"
            )

        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
        print0(f"\nResults written to: {output_path}")

        # --- Print summary table ---
        print0("\n" + "=" * 70)
        print0(f"PASSKEY RETRIEVAL SUMMARY — {model_name}")
        print0(f"  (native seq_len={native_seq_len}, "
               f"override={args.override_seq_len})")
        print0("=" * 70)
        print0(f"{'Context':>10} | {'Accuracy':>10} | Depth breakdown")
        print0("-" * 70)
        for ctx_len in context_lengths:
            acc = results["accuracy_by_length"].get(ctx_len, 0)
            depth_str = "  ".join(
                f"{d}:{a:.2f}"
                for d, a in results["accuracy_by_length_and_depth"]
                .get(ctx_len, {})
                .items()
            )
            marker = " *" if ctx_len > native_seq_len else ""
            print0(f"{ctx_len:>10} | {acc:>10.3f} | {depth_str}{marker}")
        print0("-" * 70)
        print0("(* = beyond native training sequence length)")

    compute_cleanup()


if __name__ == "__main__":
    main()