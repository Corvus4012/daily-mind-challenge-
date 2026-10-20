"""Health metrics for the review pipeline, computed from logs/{draft_id}_{cid}.json timelines.

- Red Team catch rate: share of debated candidates whose round-1 attacks include
  at least one attack with severity >= 2.
- Solvability disagreement rate: share of solver pairs whose answers disagree with each other.
- Dead letter rate: share of finished candidates (pool, dead_letter, human_review) that ended in dead_letter.
Timelines marked "error" (API or parse failure) are skipped.

Usage: python3 -m engine.metrics
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "logs"

TARGETS = {
    "red_team_catch_rate": (0.30, 0.50),
    "solvability_disagreement_rate": (0.05, 0.30),
    "dead_letter_rate": (0.10, 0.50),
}


def _severity(attack):
    try:
        return int(attack.get("severity", 0))
    except (TypeError, ValueError):
        return 0


def _load_timelines():
    timelines = []
    for path in sorted(LOGS.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("outcome") in ("pool", "dead_letter", "human_review"):
            timelines.append(data)
    return timelines


def _rate(hits, total):
    return {"value": hits / total if total else None, "hits": hits, "n": total}


def compute_metrics():
    timelines = _load_timelines()

    debated = [t for t in timelines if t.get("rounds")]
    caught = sum(
        any(_severity(a) >= 2 for a in (t["rounds"][0].get("attacks") or {}).get("attacks", []))
        for t in debated
    )
    checked = [t for t in timelines if t.get("solvability")]
    disagreed = sum(not t["solvability"].get("solvers_agree", True) for t in checked)
    dead = sum(t["outcome"] == "dead_letter" for t in timelines)

    metrics = {
        "red_team_catch_rate": _rate(caught, len(debated)),
        "solvability_disagreement_rate": _rate(disagreed, len(checked)),
        "dead_letter_rate": _rate(dead, len(timelines)),
    }
    for name, m in metrics.items():
        low, high = TARGETS[name]
        target = f"target {low:.0%}-{high:.0%}"
        if m["value"] is None:
            print(f"{name}: no data ({target})")
            continue
        line = f"{name}: {m['value']:.0%} ({m['hits']}/{m['n']}, {target})"
        if not low <= m["value"] <= high:
            line += "  WARNING: outside target"
        print(line)
    held = sum(t["outcome"] == "human_review" for t in timelines)
    if held:
        print(f"human_review (answer_key_suspect): {held}")
    return metrics


if __name__ == "__main__":
    compute_metrics()
