#!/usr/bin/env python3
"""Profile Python hotspots in the process-results pipeline."""

import argparse
import cProfile
import json
import os
import pstats
import sys
from contextlib import contextmanager
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PROCESS_RESULTS_DIR = REPO_ROOT / "src" / "lambdas" / "process-results"
MODEL_ID = "amazon.titan-embed-text-v2:0"
SOURCE_URI = "s3://test-bucket/2024-01/user1/lecture.mp4"
EMBEDDING_DIM = 1024


def _set_env_defaults():
    os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    os.environ.setdefault("AURORA_CLUSTER_ARN", "arn:aws:rds:us-east-1:123456789012:cluster:test")
    os.environ.setdefault("AURORA_SECRET_ARN", "arn:aws:secretsmanager:us-east-1:123456789012:secret:test")
    os.environ.setdefault("AURORA_DB_NAME", "lectureclip")


_set_env_defaults()
sys.path.insert(0, str(PROCESS_RESULTS_DIR))

import aurora_utils  # noqa: E402
import bedrock_utils  # noqa: E402
import transcript_utils  # noqa: E402


def build_transcribe_items(sentences=300, words_per_sentence=12):
    items = []
    start_time = 0.0
    speaker = "spk_0"

    for sentence_idx in range(sentences):
        if sentence_idx and sentence_idx % 75 == 0:
            speaker = "spk_1" if speaker == "spk_0" else "spk_0"

        for word_idx in range(words_per_sentence):
            items.append({
                "type": "pronunciation",
                "alternatives": [{"content": f"word{sentence_idx}_{word_idx}"}],
                "start_time": f"{start_time:.2f}",
                "end_time": f"{start_time + 0.24:.2f}",
                "speaker_label": speaker,
            })
            start_time += 0.27

        items.append({
            "type": "punctuation",
            "alternatives": [{"content": "."}],
        })

    return items


def build_segments(count=600):
    return [
        (idx * 6, f"spk_{idx % 2}", f"Segment {idx} " + ("content " * 16).strip() + ".")
        for idx in range(count)
    ]


def build_embedding_records(segments):
    vector = [round(0.001 * ((idx % 7) + 1), 6) for idx in range(EMBEDDING_DIM)]
    return [
        {
            "id": f"embedding-{idx}",
            "embedding": vector,
            "text": text,
            "start_second": start_second,
            "speaker": speaker,
            "source": "lecture.mp4",
            "source_uri": SOURCE_URI,
            "model_id": MODEL_ID,
            "created_at": "2026-03-21T00:00:00+00:00",
        }
        for idx, (start_second, speaker, text) in enumerate(segments)
    ]


def _fake_embed_text(_text, _model_id, _embedding_dim):
    return [0.125] * EMBEDDING_DIM


def _fake_execute(_sql, _params=None):
    return None


@contextmanager
def patched_dependencies():
    original_embed_text = bedrock_utils.embed_text
    original_execute = aurora_utils._execute
    bedrock_utils.embed_text = _fake_embed_text
    aurora_utils._execute = _fake_execute
    try:
        yield
    finally:
        bedrock_utils.embed_text = original_embed_text
        aurora_utils._execute = original_execute


def _target_stats(stats, func_name):
    matches = []
    for (filename, line_no, name), stat in stats.stats.items():
        if name == func_name:
            matches.append((filename, line_no, stat))
    if not matches:
        return None
    _, line_no, (primitive_calls, total_calls, total_time, cumulative_time, _) = matches[0]
    return {
        "line": line_no,
        "primitive_calls": primitive_calls,
        "total_calls": total_calls,
        "total_time": total_time,
        "cumulative_time": cumulative_time,
    }


def _run_profile(fn, repeat):
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeat):
        fn()
    profiler.disable()
    return pstats.Stats(profiler)


def _print_result(name, repeat, workload, stats):
    target = _target_stats(stats, name)
    print(f"## {name}")
    print(f"repeat: {repeat}")
    print(f"workload: {workload}")
    if target is None:
        print("target_stats: missing")
    else:
        per_call_total_ms = (target["total_time"] / repeat) * 1000
        per_call_cum_ms = (target["cumulative_time"] / repeat) * 1000
        print(f"target_total_ms_per_call: {per_call_total_ms:.3f}")
        print(f"target_cumulative_ms_per_call: {per_call_cum_ms:.3f}")
        print(f"target_total_calls: {target['total_calls']}")
    print("top_by_cumulative:")
    stats.sort_stats("cumulative").print_stats(8)
    print("top_by_tottime:")
    stats.sort_stats("tottime").print_stats(8)
    print()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        choices=[
            "_process_items",
            "_combine_by_speaker",
            "generate_text_embeddings",
            "insert_segments",
            "insert_embeddings",
            "all",
        ],
        default="all",
    )
    args = parser.parse_args()

    transcribe_items = build_transcribe_items()
    processed_items = transcript_utils._process_items(transcribe_items)
    segments = build_segments()
    segment_records = [
        (f"segment-{idx}", float(start_second), float(start_second + 6), text)
        for idx, (start_second, _speaker, text) in enumerate(segments)
    ]
    embedding_records = build_embedding_records(segments)

    workloads = {
        "_process_items": {
            "repeat": 80,
            "workload": f"{len(transcribe_items)} items",
            "fn": lambda: transcript_utils._process_items(transcribe_items),
        },
        "_combine_by_speaker": {
            "repeat": 120,
            "workload": f"{len(processed_items)} processed tokens",
            "fn": lambda: transcript_utils._combine_by_speaker(processed_items),
        },
        "generate_text_embeddings": {
            "repeat": 12,
            "workload": f"{len(segments)} segments x mocked {EMBEDDING_DIM}-dim embeddings",
            "fn": lambda: bedrock_utils.generate_text_embeddings(
                segments,
                SOURCE_URI,
                MODEL_ID,
                EMBEDDING_DIM,
            ),
        },
        "insert_segments": {
            "repeat": 24,
            "workload": f"{len(segments)} segments with mocked Aurora writes",
            "fn": lambda: aurora_utils.insert_segments("lecture-123", segments),
        },
        "insert_embeddings": {
            "repeat": 10,
            "workload": f"{len(segment_records)} records x {EMBEDDING_DIM}-dim vectors",
            "fn": lambda: aurora_utils.insert_embeddings(segment_records, embedding_records, MODEL_ID),
        },
    }

    targets = workloads.keys() if args.target == "all" else [args.target]

    with patched_dependencies():
        for target in targets:
            config = workloads[target]
            stats = _run_profile(config["fn"], config["repeat"])
            _print_result(target, config["repeat"], config["workload"], stats)


if __name__ == "__main__":
    main()
