"""
Reinforcement learning on GSM8K with configurable reward systems.

Based on Karpathy's chat_rl.py (simplified GRPO/REINFORCE), extended with
two additional reward signals:

  Reward "step":  Encourages multi-step reasoning by giving a small
      bonus for intermediate calculation steps, even when the final answer is
      wrong.  Targets "missing_step" and "wrong_approach" error categories.

  Reward "proximity":  Gives partial credit when the predicted numeric answer
      is close to the ground truth.  Targets "arithmetic_error" and
      "wrong_operation" categories.

Usage (single GPU examples):
  python -m scripts.chat_rl_custom --reward-mode=original          # Run 0 baseline
  python -m scripts.chat_rl_custom --reward-mode=step_proximity    # Run 1
  python -m scripts.chat_rl_custom --reward-mode=step              # Run 2
  python -m scripts.chat_rl_custom --reward-mode=proximity         # Run 3

Multi-GPU:
  torchrun --standalone --nproc_per_node=8 -m scripts.chat_rl_custom -- --reward-mode=step_proximity --run=run1_step_proximity
"""

import argparse
import os
import re
import math
import itertools
import wandb
import torch
import torch.distributed as dist
from nanochat.common import compute_init, compute_cleanup, print0, get_base_dir, DummyWandb, autodetect_device_type
from nanochat.checkpoint_manager import save_checkpoint, load_model
from nanochat.engine import Engine
from tasks.gsm8k import GSM8K, extract_answer
import json

# =============================================================================
# REWARD FUNCTIONS
# =============================================================================

def reward_original(conversation, generated_text, task):
    """Original binary reward: 1.0 if correct, 0.0 if wrong."""
    return task.reward(conversation, generated_text)


def reward_step(conversation, generated_text, task, alpha=0.15, target_steps=4):
    """
    Step/reasoning process reward.

    Gives a small bonus for showing intermediate calculation steps, even when
    the final answer is incorrect.  The bonus is capped so that a wrong answer
    with great reasoning is still worth less than a correct answer with none.

    Calculation "steps" are detected by counting lines that contain:
      - The <<...>> calculator tool-use pattern used in GSM8K training data
      - Arithmetic operator patterns like "3 * 5 = 15"
      - Explicit numeric intermediate results

    reward = base_reward + alpha * min(num_steps / target_steps, 1.0)

    With default alpha=0.15, a correct answer is worth 1.0-1.15 and a wrong
    answer with good reasoning is worth 0.0-0.15.  This keeps correctness
    dominant while still rewarding process.
    """
    base = task.reward(conversation, generated_text)

    # Count reasoning steps
    num_steps = 0
    # Pattern 1: <<...>> calculator tool use
    num_steps += len(re.findall(r'<<.*?>>', generated_text))
    # Pattern 2: lines with "= <number>" patterns (intermediate results)
    num_steps += len(re.findall(r'=\s*[\d,]+(?:\.\d+)?', generated_text))
    # Deduplicate: the above patterns can overlap, so cap reasonably
    # A simple heuristic: count unique "step-like" lines
    lines = generated_text.strip().split('\n')
    step_lines = 0
    for line in lines:
        line_stripped = line.strip()
        has_number = bool(re.search(r'\d', line_stripped))
        has_operator = bool(re.search(r'[+\-*/]', line_stripped))
        if has_number and has_operator and len(line_stripped) > 3:
            step_lines += 1

    # Use the max of our two counting methods
    effective_steps = max(num_steps, step_lines)

    step_ratio = min(effective_steps / target_steps, 1.0) if target_steps > 0 else 0.0
    bonus = alpha * step_ratio

    return base + bonus


