"""
GSM8K Evaluation EDA Script
============================
Analyzes eval_details_GSM8K_*.jsonl files from nanochat chat_eval runs.

Usage:
    python gsm8k_eda.py eval_details_GSM8K_sft.jsonl eval_details_GSM8K_rl.jsonl
    python gsm8k_eda.py eval_details_GSM8K_rl.jsonl   # single file works too

Outputs:
    - gsm8k_analysis.json         : full categorized data for the dashboard
    - gsm8k_summary.csv           : per-problem summary with categories
    - gsm8k_category_stats.csv    : accuracy by math topic
    - gsm8k_error_stats.csv       : error type breakdown
    - gsm8k_comparison.csv        : SFT vs RL comparison (if both provided)
"""

import json
import re
import sys
import csv
from collections import Counter, defaultdict
from pathlib import Path

# =============================================================================
# 1. MATH TOPIC CLASSIFICATION (keyword-based)
# =============================================================================

TOPIC_RULES = [
    # (topic_name, keywords_that_must_appear_any)
    ("ratio_proportion", [r"\bratio\b", r"\bproportion\b", r"\bfraction\b"]),
    ("percentage", [r"\bpercent\b", r"\b%\b", r"\bdiscount\b", r"\bmarkup\b", r"\btax\b", r"\btip\b", r"\bincrease.*%", r"\bdecrease.*%"]),
    ("rate_speed_time", [r"\bspeed\b", r"\bfaster\b", r"\bslower\b", r"\bper hour\b", r"\bper minute\b", r"\bper second\b", r"\bmiles per\b", r"\bfeet per\b", r"\bkm per\b", r"\brate\b"]),
    ("age_problem", [r"\bage\b", r"\byears old\b", r"\byounger\b", r"\bolder\b", r"\bborn\b"]),
    ("money_cost", [r"\$\d", r"\bdollar\b", r"\bcost\b", r"\bprice\b", r"\bpaid\b", r"\bearns?\b", r"\bsalary\b", r"\bwage\b", r"\bspend\b", r"\bprofit\b", r"\bbudget\b", r"\bcharge\b"]),
    ("geometry_area", [r"\barea\b", r"\bperimeter\b", r"\bsquare\b", r"\brectangle\b", r"\bcircle\b", r"\bradius\b", r"\blength\b", r"\bwidth\b", r"\bfeet\b.*\bfeet\b", r"\binch\b"]),
    ("counting_combinatorics", [r"\bhow many\b", r"\btotal number\b", r"\bremaining\b", r"\bleft over\b", r"\beach\b"]),
    ("time_schedule", [r"\bhours?\b", r"\bminutes?\b", r"\bdays?\b", r"\bweeks?\b", r"\bmonths?\b", r"\btime\b", r"\bschedule\b"]),
    ("work_rate", [r"\bwork\b.*\bdays?\b", r"\bjob\b", r"\btask\b", r"\bproduce\b", r"\boutput\b", r"\befficiency\b"]),
    ("comparison", [r"\bmore than\b", r"\bless than\b", r"\btimes as\b", r"\btwice\b", r"\bthrice\b", r"\bhalf\b", r"\bdouble\b", r"\btriple\b"]),
]

def classify_math_topic(question: str) -> list[str]:
    """Classify a question into one or more math topic categories."""
    q_lower = question.lower()
    topics = []
    for topic_name, patterns in TOPIC_RULES:
        for pat in patterns:
            if re.search(pat, q_lower):
                topics.append(topic_name)
                break
    if not topics:
        topics.append("other")
    return topics


# =============================================================================
# 2. ERROR TYPE CLASSIFICATION (heuristic-based)
# =============================================================================

