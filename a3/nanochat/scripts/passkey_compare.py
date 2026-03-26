"""
Compare two passkey retrieval evaluation result files side by side.

Usage:
    python -m scripts.passkey_compare results_ckpt1.json results_ckpt2.json
"""

import sys
import json


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m scripts.passkey_compare <ckpt1.json> <ckpt2.json>")
        sys.exit(1)

    path1, path2 = sys.argv[1], sys.argv[2]

    with open(path1) as f:
        r1 = json.load(f)
    with open(path2) as f:
        r2 = json.load(f)

    name1 = f"step={r1['step']} (native={r1['native_seq_len']})"
    name2 = f"step={r2['step']} (native={r2['native_seq_len']})"

    # Collect all context lengths tested
    all_lengths = sorted(
        set(
            [int(k) for k in r1["accuracy_by_length"]]
            + [int(k) for k in r2["accuracy_by_length"]]
        )
    )

    print()
    print("=" * 78)
    print("PASSKEY RETRIEVAL — CHECKPOINT COMPARISON")
    print("=" * 78)
    print(f"  Checkpoint 1: {name1}")
    print(f"  Checkpoint 2: {name2}")
    print(f"  Seed: {r1.get('seed', '?')}  |  Samples/length: {r1.get('samples_per_length', '?')}")
    print("=" * 78)
    print()

    # --- Overall accuracy table ---
    header = f"{'Context':>10} | {'Ckpt1':>8} | {'Ckpt2':>8} | {'Delta':>8}"
    print(header)
    print("-" * len(header))

    for ctx in all_lengths:
        a1 = r1["accuracy_by_length"].get(str(ctx), r1["accuracy_by_length"].get(ctx, None))
        a2 = r2["accuracy_by_length"].get(str(ctx), r2["accuracy_by_length"].get(ctx, None))

        s1 = f"{a1:.3f}" if a1 is not None else "  n/a"
        s2 = f"{a2:.3f}" if a2 is not None else "  n/a"

        if a1 is not None and a2 is not None:
            delta = a2 - a1
            sd = f"{delta:+.3f}"
        else:
            sd = "  n/a"

        marker = ""
        if ctx > r1["native_seq_len"]:
            marker = " <-- beyond ckpt1 training"

        print(f"{ctx:>10} | {s1:>8} | {s2:>8} | {sd:>8}{marker}")

    print()

    # --- Depth breakdown for key context lengths ---
    key_lengths = [l for l in all_lengths if l in (512, 1024, 2048)]
    if key_lengths:
        print("=" * 78)
        print("DEPTH BREAKDOWN (needle position: 0.00=start, 1.00=end)")
        print("=" * 78)

        for ctx in key_lengths:
            d1 = r1.get("accuracy_by_length_and_depth", {}).get(str(ctx), {})
            d2 = r2.get("accuracy_by_length_and_depth", {}).get(str(ctx), {})
            if not d1 and not d2:
                d1 = r1.get("accuracy_by_length_and_depth", {}).get(ctx, {})
                d2 = r2.get("accuracy_by_length_and_depth", {}).get(ctx, {})

            if not d1 and not d2:
                continue

            all_depths = sorted(set(list(d1.keys()) + list(d2.keys())))
            print(f"\n  Context length = {ctx}")
            dh = f"    {'Depth':>8} | {'Ckpt1':>8} | {'Ckpt2':>8}"
            print(dh)
            print("    " + "-" * (len(dh) - 4))
            for dep in all_depths:
                v1 = d1.get(dep)
                v2 = d2.get(dep)
                vs1 = f"{v1:.3f}" if v1 is not None else "  n/a"
                vs2 = f"{v2:.3f}" if v2 is not None else "  n/a"
                print(f"    {dep:>8} | {vs1:>8} | {vs2:>8}")

    print()

    # --- Overall summary ---
    # Average accuracy across all context lengths
    vals1 = [v for v in r1["accuracy_by_length"].values() if v is not None]
    vals2 = [v for v in r2["accuracy_by_length"].values() if v is not None]
    avg1 = sum(vals1) / len(vals1) if vals1 else 0
    avg2 = sum(vals2) / len(vals2) if vals2 else 0

    # Average for lengths > native_seq_len of ckpt1
    beyond1 = [
        r1["accuracy_by_length"].get(str(l), r1["accuracy_by_length"].get(l, 0))
        for l in all_lengths if l > r1["native_seq_len"]
    ]
    beyond2 = [
        r2["accuracy_by_length"].get(str(l), r2["accuracy_by_length"].get(l, 0))
        for l in all_lengths if l > r1["native_seq_len"]
    ]
    avg_beyond1 = sum(beyond1) / len(beyond1) if beyond1 else 0
    avg_beyond2 = sum(beyond2) / len(beyond2) if beyond2 else 0

    print("=" * 78)
    print("SUMMARY")
    print(f"  Average accuracy (all lengths):       Ckpt1={avg1:.3f}  Ckpt2={avg2:.3f}")
    print(f"  Average accuracy (beyond {r1['native_seq_len']}):  "
          f"Ckpt1={avg_beyond1:.3f}  Ckpt2={avg_beyond2:.3f}")
    print("=" * 78)


if __name__ == "__main__":
    main()