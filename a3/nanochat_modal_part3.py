"""
Usage
-----
Full speedrun (mirrors `bash runs/speedrun.sh`):
    modal run nanochat_modal.py

Individual stages (if you want to re-run one step):
    modal run nanochat_modal.py::stage_data
    modal run nanochat_modal.py::stage_tokenizer
    modal run nanochat_modal.py::stage_pretrain
    modal run nanochat_modal.py::stage_passkey_compare

Cost reference (8×H100 at ~$31/hr for the node)
------------------------------------------------
    quick_test  d12, 8 shards    : ~15 min
    speedrun    d24, 240 shards  : ~3 hours

Notes
-----
- Modal Volumes persist data between runs, so downloaded shards and
  checkpoints survive container restarts. Stages are idempotent where
  possible (they skip work already done).
- The nanochat repo is regularly updated. If a flag name changes, check the
  matching speedrun.sh in your cloned repo and update the args
"""

import os
import subprocess
import modal
from modal import App, Image as ModalImage, Volume, Secret

# =============================================================================
# CONFIGURATION
# =============================================================================

# ── Model depth ──────────────────────────────────────────────────────────────
#   d12  ~125M params   5 min on 8xH100    good for iterating on code changes
#   d20  ~560M params   1.5 hr on 8xH100   budget speedrun (~$36)
#   d24  ~768M params   3 hr on 8xH100     
#   d26  ~1B params     6 hr on 8xH100 
#   d32  ~1.9B params   41 hr on 8xH100
DEPTH = 16

# ── Data shards ───────────────────────────────────────────────────────────────
# FineWeb-EDU is split into 1822 parquet shards, each ~250M chars / ~100MB.
# 240 shards is enough for d24. Use 450 for d26 and 800 for d32.
NUM_SHARDS = 128

# ── GPU configuration ─────────────────────────────────────────────────────────
# "H100:8" = 8 H100s, the reference configuration for the speedrun leaderboard.
# "H100:4" = 4 H100s, half the speed, same cost per GPU-hour.
# "A100:8" = 8 A100 80GBs, ~10-20% slower than H100s but sometimes cheaper.
# Single GPU works too — code auto-compensates with gradient accumulation.
GPU_PRETRAIN = "H100:8"
GPU_FINETUNE = "H100:8"   # SFT and RL don't need all 8 GPUs

# ── Device batch size ─────────────────────────────────────────────────────────
# Sequences per GPU per forward pass. Reduce if you hit OOM.
# The training script automatically adjusts gradient accumulation to compensate
# so the effective total batch size (524,288 tokens default) stays the same.
#
#   H100 80GB: 32 fits for d24, 16 for d26, 8 for d32
#   A100 80GB: same as H100
#   A100 40GB: use 16 for d24
DEVICE_BATCH_SIZE = 16    # d24 at 16 is safe; 32 may OOM on some H100 configs

# ── WandB ─────────────────────────────────────────────────────────────────────
# Set to "dummy" to disable WandB logging
WANDB_RUN = "8h100_d16_ctx"

# ── Volume mount path ──────────────────────────────────────────────────────────
# All cached data (shards, tokenizer, checkpoints, eval bundle) lives here
# inside the Modal Volume. nanochat defaults to ~/.cache/nanochat; symlink
# the path to here so the code finds everything without modification.
VOLUME_MOUNT = "/vol"
NANOCHAT_CACHE = f"{VOLUME_MOUNT}/nanochat_cache"  # mirrors $NANOCHAT_BASE_DIR
BASE_DIR = "/data/.cache/nanochat" 

# ── Timeout ───────────────────────────────────────────────────────────────────
# Modal kills a container after this many seconds of wall-clock time.
# The pretrain timeout must be longer than your expected training time.
PRETRAIN_TIMEOUT_SEC  = 60 * 60 * 6    # 6 hours
FINETUNE_TIMEOUT_SEC  = 60 * 60 * 2    # 2 hours (SFT and RL are much shorter)
DOWNLOAD_TIMEOUT_SEC  = 60 * 90        # 90 min for shard download

# ── Derived: GPU count ────────────────────────────────────────────────────────
# Extract the integer from "H100:8" -> 8.  Used to pass --nproc_per_node.
_N_PRETRAIN_GPUS  = int(GPU_PRETRAIN.split(":")[1]) if ":" in GPU_PRETRAIN else 1
_N_FINETUNE_GPUS  = int(GPU_FINETUNE.split(":")[1]) if ":" in GPU_FINETUNE else 1

