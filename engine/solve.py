"""Blind-solve every candidate of a draft with two different models (commands/solve.md).

Solver 1: Sonnet, solve_from_first_principles. Solver 2: Haiku, solve_with_known_methods.
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

_COMMON = """Answer every sub-question. If the puzzle is missing information you need, write
"unsolvable: thiếu X" as the answer instead of guessing.
Return JSON: {"answer": str, "reasoning": str}
"answer" holds only your final answers (one line per sub-question); "reasoning" is required and shows your working."""

SOLVERS = {
    1: {
        "call": _llm.call_sonnet,
        "model": _llm.MODELS["sonnet"],
        "style": "solve_from_first_principles",
        "prompt": "You are solving a reasoning puzzle written in Vietnamese, using only the information it gives.\n"
                  "Work from the stated premises step by step. Do not reach for a known formula or textbook result; "
                  "derive what you need.\n" + _COMMON,
    },
    2: {
        "call": _llm.call_haiku,
        "model": _llm.MODELS["haiku"],
        "style": "solve_with_known_methods",
        "prompt": "You are solving a reasoning puzzle written in Vietnamese, using only the information it gives.\n"
                  "Identify the standard method for this kind of problem, if one exists, and apply it.\n" + _COMMON,
    },
}


def solve_candidate(draft_id, cid, content, tag=""):
    """Run both solvers on one puzzle; tag (e.g. "_rev1") keeps re-solves apart from the originals."""
    SOLVES.mkdir(parents=True, exist_ok=True)
    results = {}
    for solver_id, solver in SOLVERS.items():
        out = solver["call"](solver["prompt"], {"problem": content}, agent=f"solver{solver_id}")
        record = {
            "draft_id": draft_id,
            "cid": cid,
            "solver_id": solver_id,
            "solver_answer": out.get("answer"),
            "solver_reasoning": out.get("reasoning"),
            "solver_model": solver["model"],
            "solver_prompt_style": solver["style"],
            "solved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path = SOLVES / f"{draft_id}_{cid}{tag}_solver{solver_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results[solver_id] = record
    return results


def solve_draft(draft_id):
    draft = json.loads((DRAFTS / f"{draft_id}.json").read_text(encoding="utf-8"))
    written = []
    for cand in draft["candidates"]:
        solve_candidate(draft_id, cand["cid"], cand["content"])
        written += [f"{draft_id}_{cand['cid']}_solver{n}.json" for n in SOLVERS]
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m engine.solve <draft_id>")
    print("\n".join(solve_draft(sys.argv[1])))