def reward_proximity(conversation, generated_text, task, max_partial=0.4):
    """
    Numerical proximity reward.

    If the answer is correct: reward = 1.0 (same as original).
    If the answer is wrong but numerically close to ground truth: partial credit.
    If no answer can be extracted: reward = 0.0.

    Partial credit formula (for wrong answers):
      relative_error = |predicted - truth| / max(|truth|, 1)
      partial = max_partial * max(0, 1 - relative_error)

    This means:
      - Off by 0%  -> 0.4 partial credit (but it would be correct, so gets 1.0)
      - Off by 25% -> 0.3 partial credit
      - Off by 50% -> 0.2 partial credit
      - Off by 100% or more -> 0.0

    With max_partial=0.4, even the best partial credit is well below a correct
    answer (1.0), maintaining strong incentive for exact correctness.
    """
    base = task.reward(conversation, generated_text)
    if base > 0.5:
        return 1.0

    predicted_str = extract_answer(generated_text)
    assistant_parts = conversation["messages"][1]["content"]
    last_text_part = assistant_parts[-1]["text"]
    truth_str = extract_answer(last_text_part)

    if predicted_str is None or truth_str is None:
        return 0.0

    try:
        predicted = float(predicted_str.replace(",", ""))
        truth = float(truth_str.replace(",", ""))
    except (ValueError, TypeError):
        return 0.0

    denom = max(abs(truth), 1.0)
    relative_error = abs(predicted - truth) / denom

    partial = max_partial * max(0.0, 1.0 - relative_error)
    return partial


def compute_reward(conversation, generated_text, task, reward_mode):
    """Dispatch to the appropriate reward function(s) based on mode."""
    if reward_mode == "original":
        return reward_original(conversation, generated_text, task)
    elif reward_mode == "step":
        return reward_step(conversation, generated_text, task)
    elif reward_mode == "proximity":
        return reward_proximity(conversation, generated_text, task)
    elif reward_mode == "step_proximity":
        # Combine both: step bonus + proximity, but don't double-count the base
        base = task.reward(conversation, generated_text)
        if base > 0.5:
            # Correct answer — add step bonus on top
            r_step = reward_step(conversation, generated_text, task)
            return r_step  # already includes base + step bonus
        else:
            # Wrong answer — combine step bonus and proximity partial credit
            r_step_bonus = reward_step(conversation, generated_text, task) - base
            r_prox = reward_proximity(conversation, generated_text, task)
            return r_step_bonus + r_prox
    else:
        raise ValueError(f"Unknown reward mode: {reward_mode}")

# =============================================================================
# CLI arguments
# =============================================================================
parser = argparse.ArgumentParser(description="RL on GSM8K with configurable rewards")
parser.add_argument("--reward-mode", type=str, default="original",
                    choices=["original", "step", "proximity", "step_proximity"],
                    help="Reward mode: original | step | proximity | step_proximity")
parser.add_argument("--run", type=str, default="dummy", help="wandb run name ('dummy' disables wandb)")
parser.add_argument("--device-type", type=str, default="", help="cuda|cpu|mps (empty = autodetect)")
parser.add_argument("--model-tag", type=str, default=None, help="model tag to load from")
parser.add_argument("--model-step", type=int, default=None, help="model step to load from")
parser.add_argument("--output-tag", type=str, default=None,
                    help="Output model tag for checkpoints (default: same as model-tag)")
parser.add_argument("--num-epochs", type=int, default=1, help="number of epochs over GSM8K")
parser.add_argument("--device-batch-size", type=int, default=8, help="max batch size per forward pass")
parser.add_argument("--examples-per-step", type=int, default=16, help="total examples per optimization step")
parser.add_argument("--num-samples", type=int, default=16, help="number of samples per example/question")
parser.add_argument("--max-new-tokens", type=int, default=256, help="max tokens to generate per sample")
parser.add_argument("--temperature", type=float, default=1.0, help="sampling temperature")
parser.add_argument("--top-k", type=int, default=50, help="top-k sampling (0 = disabled)")
parser.add_argument("--embedding-lr", type=float, default=0.2, help="LR for embedding params (Adam)")
parser.add_argument("--unembedding-lr", type=float, default=0.004, help="LR for unembedding params (Adam)")
parser.add_argument("--matrix-lr", type=float, default=0.02, help="LR for matrix params (Muon)")
parser.add_argument("--weight-decay", type=float, default=0.0, help="weight decay (Adam)")
parser.add_argument("--init-lr-frac", type=float, default=0.05, help="initial LR fraction")
parser.add_argument("--eval-every", type=int, default=60, help="evaluate pass@k every N steps")
parser.add_argument("--eval-examples", type=int, default=400, help="number of examples for pass@k eval")
parser.add_argument("--save-every", type=int, default=60, help="save checkpoint every N steps")
args = parser.parse_args()
user_config = vars(args).copy()