def classify_error(record: dict) -> str:
    """
    Classify the type of error the model made.
    Returns one of:
        - "correct"             : model got it right
        - "wrong_operation"     : model used wrong math operation (close structure, wrong op)
        - "missing_step"        : model skipped a step in multi-step reasoning
        - "misread_relationship": model misunderstood a comparative (e.g., "5x faster" -> multiplied)
        - "arithmetic_error"    : right approach but wrong computation
        - "wrong_approach"      : completely different solution strategy
        - "no_answer"           : model didn't produce a parseable answer
        - "format_error"        : model produced an answer but not in #### format
    """
    if record.get("passed", False):
        return "correct"

    comp = record["completions"][0]  # use first completion
    pred = comp.get("predicted_answer")
    gt = record.get("ground_truth_answer")

    if pred is None:
        gen = comp.get("generated_text", "")
        if "####" not in gen:
            return "format_error"
        return "no_answer"

    if gt is None:
        return "unknown"

    # Try to parse as numbers for proximity analysis
    try:
        pred_num = float(pred)
        gt_num = float(gt)
    except (ValueError, TypeError):
        return "wrong_approach"

    # Check if it's an arithmetic error (close but not exact)
    if gt_num != 0:
        ratio = pred_num / gt_num
        diff_pct = abs(pred_num - gt_num) / abs(gt_num)

        # Common operation confusion: answer is exactly N times off
        for mult in [2, 3, 4, 5, 10, 0.5, 0.1, 0.2]:
            if abs(ratio - mult) < 0.001:
                return "wrong_operation"

        # Very close (within 10%) — likely arithmetic error
        if diff_pct < 0.10:
            return "arithmetic_error"

        # Off by an additive constant that appears in the problem — missing step
        if diff_pct < 0.50:
            return "missing_step"

    return "wrong_approach"


def compute_numerical_distance(record: dict) -> dict:
    """Compute how far off the predicted answer is from ground truth."""
    comp = record["completions"][0]
    pred = comp.get("predicted_answer")
    gt = record.get("ground_truth_answer")

    result = {"absolute_error": None, "relative_error": None, "ratio": None}
    try:
        pred_num = float(pred)
        gt_num = float(gt)
        result["absolute_error"] = abs(pred_num - gt_num)
        if gt_num != 0:
            result["relative_error"] = abs(pred_num - gt_num) / abs(gt_num)
            result["ratio"] = pred_num / gt_num
    except (ValueError, TypeError):
        pass
    return result


# =============================================================================
# 3. PROBLEM COMPLEXITY ESTIMATION
# =============================================================================

def estimate_complexity(question: str, ground_truth_answer: str = None) -> dict:
    """Estimate problem complexity from surface features."""
    q_lower = question.lower()

    # Count numbers mentioned in the question
    numbers = re.findall(r'\b\d+\.?\d*\b', question)
    num_count = len(numbers)

    # Count sentences (rough proxy for problem length)
    sentences = [s.strip() for s in re.split(r'[.?!]', question) if s.strip()]
    num_sentences = len(sentences)

    # Word count
    word_count = len(question.split())

    # Number of computation steps (heuristic: more numbers = more steps)
    estimated_steps = max(1, num_count - 1)

    # Large numbers might be harder
    max_number = max([float(n) for n in numbers], default=0)
    has_large_numbers = max_number > 1000

    # Involves fractions/decimals?
    has_fractions = bool(re.search(r'\b\d+/\d+\b', question) or re.search(r'\b\d+\.\d+\b', question))

    return {
        "num_numbers": num_count,
        "num_sentences": num_sentences,
        "word_count": word_count,
        "estimated_steps": estimated_steps,
        "has_large_numbers": has_large_numbers,
        "has_fractions": has_fractions,
    }


# =============================================================================
# 4. LOAD AND PROCESS
# =============================================================================

def load_jsonl(path: str) -> list[dict]:
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def analyze_file(path: str) -> list[dict]:
    """Load a JSONL file and enrich each record with categories."""
    records = load_jsonl(path)
    enriched = []
    for r in records:
        r["math_topics"] = classify_math_topic(r["question"])
        r["error_type"] = classify_error(r)
        r["numerical_distance"] = compute_numerical_distance(r)
        r["complexity"] = estimate_complexity(r["question"], r.get("ground_truth_answer"))
        # Flatten the first completion for easier analysis
        if r["completions"]:
            c = r["completions"][0]
            r["generated_text"] = c.get("generated_text", "")
            r["predicted_answer"] = c.get("predicted_answer")
            r["is_correct"] = c.get("is_correct", False)
        enriched.append(r)
    return enriched


# =============================================================================
# 5. AGGREGATE STATISTICS
# =============================================================================

