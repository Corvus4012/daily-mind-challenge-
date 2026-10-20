"""Blind-solve every candidate of a draft twice with Sonnet.

Solvers see only the puzzle content: never the answer, rubric or hints.
Output: solves/{draft_id}_{cid}_solver{1,2}.json

Usage: python3 -m engine.solve <draft_id>
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from engine import _llm

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
SOLVES = ROOT / "solves"

SOLVER_PROMPT = """You are solving a reasoning puzzle written in Vietnamese. Use only the information it gives.
Answer every sub-question.
Return JSON: {"answer": str, "reasoning": str}
"answer" holds your final answers only (one line per sub-question); "reasoning" holds your working."""


def solve_draft(draft_id):
    draft = json.loads((DRAFTS / f"{draft_id}.json").read_text(encoding="utf-8"))
    SOLVES.mkdir(parents=True, exist_ok=True)
    written = []
    for cand in draft["candidates"]:
        for solver_id in (1, 2):
            result = _llm.call_sonnet(SOLVER_PROMPT, {"problem": cand["content"]},
                                      agent=f"solver{solver_id}")
            path = SOLVES / f"{draft_id}_{cand['cid']}_solver{solver_id}.json"
            path.write_text(json.dumps({
                "draft_id": draft_id,
                "cid": cand["cid"],
                "solver_id": solver_id,
                "answer": result.get("answer"),
                "reasoning": result.get("reasoning"),
                "solved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written.append(path.name)
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m engine.solve <draft_id>")
    print("\n".join(solve_draft(sys.argv[1])))
