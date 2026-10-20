"""Vet a draft (commands/vet.md): solvability gate, then a Red Team / Defender / Judge debate.

Draft schema: see commands/gen.md. Solver files must exist first (engine/solve.py).
Prompts: prompts/{compare,red_team,defender,judge,reviser}.md

Outcomes per candidate:
  PASS                     -> pool/{uuid}.json
  answer_key_suspect       -> human_review/{draft_id}_{cid}.json
  any other failure        -> dead_letter/{draft_id}_{cid}.json
  full timeline            -> logs/{draft_id}_{cid}.json

Usage: python3 -m engine.review <draft_id>
"""
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

from engine import _llm, solve

ROOT = Path(__file__).resolve().parent.parent
DRAFTS = ROOT / "drafts"
SOLVES = ROOT / "solves"
POOL = ROOT / "pool"
DEAD_LETTER = ROOT / "dead_letter"
HUMAN_REVIEW = ROOT / "human_review"
LOGS = ROOT / "logs"

MAX_ROUNDS = 2
PROMPT_NAMES = ("compare", "red_team", "defender", "judge", "reviser")
REVISABLE_FIELDS = ("content", "answer", "rubric", "hints", "claims_to_verify")


class MissingSolves(RuntimeError):
    pass


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _solve_paths(draft_id, cid):
    return [SOLVES / f"{draft_id}_{cid}_solver{n}.json" for n in solve.SOLVERS]


def _check_solvability(cand, solves, prompts, timeline):
    """Gate before the debate. Returns (decision, solver_signals, comparison).

    decision: "pass", "unsolvable", "solvability_fail" or "answer_key_suspect".
    """
    unsolvable = [bool(solves[n].get("unsolvable")) for n in (1, 2)]
    signals = {"solver1_answer": solves[1].get("solver_answer"),
               "solver2_answer": solves[2].get("solver_answer"),
               "solver1_unsolvable": unsolvable[0], "solver2_unsolvable": unsolvable[1]}
    cmp = None
    if all(unsolvable):
        decision = "unsolvable"
    elif cand.get("tag_type") == "explore":
        decision = "pass"  # open-ended: there is no single answer to match
    else:
        cmp = _llm.call_sonnet(prompts["compare"], {
            "content": cand["content"], "answer": cand["answer"],
            "solver1_answer": signals["solver1_answer"], "solver2_answer": signals["solver2_answer"],
        }, agent="solvability_check")
        m1, m2 = bool(cmp.get("solver1_matches")), bool(cmp.get("solver2_matches"))
        signals.update(solver1_matches=m1, solver2_matches=m2, solver_split=m1 != m2,
                       comparison_notes=cmp.get("notes"))
        if m1 or m2:
            decision = "pass"
        elif cmp.get("solvers_agree"):
            decision = "answer_key_suspect"  # two different models converge away from the key
        else:
            decision = "solvability_fail"
    timeline["solvability_checks"].append({"at": _now(), "decision": decision, "signals": signals,
                                           "comparison": cmp})
    if timeline["solvability"] is None and cmp is not None:
        timeline["solvability"] = cmp  # metrics use the first comparison
    return decision, signals, cmp


def _finish(draft_id, cand, timeline, outcome, reason, label, sentence, details=None):
    timeline.update(outcome=outcome, reason=reason, finished_at=_now())
    if outcome in ("dead_letter", "human_review"):
        target = DEAD_LETTER if outcome == "dead_letter" else HUMAN_REVIEW
        record = {"draft_id": draft_id, "cid": cand["cid"], "reason": reason, "details": details,
                  "candidate": cand, "timestamp": _now()}
        if outcome == "human_review":
            record["flag"] = reason
        _write_json(target / f"{draft_id}_{cand['cid']}.json", record)
    return {"label": label, "reason": sentence, "outcome": outcome, "detail": reason}


def _gate_failure(draft_id, cand, timeline, decision, signals):
    if decision == "answer_key_suspect":
        return _finish(draft_id, cand, timeline, "human_review", decision, "FAIL",
                       "2 solver khác model cùng ra một đáp án khác key, nghi key sai; chuyển human_review/",
                       signals)
    if decision == "unsolvable":
        return _finish(draft_id, cand, timeline, "dead_letter", "unsolvable", "FAIL",
                       "cả 2 solver đều báo đề thiếu dữ kiện", signals)
    return _finish(draft_id, cand, timeline, "dead_letter", "solvability_fail", "FAIL",
                   f"không solver nào ra đúng đáp án ({signals.get('comparison_notes') or ''})", signals)