# Derive output tag
output_tag = args.output_tag or args.model_tag

# =============================================================================
# INIT
# =============================================================================
device_type = autodetect_device_type() if args.device_type == "" else args.device_type
ddp, ddp_rank, ddp_local_rank, ddp_world_size, device = compute_init(device_type)
master_process = ddp_rank == 0

use_dummy_wandb = args.run == "dummy" or not master_process
wandb_run = DummyWandb() if use_dummy_wandb else wandb.init(
    project="nanochat-rl", name=args.run, config=user_config
)

model, tokenizer, meta = load_model("sft", device, phase="eval",
                                     model_tag=args.model_tag, step=args.model_step)
engine = Engine(model, tokenizer)

# =============================================================================
# ROLLOUT GENERATOR
# =============================================================================
train_task = GSM8K(subset="main", split="train")
val_task = GSM8K(subset="main", split="test")
num_steps = (len(train_task) // args.examples_per_step) * args.num_epochs
print0(f"Calculated number of steps: {num_steps}")
print0(f"Reward mode: {args.reward_mode}")

@torch.no_grad()
def get_batch():
    assistant_end = tokenizer.encode_special("<|assistant_end|>")
    rank_indices = range(ddp_rank, len(train_task), ddp_world_size)
    for example_idx in itertools.cycle(rank_indices):
        conversation = train_task[example_idx]
        tokens = tokenizer.render_for_completion(conversation)
        prefix_length = len(tokens)

        model.eval()
        generated_token_sequences = []
        masks = []
        num_sampling_steps = args.num_samples // args.device_batch_size
        for sampling_step in range(num_sampling_steps):
            seed = hash((step, example_idx, sampling_step)) & 0x7FFFFFFF
            generated_token_sequences_batch, masks_batch = engine.generate_batch(
                tokens,
                num_samples=args.device_batch_size,
                max_tokens=args.max_new_tokens,
                temperature=args.temperature,
                top_k=args.top_k,
                seed=seed,
            )
            generated_token_sequences.extend(generated_token_sequences_batch)
            masks.extend(masks_batch)

        rewards = []
        for sample_tokens in generated_token_sequences:
            generated_tokens = sample_tokens[prefix_length:]
            generated_text = tokenizer.decode(generated_tokens)
            reward = compute_reward(conversation, generated_text, train_task, args.reward_mode)
            rewards.append(reward)

        max_length = max(len(seq) for seq in generated_token_sequences)
        padded_generated_token_sequences = [
            seq + [assistant_end] * (max_length - len(seq))
            for seq in generated_token_sequences
        ]
        padded_masks = [mask + [0] * (max_length - len(mask)) for mask in masks]

        ids = torch.tensor(padded_generated_token_sequences, dtype=torch.long, device=device)
        mask_ids = torch.tensor(padded_masks, dtype=torch.long, device=device)
        inputs = ids[:, :-1]
        targets = ids[:, 1:].clone()
        targets[mask_ids[:, 1:] == 0] = -1
        rewards = torch.tensor(rewards, dtype=torch.float, device=device)
        mu = rewards.mean()
        advantages = rewards - mu

        # Log training rollout details
        question_text = conversation["messages"][0]["content"]
        assistant_parts = conversation["messages"][1]["content"]
        last_text_part = assistant_parts[-1]["text"]
        ground_truth = extract_answer(last_text_part)
        train_record = {
            "step": step,
            "example_idx": example_idx,
            "reward_mode": args.reward_mode,
            "question": question_text,
            "ground_truth_answer": ground_truth,
            "rewards": rewards.tolist(),
            "samples": [],
        }
        for i, seq_tokens in enumerate(generated_token_sequences):
            gen_tokens = seq_tokens[prefix_length:]
            gen_text = tokenizer.decode(gen_tokens)
            train_record["samples"].append({
                "generated_text": gen_text,
                "predicted_answer": extract_answer(gen_text),
                "reward": rewards[i].item(),
            })
        if ddp_rank == 0:
            log_name = f"rl_train_details_{args.reward_mode}.jsonl"
            train_log_path = os.path.join(get_base_dir(), log_name)
            with open(train_log_path, "a") as f:
                f.write(json.dumps(train_record) + "\n")

        yield generated_token_sequences, inputs, targets, rewards, advantages


# =============================================================================
# EVALUATION
# =============================================================================
def run_gsm8k_eval(task, tokenizer, engine,
                   max_examples=None, num_samples=1,
                   max_completion_tokens=256, temperature=0.0, top_k=50):
    max_examples = min(max_examples, len(task)) if max_examples is not None else len(task)
    for idx in range(ddp_rank, max_examples, ddp_world_size):
        conversation = task[idx]
        tokens = tokenizer.render_for_completion(conversation)
        prefix_length = len(tokens)
        assert num_samples <= args.device_batch_size
        generated_token_sequences, masks = engine.generate_batch(
            tokens,
            num_samples=num_samples,
            max_tokens=max_completion_tokens,
            temperature=temperature,
            top_k=top_k,
        )
        question_text = conversation["messages"][0]["content"]
        assistant_parts = conversation["messages"][1]["content"]
        last_text_part = assistant_parts[-1]["text"]
        ground_truth = extract_answer(last_text_part)

        outcomes = []
        for sample_tokens in generated_token_sequences:
            generated_tokens = sample_tokens[prefix_length:]
            generated_text = tokenizer.decode(generated_tokens)
            is_correct = task.evaluate(conversation, generated_text)
            predicted = extract_answer(generated_text)
            outcomes.append({
                "is_correct": is_correct,
                "generated_text": generated_text,
                "predicted_answer": predicted,
            })
        record = {
            "idx": idx,
            "question": question_text,
            "ground_truth_answer": ground_truth,
            "outcomes": outcomes,
        }
        yield record


# =============================================================================
# TRAINING LOOP
# =============================================================================
optimizer = model.setup_optimizer(
    unembedding_lr=args.unembedding_lr,
    embedding_lr=args.embedding_lr,
    matrix_lr=args.matrix_lr,
    weight_decay=args.weight_decay,
)

for group in optimizer.param_groups:
    group["lr"] = group["lr"] * args.init_lr_frac
    group["initial_lr"] = group["lr"]

def get_lr_multiplier(it):
    return 1.0 - it / num_steps

print0(f"Total sequences per step: {args.examples_per_step * args.num_samples}")
assert args.examples_per_step % ddp_world_size == 0
examples_per_rank = args.examples_per_step // ddp_world_size
print0(f"Calculated examples per rank: {examples_per_rank}")

batch_iterator = get_batch()
for step in range(num_steps):

    if step % args.eval_every == 0:
        model.eval()
        passk = torch.zeros(args.device_batch_size, device=device)
        records_iter = run_gsm8k_eval(
            val_task, tokenizer, engine,
            num_samples=args.device_batch_size,
            max_examples=args.eval_examples, temperature=1.0,
        )
        records = list(records_iter)
        for k in range(1, args.device_batch_size + 1):
            passk[k - 1] = sum(
                any(o["is_correct"] for o in r["outcomes"][:k]) for r in records
            )
        num_records = torch.tensor(len(records), dtype=torch.long, device=device)
        if ddp:
            dist.all_reduce(num_records, op=dist.ReduceOp.SUM)
            dist.all_reduce(passk, op=dist.ReduceOp.SUM)
        passk = passk / num_records.item()
        print_passk = [f"Pass@{k}: {passk[k - 1].item():.4f}"
                       for k in range(1, args.device_batch_size + 1)]
        print0(f"Step {step} | {', '.join(print_passk)}")
        log_passk = {f"pass@{k}": passk[k - 1].item()
                     for k in range(1, args.device_batch_size + 1)}
        wandb_run.log({"step": step, **log_passk})

        if master_process:
            eval_log_name = f"rl_eval_details_{args.reward_mode}.jsonl"
            eval_log_path = os.path.join(get_base_dir(), eval_log_name)
            with open(eval_log_path, "a") as f:
                for r in records:
                    r["step"] = step
                    r["reward_mode"] = args.reward_mode
                    f.write(json.dumps(r) + "\n")

    rewards_list = []
    sequence_lengths = []
    for example_step in range(examples_per_rank):
        sequences_all, inputs_all, targets_all, rewards_all, advantages_all = next(batch_iterator)
        model.train()
        assert inputs_all.size(0) % args.device_batch_size == 0
        num_passes = inputs_all.size(0) // args.device_batch_size
        for pass_idx in range(num_passes):
            b0, b1 = pass_idx * args.device_batch_size, (pass_idx + 1) * args.device_batch_size
            inputs = inputs_all[b0:b1]
            targets = targets_all[b0:b1]
            rewards = rewards_all[b0:b1]
            advantages = advantages_all[b0:b1]
            logp = -model(inputs, targets, loss_reduction='none').view_as(inputs)
            pg_obj = (logp * advantages.unsqueeze(-1)).sum()
            num_valid = (targets >= 0).sum().clamp(min=1)
            pg_obj = pg_obj / (num_valid * num_passes * examples_per_rank)
            loss = -pg_obj
            loss.backward()
            print0(f"Step {step}/{num_steps} | Example step {example_step} | "
                   f"Pass {pass_idx} | loss: {loss.item():.6f} | "
                   f"Avg reward: {rewards.mean().item()}")
        rewards_list.append(rewards_all.mean().item())
        sequence_lengths.extend(len(seq) for seq in sequences_all)

    mean_reward = sum(rewards_list) / len(rewards_list)
    mean_sequence_length = sum(sequence_lengths) / len(sequence_lengths)
    if ddp:
        mean_reward_tensor = torch.tensor(mean_reward, dtype=torch.float, device=device)
        mean_seq_len_tensor = torch.tensor(mean_sequence_length, dtype=torch.float, device=device)
        dist.all_reduce(mean_reward_tensor, op=dist.ReduceOp.AVG)
        dist.all_reduce(mean_seq_len_tensor, op=dist.ReduceOp.AVG)
        mean_reward = mean_reward_tensor.item()
        mean_sequence_length = mean_seq_len_tensor.item()
    print0(f"Step {step}/{num_steps} | Avg reward: {mean_reward} | "
           f"Avg seq len: {mean_sequence_length:.2f}")
    wandb_run.log({
        "step": step,
        "reward": mean_reward,
        "sequence_length": mean_sequence_length,
    })

    lrm = get_lr_multiplier(step)
    for group in optimizer.param_groups:
        group["lr"] = group["initial_lr"] * lrm
    optimizer.step()
    model.zero_grad(set_to_none=True)
    wandb_run.log({"step": step, "lrm": lrm})

    if master_process and ((step > 0 and step % args.save_every == 0) or step == num_steps - 1):
        base_dir = get_base_dir()
        depth = model.config.n_layer
        dirname = output_tag if output_tag else f"d{depth}"
        checkpoint_dir = os.path.join(base_dir, "chatrl_checkpoints", dirname)
        model_config_kwargs = model.config.__dict__
        save_checkpoint(
            checkpoint_dir,
            step,
            model.state_dict(),
            None,
            {"model_config": model_config_kwargs},
        )
        print(f"✅ Saved checkpoint to {checkpoint_dir}")

# =============================================================================
# REPORT
# =============================================================================
from nanochat.report import get_report
section_name = f"Chat RL ({args.reward_mode})"
get_report().log(section=section_name, data=[user_config])

wandb_run.finish()
compute_cleanup()