# Eval bundle URL (fixed, hosted by Karpathy)
EVAL_BUNDLE_URL = "https://karpathy-public.s3.us-west-2.amazonaws.com/eval_bundle.zip"

# Identity conversations for SFT personality layer
IDENTITY_JSONL_URL = (
    "https://karpathy-public.s3.us-west-2.amazonaws.com/identity_conversations.jsonl"
)

# =============================================================================
# MODAL PRIMITIVES — App, Volume, Secret, Image
# =============================================================================

app = modal.App("nanochat-d16-speedrun-ctx")

# Persistent network volume: survives container shutdowns.
# Stores downloaded shards (~24GB), tokenizer, checkpoints, eval bundle.
# First time you run, Modal creates this automatically.
volume = Volume.from_name("nanochat-d16-vol-ctx", create_if_missing=True)

# Secret: injects WANDB_API_KEY and HF_TOKEN as env vars inside containers.
# Create once with:
#   modal secret create nanochat-secrets WANDB_API_KEY=... HF_TOKEN=hf_...
secret = Secret.from_name("nanochat-secrets")

# Container image -- built once, cached by Modal until you change it.
# Mirrors the environment setup block at the top of speedrun.sh:
#   command -v uv || curl -LsSf https://astral.sh/uv/install.sh | sh
#   uv sync
#   maturin develop --release --manifest-path rustbpe/Cargo.toml
image = (
    # NVIDIA CUDA 12.8 with Python 3.11
    ModalImage.from_registry("nvidia/cuda:12.8.1-devel-ubuntu24.04", add_python="3.11")

    # System dependencies
    .apt_install("git", "build-essential", "curl", "wget", "unzip")

    # Copy nanochat repo into the image
    # .add_local_dir(local_path="./nanochat", remote_path="/root/nanochat", copy=True)
    .add_local_dir(local_path="./nanochat", remote_path="/root/nanochat", copy=True, ignore=[".venv", "**/.venv"])
    .workdir("/root/nanochat")

    # Install Rust and uv
    .run_commands(
        "curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y",
        "echo 'source $HOME/.cargo/env' >> $HOME/.bashrc",
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
        "echo 'export PATH=\"$HOME/.cargo/bin:$PATH\"' >> $HOME/.bashrc",
        "bash -c 'source $HOME/.cargo/env'",
    )
    .pip_install("uv")
    # Environment variables
    .env({
        "OMP_NUM_THREADS": "1",
        "NANOCHAT_BASE_DIR": "/data/.cache/nanochat",
        "HF_HOME": "/data/.cache/huggingface",
    })
    .run_commands("ls /root/nanochat/.venv/bin/python || echo 'VENV NOT FOUND'")
    .run_commands(
        "cd /root/nanochat && uv sync --extra gpu --no-install-project",
    )
)

# =============================================================================
# HELPERS
# =============================================================================

def _python(module: str, args: list | None = None, *, cwd: str = "/root/nanochat") -> None:
    """Run `python -m {module} [args]` -- for non-distributed scripts."""
    args = args or []
    cmd = f"cd {cwd} && uv run python -m {module} {' '.join(args)}"
    _run(cmd)


def _torchrun(module: str, args: list | None = None, *, nproc: int) -> None:
    """
    Run a nanochat training script under torchrun for multi-GPU distributed execution.

    Mirrors the pattern used throughout speedrun.sh:
        torchrun --standalone --nproc_per_node=$NPROC_PER_NODE -m {module} -- {args}

    torchrun spawns `nproc` processes (one per GPU), assigns each a local rank,
    and sets up NCCL for gradient synchronisation across GPUs.
    --standalone means single-node (no multi-machine rendezvous server needed).
    The -- separates torchrun's own flags from the script's argument parser.
    """
    args = args or []
    args_str = (" -- " + " ".join(args)) if args else ""
    cmd = (
        f"cd /root/nanochat && "
        f"uv run torchrun --standalone --nproc_per_node={nproc} -m {module}{args_str}"
    )
    print(cmd)
    _run(cmd)


def _run(cmd: str) -> None:
    """Shell out to bash, stream stdout/stderr, and raise on failure."""
    print(f"\n>>>  {cmd}\n")
    result = subprocess.run(["bash", "-c", cmd], check=False)
    if result.returncode != 0:
        raise RuntimeError(f"Command exited with code {result.returncode}:\n  {cmd}")


