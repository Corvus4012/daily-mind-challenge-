"""Blind-solve every candidate of a draft with two independent solvers (commands/solve.md).

Solver 1: Sonnet + prompts/solver_first_principles.md
Solver 2: Haiku  + prompts/solver_known_methods.md
For tag_type "lookup" both solvers run on Sonnet with web search, since the puzzle needs one lookup.
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

SOLVERS = {
    1: {"model": "sonnet", "style": "solve_from_first_principles", "prompt": "solver_first_principles"},
    2: {"model": "haiku", "style": "solve_with_known_methods", "prompt": "solver_known_methods"},
}


def _run_solver(solver, content, lookup, agent):
    prompt = _llm.load_prompt(solver["prompt"])
    if lookup:
        return "sonnet", _llm.call_sonnet(prompt, {"content": content}, agent=agent, web_search=True)
    call = _llm.call_sonnet if solver["model"] == "sonnet" else _llm.call_haiku
    return solver["model"], call(prompt, {"content": content}, agent=agent)


def solve_candidate(draft_id, cand, tag=""):
    """Run both solvers on one candidate; tag (e.g. "_rev1") keeps re-solves apart from the originals."""
    SOLVES.mkdir(parents=True, exist_ok=True)
    lookup = cand.get("tag_type") == "lookup"
    results = {}
    for solver_id, solver in SOLVERS.items():
        model_key, out = _run_solver(solver, cand["content"], lookup, f"solver{solver_id}")
        answer = out.get("solver_answer")
        record = {
            "draft_id": draft_id,
            "cid": cand["cid"],
            "solver_id": solver_id,
            "solver_answer": answer,
            "solver_reasoning": out.get("solver_reasoning"),
            "unsolvable": bool(out.get("unsolvable")) or str(answer or "").lower().startswith("unsolvable"),
            "solver_model": _llm.MODELS[model_key],
            "solver_prompt_style": solver["style"],
            "web_search": lookup,
            "solved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        path = SOLVES / f"{draft_id}_{cand['cid']}{tag}_solver{solver_id}.json"
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        results[solver_id] = record
    return results


def solve_draft(draft_id):
    draft = json.loads((DRAFTS / f"{draft_id}.json").read_text(encoding="utf-8"))
    written = []
    for cand in draft["candidates"]:
        solve_candidate(draft_id, cand)
        written += [f"{draft_id}_{cand['cid']}_solver{n}.json" for n in SOLVERS]
    return written


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m engine.solve <draft_id>")
    print("\n".join(solve_draft(sys.argv[1])))
