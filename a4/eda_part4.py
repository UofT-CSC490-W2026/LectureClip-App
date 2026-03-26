"""
Compare error patterns across all 4 RL runs.

Usage:
  python eda_compare_runs.py \
    eval_details_GSM8K_rl.jsonl \
    eval_details_GSM8K_rl_step_proximity.jsonl \
    eval_details_GSM8K_rl_step.jsonl \
    eval_details_GSM8K_rl_proximity.jsonl

Each file should be the JSONL output from chat_eval_labeled (or chat_eval_detail).
The script will:
  1. Parse each file, classify errors by type and math topic
  2. Print a comparison table
  3. Generate visualization code (matplotlib) you can run separately
"""

import json
import re
import sys
import csv
from collections import defaultdict

# =============================================================================
# ERROR CLASSIFICATION (same logic as eda_part3.py)
# =============================================================================

MATH_TOPICS = {
    "money_cost": r"(?:cost|price|pay|dollar|cent|\$|spend|buy|purchase|sell|profit|discount|budget|expense|worth|afford|charge|fee|tax|tip|loan|debt|earn|wage|salary|income)",
    "time_schedule": r"(?:hour|minute|second|day|week|month|year|time|clock|schedule|duration|ago|later|long does|when will|how long)",
    "rate_speed_time": r"(?:speed|rate|per hour|mph|km/h|miles per|gallons per|per minute|faster|slower|velocity|distance.*time|time.*distance)",
    "percentage": r"(?:percent|%|\bof\b.*\bmore\b|\bof\b.*\bless\b|increase by|decrease by|markup|markdown|ratio.*100)",
    "ratio_proportion": r"(?:ratio|proportion|for every|per each|scale|fraction of the)",
    "geometry_area": r"(?:area|perimeter|length|width|height|square|rectangle|circle|triangle|radius|diameter|volume|feet|meters|inches|yards|acres)",
    "age_problem": r"(?:age|years old|older|younger|born|birthday|how old)",
    "work_rate": r"(?:work|job|task|together|alone|fill|drain|pipe|pool|complete|finish.*time|can do)",
    "comparison": r"(?:more than|less than|fewer|greater|difference|compare|total|sum|combine|altogether|how many more|how much more|exceed|remain|left over)",
    "counting_combinatorics": r"(?:how many|how much|total|number of|count|each|every|group|divide|split|share|distribute|arrange|ways|combination|sets of)",
}

def classify_topic(question):
    q_lower = question.lower()
    for topic, pattern in MATH_TOPICS.items():
        if re.search(pattern, q_lower):
            return topic
    return "other"


def classify_error(record):
    """Classify error type for a single problem record."""
    for comp in record.get("completions", []):
        if comp.get("is_correct", False):
            return "correct"
    
    if not record.get("completions"):
        return "format_error"
    
    comp = record["completions"][0]
    gen_text = comp.get("generated_text", "")
    predicted = comp.get("predicted_answer")
    ground_truth = record.get("ground_truth_answer")
    
    if predicted is None:
        return "format_error"
    
    try:
        pred_val = float(str(predicted).replace(",", ""))
        truth_val = float(str(ground_truth).replace(",", ""))
    except (ValueError, TypeError):
        return "wrong_approach"
    
    if truth_val == 0:
        if pred_val == 0:
            return "correct"
        return "wrong_approach"
    
    relative_error = abs(pred_val - truth_val) / max(abs(truth_val), 1)
    
    if relative_error < 0.1:
        return "arithmetic_error"
    
    if relative_error < 0.5:
        return "wrong_operation"
    
    step_count = len(re.findall(r'<<.*?>>', gen_text)) + len(re.findall(r'=\s*\d', gen_text))
    if step_count < 2:
        return "missing_step"
    
    return "wrong_approach"


def estimate_steps(text):
    """Count approximate reasoning steps in generated text."""
    steps = 0
    steps += len(re.findall(r'<<.*?>>', text))
    lines = text.strip().split('\n')
    for line in lines:
        if re.search(r'\d', line) and re.search(r'[+\-*/=]', line):
            steps += 1
    return max(steps, 1)


# =============================================================================
# PARSE AND ANALYZE
# =============================================================================

def analyze_run(filepath, label):
    """Parse a JSONL eval file and return structured analysis."""
    records = []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    
    total = len(records)
    correct = sum(1 for r in records if any(
        c.get("is_correct", False) for c in r.get("completions", [])
    ))
    
    results = []
    for r in records:
        topic = classify_topic(r.get("question", ""))
        error_type = classify_error(r)
        comp = r["completions"][0] if r.get("completions") else {}
        gen_text = comp.get("generated_text", "")
        steps = estimate_steps(gen_text)
        
        rel_err = None
        if error_type != "correct":
            try:
                pred = float(str(comp.get("predicted_answer", "0")).replace(",", ""))
                truth = float(str(r.get("ground_truth_answer", "0")).replace(",", ""))
                if truth != 0:
                    rel_err = abs(pred - truth) / abs(truth)
            except (ValueError, TypeError):
                pass
        
        results.append({
            "idx": r.get("idx"),
            "topic": topic,
            "error_type": error_type,
            "steps": steps,
            "relative_error": rel_err,
            "is_correct": error_type == "correct",
        })
    
    return {
        "label": label,
        "total": total,
        "correct": correct,
        "accuracy": correct / total if total > 0 else 0,
        "records": results,
    }