# def _setup_base_dir():
#     os.makedirs(BASE_DIR, exist_ok=True)
#     os.makedirs(f"{BASE_DIR}/base_data", exist_ok=True)
#     os.makedirs(f"{BASE_DIR}/tokenizer", exist_ok=True)
#     os.makedirs(f"{BASE_DIR}/checkpoints", exist_ok=True)
#     os.makedirs(f"{BASE_DIR}/eval_bundle", exist_ok=True)
#     os.makedirs(f"{BASE_DIR}/report", exist_ok=True)

def _setup_cache() -> None:
    """
    Create cache directories and symlink ~/.cache/nanochat -> the volume.

    nanochat hardcodes $NANOCHAT_BASE_DIR (defaulting to ~/.cache/nanochat) as
    the root for all its output: data shards, the tokenizer, checkpoints,
    the eval bundle, and the markdown report.  By symlinking that path to
    our persistent Modal Volume, everything survives across container restarts.

    speedrun.sh:
        export NANOCHAT_BASE_DIR="$HOME/.cache/nanochat"
        mkdir -p $NANOCHAT_BASE_DIR
    """
    # _setup_base_dir()
    os.makedirs(NANOCHAT_CACHE, exist_ok=True)

    if not os.path.lexists(BASE_DIR):
        os.makedirs("/data/.cache/", exist_ok=True)
        os.symlink(NANOCHAT_CACHE, BASE_DIR)
        print(f"Symlinked {BASE_DIR} -> {NANOCHAT_CACHE}")
    else:
        print(f"Cache symlink already exists: {BASE_DIR}")


def _curl(url: str, dest: str) -> None:
    """Download a file with curl, skipping if already present."""
    if os.path.exists(dest):
        print(f"Already cached, skipping: {dest}")
        return
    _run(f"curl -L -o {dest} {url}")


# =============================================================================
# STAGE 0: DATA DOWNLOAD
# =============================================================================

@app.function(
    image=image,
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    cpu=8,
    memory=16384,
    timeout=DOWNLOAD_TIMEOUT_SEC,
)
def stage_data(num_shards: int = NUM_SHARDS) -> None:
    """
    Download FineWeb-EDU dataset shards (CPU-only, run once).

    speedrun.sh:
        python -m nanochat.dataset -n 240

    Each shard is one parquet file of ~250M chars / ~100MB of high-quality
    educational web text, re-packaged by Karpathy from HuggingFace.
    nanochat.dataset parallelises the download internally and skips shards
    that are already present on disk -- this stage is idempotent.

    240 shards = ~24GB = enough data for a d24 model at the default
    tokens:params ratio (~10x Chinchilla-optimal).
    """
    _setup_cache()
    print(f"Downloading {num_shards} FineWeb-EDU shards...")
    _python("nanochat.dataset", [f"-n {num_shards}"])
    volume.commit()
    print(f"Done: {num_shards} shards downloaded.")


# =============================================================================
# STAGE 1: TOKENIZER TRAINING
# =============================================================================

@app.function(
    image=image,
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    gpu="H100:1",
    timeout=60 * 30,
)
def stage_tokenizer() -> None:
    """
    Train a custom BPE tokenizer on 2B characters of FineWeb-EDU.

    speedrun.sh:
        python -m scripts.tok_train --max-chars=2000000000
        python -m scripts.tok_eval

    The tokenizer is implemented in Rust (rustbpe/) for speed and wrapped in
    a Python API in nanochat/tokenizer.py. It uses the same algorithm as GPT-4:
    regex pre-splitting followed by byte-level BPE. The default vocab size is
    2^16 = 65,536 tokens (9 are reserved as special chat tokens like
    <|user_start|>, <|assistant_start|>, etc.).

    tok_eval prints the compression ratio (should be ~4.8 chars/token, beating
    GPT-2's ~3.9 chars/token).

    This stage takes ~1-2 minutes and only needs to run once.
    """
    _setup_cache()

    tokenizer_path = os.path.join(NANOCHAT_CACHE, "tokenizer.model")
    if os.path.exists(tokenizer_path):
        print("Tokenizer already trained. Skipping tok_train.")
    else:
        print("Training tokenizer on 2B characters...")
        # speedrun.sh: python -m scripts.tok_train --max-chars=2000000000
        _python("scripts.tok_train", ["--max-chars=2000000000"])
        volume.commit()

    # speedrun.sh: python -m scripts.tok_eval
    print("Evaluating tokenizer compression ratio...")
    _python("scripts.tok_eval")
    print("Tokenizer ready.")


# =============================================================================
# STAGE 2: BASE MODEL PRETRAINING
# =============================================================================

