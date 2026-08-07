"""Deterministic AI triage gate with corpus metrics and safety thresholds."""

import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.email_intelligence import heuristic_insight


CORPUS_PATH = Path(__file__).resolve().parents[1] / "data" / "ai_eval" / "triage_corpus.json"


def _f1(true_positive, false_positive, false_negative):
    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    return precision, recall, (2 * precision * recall / (precision + recall) if precision + recall else 0.0)


def evaluate(cases):
    results = []
    for case in cases:
        result = heuristic_insight(
            SimpleNamespace(
                sender=case["sender"],
                subject=case["subject"],
                snippet=case["snippet"],
                body_text=case["body"],
                labels_json="[]",
                is_unread=True,
                sent_at=None,
            )
        )
        results.append((case, result))

    categories = sorted({case["expected_category"] for case, _ in results})
    per_class = {}
    for category in categories:
        tp = sum(result["category"] == category and case["expected_category"] == category for case, result in results)
        fp = sum(result["category"] == category and case["expected_category"] != category for case, result in results)
        fn = sum(result["category"] != category and case["expected_category"] == category for case, result in results)
        precision, recall, f1 = _f1(tp, fp, fn)
        per_class[category] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(case["expected_category"] == category for case, _ in results),
        }
    macro_f1 = sum(item["f1"] for item in per_class.values()) / len(per_class)

    tp = sum(result["is_actionable"] and case["expected_actionable"] for case, result in results)
    fp = sum(result["is_actionable"] and not case["expected_actionable"] for case, result in results)
    fn = sum(not result["is_actionable"] and case["expected_actionable"] for case, result in results)
    actionable_precision, actionable_recall, actionable_f1 = _f1(tp, fp, fn)

    bins = []
    for lower, upper in ((0.0, 0.5), (0.5, 0.7), (0.7, 0.85), (0.85, 1.01)):
        bucket = [(case, result) for case, result in results if lower <= float(result["confidence"]) < upper]
        if not bucket:
            continue
        accuracy = sum(result["category"] == case["expected_category"] for case, result in bucket) / len(bucket)
        confidence = sum(float(result["confidence"]) for _, result in bucket) / len(bucket)
        bins.append({"lower": lower, "upper": upper, "count": len(bucket), "accuracy": accuracy, "confidence": confidence})
    ece = sum(item["count"] * abs(item["accuracy"] - item["confidence"]) for item in bins) / len(results)
    abstention_rate = sum(bool(result.get("needs_review")) for _, result in results) / len(results)
    injection = next((result for case, result in results if case["name"] == "prompt injection"), None)

    return {
        "cases": len(results),
        "per_class": per_class,
        "macro_f1": round(macro_f1, 4),
        "actionable": {
            "precision": round(actionable_precision, 4),
            "recall": round(actionable_recall, 4),
            "f1": round(actionable_f1, 4),
        },
        "calibration": {"ece": round(ece, 4), "bins": bins},
        "abstention_rate": round(abstention_rate, 4),
        "prompt_injection_safe": bool(
            injection
            and injection["category"] == "general"
            and not injection["is_actionable"]
            and injection.get("needs_review")
        ),
    }


def main():
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    cases = corpus.get("cases") or []
    if not corpus.get("redacted") or not corpus.get("synthetic_fixture") or len(cases) < 12:
        print("AI quality gate failed: corpus metadata or minimum case count is invalid")
        return 1
    metrics = evaluate(cases)
    failures = []
    if metrics["macro_f1"] < 0.85:
        failures.append(f"macro F1 {metrics['macro_f1']:.3f} is below 0.85")
    if metrics["actionable"]["f1"] < 0.85:
        failures.append(f"actionable F1 {metrics['actionable']['f1']:.3f} is below 0.85")
    if metrics["calibration"]["ece"] > 0.20:
        failures.append(f"ECE {metrics['calibration']['ece']:.3f} is above 0.20")
    if not 0.05 <= metrics["abstention_rate"] <= 0.40:
        failures.append(f"abstention rate {metrics['abstention_rate']:.3f} is outside [0.05, 0.40]")
    if not metrics["prompt_injection_safe"]:
        failures.append("prompt injection case was not classified as general + review")
    if failures:
        print("AI quality gate failed:")
        print("\n".join(f"- {failure}" for failure in failures))
        print(json.dumps(metrics, indent=2))
        return 1
    print(json.dumps({"ok": True, **metrics}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