def print_comparison(analyses):
    """Print a formatted comparison table."""
    print("\n" + "=" * 70)
    print("  OVERALL ACCURACY COMPARISON")
    print("=" * 70)
    for a in analyses:
        print(f"  {a['label']:>25s}: {a['correct']}/{a['total']} ({100*a['accuracy']:.1f}%)")
    
    # Error type breakdown
    print("\n" + "=" * 70)
    print("  ERROR TYPE BREAKDOWN (% of all problems)")
    print("=" * 70)
    error_types = ["correct", "wrong_approach", "missing_step", "wrong_operation",
                   "arithmetic_error", "format_error"]
    header = f"  {'Error Type':<22s}" + "".join(f"{a['label']:>16s}" for a in analyses)
    print(header)
    print("  " + "-" * (22 + 16 * len(analyses)))
    for etype in error_types:
        row = f"  {etype:<22s}"
        for a in analyses:
            count = sum(1 for r in a["records"] if r["error_type"] == etype)
            pct = 100 * count / a["total"] if a["total"] > 0 else 0
            row += f"{pct:>15.1f}%"
        print(row)
    
    # Topic-level accuracy
    all_topics = sorted(set(r["topic"] for a in analyses for r in a["records"]))
    print("\n" + "=" * 70)
    print("  ACCURACY BY MATH TOPIC")
    print("=" * 70)
    header = f"  {'Topic':<28s}" + "".join(f"{a['label']:>16s}" for a in analyses)
    print(header)
    print("  " + "-" * (28 + 16 * len(analyses)))
    for topic in all_topics:
        row = f"  {topic:<28s}"
        for a in analyses:
            topic_records = [r for r in a["records"] if r["topic"] == topic]
            if topic_records:
                topic_correct = sum(1 for r in topic_records if r["is_correct"])
                pct = 100 * topic_correct / len(topic_records)
                row += f"{pct:>15.1f}%"
            else:
                row += f"{'N/A':>16s}"
        print(row)
    
    # Average steps and relative error
    print("\n" + "=" * 70)
    print("  REASONING METRICS")
    print("=" * 70)
    for a in analyses:
        correct_steps = [r["steps"] for r in a["records"] if r["is_correct"]]
        wrong_steps = [r["steps"] for r in a["records"] if not r["is_correct"]]
        wrong_rel_errs = [r["relative_error"] for r in a["records"]
                          if r["relative_error"] is not None]
        avg_correct_steps = sum(correct_steps) / len(correct_steps) if correct_steps else 0
        avg_wrong_steps = sum(wrong_steps) / len(wrong_steps) if wrong_steps else 0
        median_rel_err = sorted(wrong_rel_errs)[len(wrong_rel_errs)//2] if wrong_rel_errs else 0
        print(f"  {a['label']:>25s}: "
              f"Avg steps (correct={avg_correct_steps:.1f}, wrong={avg_wrong_steps:.1f}) | "
              f"Median rel error (wrong): {median_rel_err:.2f}")
    
    # Pairwise gains/losses vs Run 0
    if len(analyses) >= 2:
        baseline = analyses[0]
        baseline_correct = {r["idx"] for r in baseline["records"] if r["is_correct"]}
        print("\n" + "=" * 70)
        print(f"  GAINS/LOSSES vs {baseline['label']}")
        print("=" * 70)
        for a in analyses[1:]:
            a_correct = {r["idx"] for r in a["records"] if r["is_correct"]}
            gained = len(a_correct - baseline_correct)
            lost = len(baseline_correct - a_correct)
            net = gained - lost
            print(f"  {a['label']:>25s}: Gained={gained}, Lost={lost}, Net={net:+d}")


def save_comparison_csv(analyses, output_path="run_comparison.csv"):
    """Save comparison data to CSV for external analysis."""
    rows = []
    for a in analyses:
        for r in a["records"]:
            rows.append({
                "run": a["label"],
                "idx": r["idx"],
                "topic": r["topic"],
                "error_type": r["error_type"],
                "is_correct": r["is_correct"],
                "steps": r["steps"],
                "relative_error": r["relative_error"],
            })
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nSaved comparison data to {output_path}")


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python eda_compare_runs.py <run0.jsonl> [run1.jsonl] [run2.jsonl] [run3.jsonl]")
        print("  Files are labeled by order: Run0_original, Run1_step_proximity, Run2_step, Run3_proximity")
        print("  Or pass fewer files for partial comparison.")
        sys.exit(1)
    
    labels = ["Run0_original", "Run1_step_proximity", "Run2_step", "Run3_proximity"]
    
    analyses = []
    for i, filepath in enumerate(sys.argv[1:]):
        label = labels[i] if i < len(labels) else f"Run{i}"
        print(f"Processing: {filepath} (label={label})")
        a = analyze_run(filepath, label)
        analyses.append(a)
    
    print_comparison(analyses)
    save_comparison_csv(analyses)
    
    # viz_path = "visualize_runs.py"
    # with open(viz_path, "w") as f:
    #     f.write(VISUALIZATION_CODE)
    # print(f"\nVisualization code saved to {viz_path}")
    # print("Run it with: python visualize_runs.py")