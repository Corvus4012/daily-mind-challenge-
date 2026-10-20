"""Smoke test: run solve -> review (incl. REVISE + re-solve) -> metrics on 1 domain, 1 candidate.

The API is stubbed (no key or network needed) and everything runs in a temporary
copy of engine/, so the repo's drafts/, pool/, logs/ etc. stay untouched.
Outputs are placeholders; the test only checks that the pipeline runs without errors.

Usage: python3 test_smoke.py
"""
import json
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

REPO = Path(__file__).resolve().parent
DRAFT_ID = "2026-01-01_3"


def _fake_create_message(model, system, user_content, agent, _state={"judge_calls": 0}):
    if agent.startswith("solver"):
        out = {"answer": "p = 12", "reasoning": "stub"}
    elif agent == "solvability_check":
        out = {"solver1_matches": True, "solver2_matches": True, "solvers_agree": True, "notes": "stub"}
    elif agent == "red_team":
        out = {"attacks": [{"type": "C2", "severity": 2, "claim": "stub attack"}]}
    elif agent == "defender":
        out = {"responses": [{"attack": "C2", "response": "stub defense"}]}
    elif agent == "judge":
        _state["judge_calls"] += 1
        verdict = "REVISE" if _state["judge_calls"] == 1 else "PASS"
        out = {"verdict": verdict, "reason": "stub", "revision_notes": "stub: clarify premise"}
    elif agent == "reviser":
        out = {"content": "Revised stub puzzle.", "answer": "p = 12", "rubric": "stub", "hints": ["h1", "h2", "h3"]}
    else:
        raise AssertionError(f"unexpected agent {agent!r}")
    text = json.dumps(out, ensure_ascii=False)
    if agent == "defender":
        text = f"Here is my reply:\n```json\n{text}\n```"  # exercises the regex JSON fallback
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200),
        stop_reason="end_turn",
        stop_details=None,
    )


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        shutil.copytree(REPO / "engine", tmp / "engine", ignore=shutil.ignore_patterns("__pycache__"))
        for d in ("drafts", "solves", "pool", "dead_letter", "human_review", "logs", "prompts"):
            (tmp / d).mkdir()
        for name in ("red_team", "defender", "judge"):
            (tmp / "prompts" / f"{name}.md").write_text(f"Smoke-test {name} prompt.\n", encoding="utf-8")
        draft = {
            "draft_id": DRAFT_ID, "date": "2026-01-01", "domain_id": 3, "target_level": 2,
            "candidates": [{
                "cid": "c1", "domain_id": 3, "level": 2, "tag_type": "reason", "format": "fill-in",
                "content": "Stub puzzle: find the stable price p.",
                "answer": "p = 12", "rubric": "stub", "hints": ["h1", "h2", "h3"],
                "claims_to_verify": [], "reasoning_chain": "stub self-check C1-C5",
            }],
        }
        (tmp / "drafts" / f"{DRAFT_ID}.json").write_text(json.dumps(draft), encoding="utf-8")

        sys.path.insert(0, str(tmp))
        from engine import _llm, metrics, review, solve
        assert Path(_llm.__file__).parent == tmp / "engine", "imported the repo copy instead of the temp copy"
        _llm._create_message = _fake_create_message

        print("solve_draft:", solve.solve_draft(DRAFT_ID))
        outcome = review.review_draft(DRAFT_ID)
        print("review_draft:", outcome)

        timeline = json.loads((tmp / "logs" / f"{DRAFT_ID}_c1.json").read_text(encoding="utf-8"))
        print("timeline:", [e["step"] + "=" + str(e.get("verdict") or e.get("decision") or "ok") for e in timeline["events"]])
        print("solve files:", sorted(p.name for p in (tmp / "solves").glob("*.json")))
        pool_files = list((tmp / "pool").glob("*.json"))
        print("pool files:", len(pool_files), "| dead_letter files:", len(list((tmp / "dead_letter").glob("*.json"))))
        costs = [json.loads(line) for line in (tmp / "logs" / "cost.jsonl").read_text().splitlines()]
        print(f"cost log: {len(costs)} calls, ${sum(c['cost_usd'] for c in costs):.4f} (stubbed token counts)")
        metrics.compute_metrics()

        assert outcome["c1"]["label"] == "PASS" and outcome["c1"]["outcome"] == "pool", outcome
        assert len(list((tmp / "solves").glob("*_rev1_solver*.json"))) == 2, "revision was not re-solved"
        assert len(pool_files) == 1
        assert json.loads(pool_files[0].read_text(encoding="utf-8"))["content"] == "Revised stub puzzle."
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