@app.function(
    image=image,
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    gpu=GPU_PRETRAIN,
    timeout=PRETRAIN_TIMEOUT_SEC,
)
def stage_pretrain(
    depth: int = DEPTH,
    device_batch_size: int = DEVICE_BATCH_SIZE,
    wandb_run: str = WANDB_RUN,
    max_seq_len: int = 2048,
    model_tag: str | None = None,
    resume_from_step: int = -1,
    num_iterations: int = -1,
    core_metric_every: int = -1,
) -> None:
    """
    Pretrain the base GPT model on FineWeb-EDU from random initialization.

    speedrun.sh:
        python -m nanochat.report reset
        torchrun --standalone --nproc_per_node=8 -m scripts.base_train -- \\
            --depth=20 \\
            --device-batch-size=16 \\
            --run=$WANDB_RUN

    This is the most compute-intensive stage. The training loop in
    scripts/base_train.py implements:
        - Chinchilla-optimal token budget derived from depth
        - Muon optimizer for weight matrices, AdamW for embeddings
        - BOS-aligned BestFit-Crop data packing (no midtraining)
        - Cosine LR warmup + linear warmdown (50% of training)
        - Gradient accumulation if device_batch_size * n_gpus < target batch

    Flags:
        --depth               Transformer depth; controls all other hparams
        --device-batch-size   Sequences per GPU per step (reduce if OOM)
        --run                 WandB run name ("dummy" to disable logging)
        --save-every          Checkpoint every N steps (resume-friendly)
    """
    _setup_cache()

    # speedrun.sh: python -m nanochat.report reset
    # Resets the markdown report file and writes system info + run timestamp.
    print("Resetting training report...")
    _python("nanochat.report", ["reset"])

    print(
        f"Starting pretraining: depth={depth}, "
        f"device_batch_size={device_batch_size}, "
        f"nproc={_N_PRETRAIN_GPUS}, run={wandb_run}"
    )

    # speedrun.sh: torchrun --standalone --nproc_per_node=$NPROC_PER_NODE
    #              -m scripts.base_train -- --depth=24 --device-batch-size=16 --run=...

    args = [
        f"--depth={depth}",
        f"--device-batch-size={device_batch_size}",
        f"--run={wandb_run}",
        f"--max-seq-len={max_seq_len}",
        f"--save-every=250",
        f"--core-metric-every={core_metric_every}",
    ]

    if model_tag is not None:
        args.append(f"--model-tag={model_tag}")

    if resume_from_step != -1:
        args.append(f"--resume-from-step={resume_from_step}")

    if num_iterations > 0:
        args.append(f"--num-iterations={num_iterations}")

    _torchrun("scripts.base_train", args, nproc=_N_PRETRAIN_GPUS)

    volume.commit()
    print("Pretraining complete.")


# =============================================================================
# STAGE 3: PASSKEY EVALUTATION
# =============================================================================

@app.function(
    image=image,
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    gpu="H100:1",          # single GPU is enough for eval
    timeout=60 * 60 * 2,   # 2 hours
)
def stage_passkey_eval(
    step: int | None = None,
    model_tag: str = "d16_ctx",
    context_lengths: str = "128,256,384,512,768,1024,1536,2048",
    samples_per_length: int = 128,
    depth_bins: int = 8,
    seed: int = 42,
    override_seq_len: int = 2048,
) -> None:
    """
    Evaluate a single checkpoint on passkey retrieval at multiple context lengths.
    
    The script scripts/passkey_eval.py must already exist in your nanochat/ directory.
    """
    _setup_cache()

    step_str = f"--step={step}" if step is not None else ""
    
    # Single-GPU: use python directly (no torchrun needed for eval)
    args = [
        f"--model-tag={model_tag}",
        step_str,
        f"--context-lengths={context_lengths}",
        f"--samples-per-length={samples_per_length}",
        f"--depth-bins={depth_bins}",
        f"--seed={seed}",
        f"--override-seq-len={override_seq_len}",
    ]
    args = [a for a in args if a]  # remove empty strings
    
    _python("scripts.passkey_eval", args)
    volume.commit()


# --- Stage: Run both checkpoints and compare ---

