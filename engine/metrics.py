#!/usr/bin/env python3
"""Health of the system, from logs/review.jsonl (puzzle vetting) and state/history.jsonl (learning).

Vetting
- First-pass acceptance: share of candidates accepted without revision. Very high means the
  reviewer is too lenient; very low means generation is weak.
- Blind-solve mismatch: share of candidates whose first blind solver missed the answer key.
  This is the main defect detector (ambiguity, missing premise or a wrong key).
- Issue types and rejects by domain show where generation needs work.
Learning
- Results by domain and the skills currently due for review.

Usage: python3 engine/metrics.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import dmc  # noqa: E402
import roll  # noqa: E402

TARGETS = {
    "first_pass_acceptance": (0.40, 0.80),
    "blind_solve_mismatch": (0.05, 0.30),
}
MIN_SAMPLE = 10  # below this, rates are too noisy to warn about


def _rate_line(name, hits, n):
    if not n:
        return f"{name}: no data"
    low, high = TARGETS[name]
    line = f"{name}: {hits / n:.0%} ({hits}/{n}, target {low:.0%}-{high:.0%})"
    if n < MIN_SAMPLE:
        line += f"  (n<{MIN_SAMPLE}: too early to judge)"
    elif not low <= hits / n <= high:
        line += "  WARNING: outside target"
    return line


def compute_metrics():
    reviews = []
    if dmc.REVIEW_LOG.exists():
        reviews = [json.loads(l) for l in dmc.REVIEW_LOG.read_text(encoding="utf-8").splitlines() if l.strip()]
    hist = roll.load()

    print("== Vetting ==")
    accepted = [r for r in reviews if r["outcome"] == "accepted"]
    first_pass = sum(not r["revised"] for r in accepted)
    print(f"candidates: {len(reviews)} | accepted: {len(accepted)} | rejected: {len(reviews) - len(accepted)}")
    print(_rate_line("first_pass_acceptance", first_pass, len(reviews)))
    solved = [r for r in reviews if r.get("first_solve_match") is not None]
    print(_rate_line("blind_solve_mismatch", sum(not r["first_solve_match"] for r in solved), len(solved)))
    issues = Counter(i.get("type") for r in reviews for i in r.get("issues", []) if i.get("severity", 0) >= 2)
    if issues:
        print("issues (severity>=2):", ", ".join(f"{t} {n}" for t, n in issues.most_common()))
    rejects = Counter(r["domain_id"] for r in reviews if r["outcome"] == "rejected")
    if rejects:
        print("rejects by domain:", ", ".join(f"{d}. {roll.DOMAINS[d]} {n}" for d, n in rejects.most_common()))

    print("== Learning ==")
    graded = [h for h in hist if h["result"] in ("correct", "partial", "incorrect")]
    print(f"days: {len(hist)} | base level now: {roll.current_level(hist)}")
    by_domain = {}
    for h in graded:
        by_domain.setdefault(h["domain_id"], Counter())[h["result"]] += 1
    for d, c in sorted(by_domain.items()):
        print(f"  {d}. {roll.DOMAINS[d]}: " + ", ".join(f"{k} {v}" for k, v in c.items()))
    due = dmc.due_skills(hist, dmc.today())
    print("skills due for review:", ", ".join(f"{d['skill']} (missed {d['missed_on']})" for d in due) or "none")


if __name__ == "__main__":
    compute_metrics()