def compute_stats(records: list[dict], label: str = "") -> dict:
    """Compute summary statistics for a set of records."""
    total = len(records)
    correct = sum(1 for r in records if r.get("passed", False))

    # By math topic
    topic_stats = defaultdict(lambda: {"total": 0, "correct": 0})
    for r in records:
        for topic in r["math_topics"]:
            topic_stats[topic]["total"] += 1
            topic_stats[topic]["correct"] += int(r.get("passed", False))

    # By error type
    error_counts = Counter(r["error_type"] for r in records)

    # Complexity vs accuracy
    correct_complexity = [r["complexity"]["estimated_steps"] for r in records if r.get("passed")]
    wrong_complexity = [r["complexity"]["estimated_steps"] for r in records if not r.get("passed")]

    avg_correct_steps = sum(correct_complexity) / len(correct_complexity) if correct_complexity else 0
    avg_wrong_steps = sum(wrong_complexity) / len(wrong_complexity) if wrong_complexity else 0

    # Numerical distance for wrong answers
    wrong_records = [r for r in records if not r.get("passed")]
    rel_errors = [r["numerical_distance"]["relative_error"] for r in wrong_records if r["numerical_distance"]["relative_error"] is not None]
    avg_rel_error = sum(rel_errors) / len(rel_errors) if rel_errors else None

    return {
        "label": label,
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0,
        "topic_stats": {k: {"total": v["total"], "correct": v["correct"], "accuracy": v["correct"]/v["total"] if v["total"] > 0 else 0} for k, v in topic_stats.items()},
        "error_counts": dict(error_counts),
        "avg_steps_correct": avg_correct_steps,
        "avg_steps_wrong": avg_wrong_steps,
        "avg_relative_error": avg_rel_error,
    }