def _review_candidate(draft_id, cand, prompts):
    problem_id = f"{draft_id}_{cand['cid']}"
    timeline = {"draft_id": draft_id, "cid": cand["cid"], "started_at": _now(),
                "solvability": None, "solvability_checks": [], "rounds": [], "events": []}
    try:
        solves = {n: _read_json(p) for n, p in zip(solve.SOLVERS, _solve_paths(draft_id, cand["cid"]))}
        decision, signals, _ = _check_solvability(cand, solves, prompts, timeline)
        timeline["events"].append({"at": _now(), "step": "solvability", "decision": decision})
        if decision != "pass":
            return _gate_failure(draft_id, cand, timeline, decision, signals)

        for round_no in range(1, MAX_ROUNDS + 1):
            base = {"problem_id": problem_id, "content": cand["content"], "answer": cand["answer"],
                    "level": cand.get("level"), "tag_type": cand.get("tag_type")}
            web = bool(cand.get("claims_to_verify")) or cand.get("tag_type") == "lookup"
            attacks = _llm.call_opus(prompts["red_team"], {
                **base, "claims_to_verify": cand.get("claims_to_verify") or [], "solver_signals": signals,
            }, agent="red_team", web_search=web)
            defense = _llm.call_sonnet(prompts["defender"], {**base, "attacks": attacks.get("attacks", [])},
                                       agent="defender")
            judgment = _llm.call_opus(prompts["judge"], {
                **base, "attacks": attacks.get("attacks", []), "defenses": defense.get("responses", []),
                "round": round_no,
            }, agent="judge")
            decision = str(judgment.get("decision") or judgment.get("verdict") or "").upper()
            reason = str(judgment.get("reason") or "").strip()
            timeline["rounds"].append({"round": round_no, "problem": dict(cand), "attacks": attacks,
                                       "defense": defense, "judgment": judgment, "verdict": decision})
            timeline["events"].append({"at": _now(), "step": f"round_{round_no}", "verdict": decision})

            if decision == "PASS":
                pool_id = str(uuid.uuid4())
                entry = {k: v for k, v in cand.items() if k != "reasoning_chain"}
                _write_json(POOL / f"{pool_id}.json", {
                    "id": pool_id, "draft_id": draft_id, **entry,
                    "generator_level": cand.get("level"),
                    "level": judgment.get("final_level") or cand.get("level"),
                    "review": {"rounds": round_no, "reason": reason,
                               "confidence": judgment.get("confidence"), "solver_signals": signals},
                    "created_at": _now(),
                })
                timeline["pool_id"] = pool_id
                return _finish(draft_id, cand, timeline, "pool", "pass", "PASS", reason or "judge cho qua")
            if decision == "FAIL":
                return _finish(draft_id, cand, timeline, "dead_letter", "judge_fail", "FAIL",
                               reason or "judge đánh trượt", judgment)
            if decision != "REVISE":
                return _finish(draft_id, cand, timeline, "dead_letter", "invalid_verdict", "FAIL",
                               f"judge trả decision không hợp lệ: {decision!r}", judgment)
            if round_no == MAX_ROUNDS:
                return _finish(draft_id, cand, timeline, "dead_letter", "max_revision_exceeded", "REVISE",
                               f"hết {MAX_ROUNDS} vòng mà judge vẫn yêu cầu sửa", judgment)

            revised = _llm.call_opus(prompts["reviser"], {
                **{k: cand.get(k) for k in REVISABLE_FIELDS},
                "revision_notes": judgment.get("revision_notes") or reason,
            }, agent="reviser")
            missing = [k for k in ("content", "answer") if not revised.get(k)]
            if missing:
                return _finish(draft_id, cand, timeline, "dead_letter", "invalid_revision", "FAIL",
                               f"reviser thiếu trường {missing}", revised)
            cand = {**cand, **{k: revised[k] for k in REVISABLE_FIELDS if k in revised}}
            timeline["events"].append({"at": _now(), "step": f"revision_{round_no}",
                                       "answer_changed": revised.get("answer_changed"),
                                       "changes_summary": revised.get("changes_summary")})

            # Any revision can change solvability, so both solvers re-solve it blind every time.
            resolves = solve.solve_candidate(draft_id, cand, tag=f"_rev{round_no}")
            decision, signals, _ = _check_solvability(cand, resolves, prompts, timeline)
            timeline["events"].append({"at": _now(), "step": f"resolve_{round_no}", "decision": decision})
            if decision != "pass":
                return _gate_failure(draft_id, cand, timeline, decision, signals)
        raise AssertionError("unreachable: every round returns")
    except Exception as exc:
        # API/parse failures abort the draft; metrics skip timelines marked "error".
        timeline.update(outcome="error", reason=f"{type(exc).__name__}: {exc}", finished_at=_now())
        raise
    finally:
        _write_json(LOGS / f"{draft_id}_{cand['cid']}.json", timeline)


def review_draft(draft_id):
    draft = _read_json(DRAFTS / f"{draft_id}.json")
    missing = [p.name for c in draft["candidates"] for p in _solve_paths(draft_id, c["cid"]) if not p.exists()]
    if missing:
        raise MissingSolves(f"Chạy /solve trước (thiếu: {', '.join(missing)})")
    prompts = {name: _llm.load_prompt(name) for name in PROMPT_NAMES}
    return {cand["cid"]: _review_candidate(draft_id, cand, prompts) for cand in draft["candidates"]}


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: python3 -m engine.review <draft_id>")
    try:
        results = review_draft(sys.argv[1])
    except MissingSolves as exc:
        sys.exit(str(exc))
    for cid, r in results.items():
        print(f"{cid}: {r['label']} — {r['reason']}")
