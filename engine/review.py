"""Review a draft: solvability check, then a Red Team / Defender / Judge debate per candidate.

Draft file drafts/{draft_id}.json:
  {"draft_id": str, "date": str, "tag": str, "level": int,
   "candidates": [{"cid": str, "domain_id": int, "content": str,
                   "answer": str, "rubric": str, "hints": [str, ...]}, ...]}
Solver files must already exist (engine/solve.py).

Outcomes per candidate:
  PASS                -> pool/{uuid}.json
  anything else       -> dead_letter/{draft_id}_{cid}.json
  full timeline       -> logs/{draft_id}_{cid}.json

Usage: python3 -m engine.review <draft_id>
"""
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from engine import _llm

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
SOLVES = ROOT / "solves"
POOL = ROOT / "pool"
DEAD_LETTER = ROOT / "dead_letter"
LOGS = ROOT / "logs"
PROMPTS = ROOT / "prompts"

MAX_ROUNDS = 2
PROBLEM_FIELDS = ("content", "answer", "rubric", "hints")

COMPARE_PROMPT = """You check whether two independent solvers reached the reference answer of a puzzle.
Judge meaning, not wording: equivalent numbers, units, or phrasings count as a match.
Return JSON: {"solver1_matches": bool, "solver2_matches": bool, "solvers_agree": bool, "notes": str}
solvers_agree compares the two solver answers with each other, regardless of the reference."""

REVISE_PROMPT = """You revise a daily reasoning puzzle according to the judge's revision notes.
Fix exactly what the notes ask for; keep the domain, tag, level and language (Vietnamese) unchanged.
Make sure the answer, rubric and hints match the revised content.
Return JSON: {"content": str, "answer": str, "rubric": str, "hints": [str, ...]}"""


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _load_prompt(name):
    path = PROMPTS / f"{name}.md"
    text = path.read_text(encoding="utf-8")
    # Placeholder files hold only an HTML comment; refuse to spend API calls on them.
    if not re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL).strip():
        raise _llm.LLMError(f"{path} has no prompt content yet.")
    return text


def _problem(draft, cand):
    return {
        "domain_id": cand.get("domain_id"),
        "tag": draft.get("tag"),
        "level": draft.get("level"),
        **{k: cand[k] for k in PROBLEM_FIELDS},
    }


def _dead_letter(draft_id, cand, reason, timeline, details=None):
    timeline.update(outcome="dead_letter", reason=reason, finished_at=_now())
    _write_json(DEAD_LETTER / f"{draft_id}_{cand['cid']}.json", {
        "draft_id": draft_id,
        "cid": cand["cid"],
        "reason": reason,
        "details": details,
        "candidate": cand,
        "timestamp": _now(),
    })
    return f"dead_letter:{reason}"


def _check_solvability(draft_id, draft, cand, timeline):
    """Returns True when both solvers reached the reference answer."""
    solves = []
    for solver_id in (1, 2):
        path = SOLVES / f"{draft_id}_{cand['cid']}_solver{solver_id}.json"
        if not path.exists():
            raise FileNotFoundError(f"{path} is missing; run engine/solve.py on this draft first.")
        solves.append(_read_json(path))
    result = _llm.call_haiku(COMPARE_PROMPT, {
        "problem": cand["content"],
        "reference_answer": cand["answer"],
        "solver1_answer": solves[0].get("answer"),
        "solver2_answer": solves[1].get("answer"),
    }, agent="solvability_check")
    timeline["solvability"] = result
    timeline["events"].append({"at": _now(), "step": "solvability", "result": result})
    return bool(result.get("solver1_matches")) and bool(result.get("solver2_matches"))


def _review_candidate(draft_id, draft, cand, prompts):
    timeline = {"draft_id": draft_id, "cid": cand["cid"], "started_at": _now(),
                "solvability": None, "rounds": [], "events": []}
    try:
        if not _check_solvability(draft_id, draft, cand, timeline):
            return _dead_letter(draft_id, cand, "solvability_fail", timeline, timeline["solvability"])

        for round_no in range(1, MAX_ROUNDS + 1):
            problem = _problem(draft, cand)
            attacks = _llm.call_opus(prompts["red_team"], {"problem": problem}, agent="red_team")
            defense = _llm.call_sonnet(prompts["defender"], {"problem": problem, "attacks": attacks},
                                       agent="defender")
            judgment = _llm.call_opus(prompts["judge"], {"problem": problem, "attacks": attacks,
                                                         "defense": defense}, agent="judge")
            verdict = str(judgment.get("verdict", "")).upper()
            timeline["rounds"].append({"round": round_no, "problem": problem, "attacks": attacks,
                                       "defense": defense, "judgment": judgment, "verdict": verdict})
            timeline["events"].append({"at": _now(), "step": f"round_{round_no}", "verdict": verdict})

            if verdict == "PASS":
                pool_id = str(uuid.uuid4())
                _write_json(POOL / f"{pool_id}.json", {
                    "id": pool_id, "draft_id": draft_id, "cid": cand["cid"],
                    "date": draft.get("date"), **problem,
                    "review": {"rounds": round_no, "verdict": verdict}, "created_at": _now(),
                })
                timeline.update(outcome="pool", pool_id=pool_id, finished_at=_now())
                return "pool"
            if verdict == "FAIL":
                return _dead_letter(draft_id, cand, "judge_fail", timeline, judgment)
            if verdict != "REVISE":
                return _dead_letter(draft_id, cand, "invalid_verdict", timeline, judgment)
            if round_no == MAX_ROUNDS:
                return _dead_letter(draft_id, cand, "max_revision_exceeded", timeline, judgment)

            revised = _llm.call_opus(REVISE_PROMPT, {"problem": problem,
                                                     "revision_notes": judgment.get("revision_notes")},
                                     agent="reviser")
            missing = [k for k in PROBLEM_FIELDS if k not in revised]
            if missing:
                return _dead_letter(draft_id, cand, "invalid_revision", timeline, {"missing": missing})
            cand = {**cand, **{k: revised[k] for k in PROBLEM_FIELDS}}
            timeline["events"].append({"at": _now(), "step": f"revision_{round_no}", "revised": revised})
        raise AssertionError("unreachable: every round returns")
    except Exception as exc:
        # API/parse failures abort the draft; metrics skip timelines marked "error".
        timeline.update(outcome="error", reason=f"{type(exc).__name__}: {exc}", finished_at=_now())
        raise
    finally:
        _write_json(LOGS / f"{draft_id}_{cand['cid']}.json", timeline)


def review_draft(draft_id):
    draft = _read_json(DRAFTS / f"{draft_id}.json")
    prompts = {name: _load_prompt(name) for name in ("red_team", "defender", "judge")}
    return {cand["cid"]: _review_candidate(draft_id, draft, cand, prompts)
            for cand in draft["candidates"]}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m engine.review <draft_id>")
    print(json.dumps(review_draft(sys.argv[1]), ensure_ascii=False, indent=2))