@app.function(
    image=image,
    secrets=[secret],
    volumes={VOLUME_MOUNT: volume},
    gpu="H100:1",
    timeout=60 * 60 * 4,   # 4 hours for both evals
)
def stage_passkey_compare(
    model_tag: str = "d16_ctx",
    step1: int = 1500,
    step2: int = 2500,
    context_lengths: str = "128,256,384,512,768,1024,1536,2048",
    samples_per_length: int = 128,
    depth_bins: int = 8,
    seed: int = 42,
) -> None:
    """
    Evaluate both checkpoints and print a side-by-side comparison.
    """
    _setup_cache()

    base_args = [
        f"--model-tag={model_tag}",
        f"--context-lengths={context_lengths}",
        f"--samples-per-length={samples_per_length}",
        f"--depth-bins={depth_bins}",
        f"--seed={seed}",
        f"--override-seq-len=2048",
    ]

    # --- Checkpoint 1 ---
    print(f"\n{'='*60}")
    print(f"Evaluating Checkpoint 1: step={step1} (trained at seq_len=512)")
    print(f"{'='*60}")
    ckpt1_output = f"{NANOCHAT_CACHE}/passkey_eval/ckpt1_step{step1}.json"
    _python("scripts.passkey_eval", base_args + [
        f"--step={step1}",
        f"--output={ckpt1_output}",
    ])

    # --- Checkpoint 2 ---
    print(f"\n{'='*60}")
    print(f"Evaluating Checkpoint 2: step={step2} (continued at seq_len=2048)")
    print(f"{'='*60}")
    ckpt2_output = f"{NANOCHAT_CACHE}/passkey_eval/ckpt2_step{step2}.json"
    _python("scripts.passkey_eval", base_args + [
        f"--step={step2}",
        f"--output={ckpt2_output}",
    ])

    # --- Comparison ---
    print(f"\n{'='*60}")
    print("Comparison")
    print(f"{'='*60}")
    _python("scripts.passkey_compare", [ckpt1_output, ckpt2_output])

    volume.commit()


# =============================================================================
# FULL SPEEDRUN PIPELINE (main entrypoint)
# =============================================================================

@app.local_entrypoint()
def main() -> None:
    """
    Run the complete speedrun pipeline, mirroring runs/speedrun.sh end-to-end.

    This is what executes when you run: modal run nanochat_modal.py

    Stage order (matches speedrun.sh top to bottom):
        0. Download FineWeb-EDU shards       (CPU, ~20 min for 240 shards)
        1. Train BPE tokenizer               (1 GPU, ~2 min)
        2. Pretrain base model               (8 GPU, ~3 hours for d24)
        3. Post-pretrain eval (loss + CORE)  (8 GPU, ~30 min)
        4. SFT + chat_eval                   (4 GPU, ~30-45 min)
        5. Chat sample                       (1 GPU, ~1 min)

    Each stage is a separate Modal function call with its own container, GPU
    allocation, and log stream. If a stage fails, re-run it individually:
        modal run nanochat_modal.py::stage_pretrain

    The optional RL stage is NOT included in the default pipeline. Run it
    manually after stage_sft if you want the math reasoning boost:
        modal run nanochat_modal.py::stage_rl
    """
    w = 64
    print("\n" + "=" * w)
    print("nanochat Speedrun -- Modal Edition")
    print(f"  Mirrors: runs/speedrun.sh")
    print(f"  depth={DEPTH}  shards={NUM_SHARDS}  gpu={GPU_PRETRAIN}  wandb={WANDB_RUN}")
    print("=" * w + "\n")

    # Stage 0: Data
    # speedrun.sh: python -m nanochat.dataset -n 240
    print("[0/6] Downloading FineWeb-EDU shards...")
    stage_data.remote(num_shards=NUM_SHARDS)

    # Stage 1: Tokenizer
    # speedrun.sh: python -m scripts.tok_train && python -m scripts.tok_eval
    print("[1/6] Training tokenizer...")
    stage_tokenizer.remote()

    # Stage 2: Pretrain
    # speedrun.sh: python -m nanochat.report reset
    #              torchrun ... -m scripts.base_train -- --depth=24 ...
    print("[2/6] Pretraining base model (the long one)...")

    # stage_pretrain.remote(depth=DEPTH, device_batch_size=DEVICE_BATCH_SIZE, wandb_run=WANDB_RUN)
    
    stage_pretrain.remote(
        depth=16,
        device_batch_size=DEVICE_BATCH_SIZE,
        wandb_run="8h100_d16_ctx512_s1",
        max_seq_len=512,
        model_tag="d16_ctx",
        num_iterations=1500,
        core_metric_every=-1,
    )

    stage_pretrain.remote(
        depth=16,
        device_batch_size=DEVICE_BATCH_SIZE,
        wandb_run="8h100_d16_ctx2048_s2",
        max_seq_len=2048,
        model_tag="d16_ctx",
        resume_from_step=1500,
        num_iterations=2500,   # total final step, not extra
        core_metric_every=-1,
    )