def print_stats(stats: dict):
    label = stats["label"] or "Dataset"
    print(f"\n{'='*60}")
    print(f"  {label}: {stats['correct']}/{stats['total']} ({100*stats['accuracy']:.1f}%)")
    print(f"{'='*60}")

    print(f"\n  Avg estimated steps — correct: {stats['avg_steps_correct']:.1f}, wrong: {stats['avg_steps_wrong']:.1f}")
    if stats['avg_relative_error'] is not None:
        print(f"  Avg relative error (wrong answers): {stats['avg_relative_error']:.2f}")

    print(f"\n  Accuracy by Math Topic:")
    print(f"  {'Topic':<28} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print(f"  {'-'*56}")
    for topic, ts in sorted(stats["topic_stats"].items(), key=lambda x: -x[1]["accuracy"]):
        print(f"  {topic:<28} {ts['correct']:>8} {ts['total']:>8} {100*ts['accuracy']:>9.1f}%")

    print(f"\n  Error Type Breakdown:")
    print(f"  {'Error Type':<28} {'Count':>8} {'% of All':>10}")
    print(f"  {'-'*48}")
    for err_type, count in sorted(stats["error_counts"].items(), key=lambda x: -x[1]):
        print(f"  {err_type:<28} {count:>8} {100*count/stats['total']:>9.1f}%")


# =============================================================================
# 6. COMPARISON (SFT vs RL)
# =============================================================================

def compare_checkpoints(records_a: list[dict], records_b: list[dict], label_a: str, label_b: str) -> list[dict]:
    """Compare two checkpoint evaluations problem-by-problem."""
    index_a = {r["idx"]: r for r in records_a}
    index_b = {r["idx"]: r for r in records_b}
    common_indices = sorted(set(index_a.keys()) & set(index_b.keys()))

    comparison = []
    gained = 0  # wrong in A, correct in B
    lost = 0    # correct in A, wrong in B
    for idx in common_indices:
        ra, rb = index_a[idx], index_b[idx]
        passed_a = ra.get("passed", False)
        passed_b = rb.get("passed", False)
        change = "unchanged"
        if not passed_a and passed_b:
            change = "gained"
            gained += 1
        elif passed_a and not passed_b:
            change = "lost"
            lost += 1
        comparison.append({
            "idx": idx,
            "question": ra["question"],
            "ground_truth": ra.get("ground_truth_answer"),
            f"{label_a}_correct": passed_a,
            f"{label_b}_correct": passed_b,
            "change": change,
            "math_topics": ra["math_topics"],
            "error_type_a": ra["error_type"],
            "error_type_b": rb["error_type"],
        })

    print(f"\n{'='*60}")
    print(f"  Comparison: {label_a} vs {label_b}")
    print(f"  Common problems: {len(common_indices)}")
    print(f"  Gained (wrong→right): {gained}")
    print(f"  Lost   (right→wrong): {lost}")
    print(f"  Net improvement: {gained - lost}")
    print(f"{'='*60}")

    # Which topics improved most?
    topic_changes = defaultdict(lambda: {"gained": 0, "lost": 0})
    for c in comparison:
        if c["change"] in ("gained", "lost"):
            for topic in c["math_topics"]:
                topic_changes[topic][c["change"]] += 1

    print(f"\n  Topic-level changes:")
    print(f"  {'Topic':<28} {'Gained':>8} {'Lost':>8} {'Net':>8}")
    print(f"  {'-'*54}")
    for topic, changes in sorted(topic_changes.items(), key=lambda x: -(x[1]["gained"] - x[1]["lost"])):
        net = changes["gained"] - changes["lost"]
        print(f"  {topic:<28} {changes['gained']:>8} {changes['lost']:>8} {net:>+8}")

    return comparison


# =============================================================================
# 7. SAVE OUTPUTS
# =============================================================================

def save_csv(rows: list[dict], path: str, fieldnames: list[str] = None):
    if not rows:
        return
    if fieldnames is None:
        fieldnames = list(rows[0].keys())
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  Saved: {path}")


def save_summary_csv(records: list[dict], path: str):
    """Save a flat per-problem CSV for easy spreadsheet analysis."""
    rows = []
    for r in records:
        rows.append({
            "idx": r["idx"],
            "question": r["question"],
            "ground_truth_answer": r.get("ground_truth_answer", ""),
            "predicted_answer": r.get("predicted_answer", ""),
            "is_correct": r.get("passed", False),
            "math_topics": "|".join(r["math_topics"]),
            "error_type": r["error_type"],
            "absolute_error": r["numerical_distance"]["absolute_error"],
            "relative_error": r["numerical_distance"]["relative_error"],
            "num_numbers": r["complexity"]["num_numbers"],
            "estimated_steps": r["complexity"]["estimated_steps"],
            "word_count": r["complexity"]["word_count"],
            "generated_text": r.get("generated_text", "")[:500],  # truncate
        })
    save_csv(rows, path)


def save_analysis_json(all_data: dict, path: str):
    """Save full analysis as JSON for the interactive dashboard."""
    with open(path, "w") as f:
        json.dump(all_data, f, indent=2, default=str)
    print(f"  Saved: {path}")


# =============================================================================
# MAIN
# =============================================================================

def main():
    if len(sys.argv) < 2:
        print("Usage: python gsm8k_eda.py <eval_details_GSM8K_*.jsonl> [eval_details_GSM8K_*.jsonl]")
        print("\nExamples:")
        print("  python gsm8k_eda.py eval_details_GSM8K_rl.jsonl")
        print("  python gsm8k_eda.py eval_details_GSM8K_sft.jsonl eval_details_GSM8K_rl.jsonl")
        sys.exit(1)

    files = sys.argv[1:]
    all_analysis = {}

    for fpath in files:
        # Infer label from filename
        p = Path(fpath)
        if "sft" in p.stem.lower():
            label = "sft"
        elif "rl" in p.stem.lower():
            label = "rl"
        else:
            label = p.stem

        print(f"\nProcessing: {fpath} (label={label})")
        records = analyze_file(fpath)
        stats = compute_stats(records, label=label)
        print_stats(stats)

        # Save per-file outputs
        save_summary_csv(records, f"gsm8k_summary_{label}.csv")

        # Save category stats
        topic_rows = [{"topic": k, **v} for k, v in stats["topic_stats"].items()]
        save_csv(topic_rows, f"gsm8k_category_stats_{label}.csv")

        # Save error stats
        error_rows = [{"error_type": k, "count": v, "pct": v/stats["total"]*100} for k, v in stats["error_counts"].items()]
        save_csv(error_rows, f"gsm8k_error_stats_{label}.csv")

        all_analysis[label] = {
            "records": records,
            "stats": stats,
        }

    # If we have both SFT and RL, do a comparison
    if "sft" in all_analysis and "rl" in all_analysis:
        comparison = compare_checkpoints(
            all_analysis["sft"]["records"],
            all_analysis["rl"]["records"],
            "sft", "rl"
        )
        save_csv(comparison, "gsm8k_comparison.csv")
        all_analysis["comparison"] = comparison

    # Save full analysis JSON for the dashboard
    # Strip generated_text from JSON to keep size manageable
    dashboard_data = {}
    for label, data in all_analysis.items():
        if label == "comparison":
            dashboard_data["comparison"] = data
        else:
            dashboard_data[label] = {
                "stats": data["stats"],
                "records": [{
                    "idx": r["idx"],
                    "question": r["question"][:200],
                    "ground_truth_answer": r.get("ground_truth_answer"),
                    "predicted_answer": r.get("predicted_answer"),
                    "passed": r.get("passed", False),
                    "math_topics": r["math_topics"],
                    "error_type": r["error_type"],
                    "numerical_distance": r["numerical_distance"],
                    "complexity": r["complexity"],
                } for r in data["records"]]
            }
    save_analysis_json(dashboard_data, "gsm8k_analysis.json")

    print(f"\nDone! All outputs saved.")


if __name__ == "__main__":
    main()