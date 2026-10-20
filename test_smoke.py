"""Smoke test: run solve -> vet (incl. REVISE + re-solve) -> metrics on 1 domain, 1 candidate.

The API is stubbed (no key or network needed) and everything runs in a temporary
copy of engine/ and prompts/, so the repo's drafts/, pool/, logs/ etc. stay untouched.
The real prompt files are rendered, so a placeholder without a value fails the test.
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
CALLS = []


def fake_output(agent, judge_call):
    if agent.startswith("solver"):
        return {"solver_reasoning": "stub", "solver_answer": "p = 12", "unsolvable": False}
    if agent == "solvability_check":
        return {"solver1_matches": True, "solver2_matches": True, "solvers_agree": True, "notes": "stub"}
    if agent == "red_team":
        return {"problem_id": DRAFT_ID + "_c1", "checklist": {}, "verdict": "revise",
                "attacks": [{"type": "ambiguity", "severity": 2, "detail": "stub", "suggested_fix": "stub"}]}
    if agent == "defender":
        return {"responses": [{"attack_index": 0, "stance": "partial", "counter": "stub",
                               "proposed_revision": "stub"}]}
    if agent == "judge":
        decision = "REVISE" if judge_call == 1 else "PASS"
        return {"decision": decision, "reason": "stub", "revision_notes": "stub: clarify premise",
                "final_level": 2, "confidence": 0.8}
    if agent == "reviser":
        return {"content": "Revised stub puzzle.", "answer": "p = 12", "rubric": "stub",
                "hints": ["h1", "h2", "h3"], "claims_to_verify": [], "answer_changed": False,
                "changes_summary": "stub"}
    raise AssertionError(f"unexpected agent {agent!r}")


def fake_create_message(model, system, messages, agent, tools):
    CALLS.append((agent, model, bool(tools)))
    judge_call = sum(1 for a, _, _ in CALLS if a == "judge")
    text = json.dumps(fake_output(agent, judge_call), ensure_ascii=False)
    if agent == "defender":
        text = f"Here is my reply:\n```json\n{text}\n```"  # exercises the regex JSON fallback
    return SimpleNamespace(
        content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=1000, output_tokens=200, server_tool_use=None),
        stop_reason="end_turn",
        stop_details=None,
    )


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for d in ("engine", "prompts"):
            shutil.copytree(REPO / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        for d in ("drafts", "solves", "pool", "dead_letter", "human_review", "logs"):
            (tmp / d).mkdir()
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
        _llm._create_message = fake_create_message

        print("solve_draft:", solve.solve_draft(DRAFT_ID))
        results = review.review_draft(DRAFT_ID)
        for cid, r in results.items():
            print(f"vet: {cid}: {r['label']} — {r['reason']}")

        timeline = json.loads((tmp / "logs" / f"{DRAFT_ID}_c1.json").read_text(encoding="utf-8"))
        print("timeline:", [e["step"] + "=" + str(e.get("verdict") or e.get("decision") or "ok")
                            for e in timeline["events"]])
        print("agent -> model:", {a: m for a, m, _ in CALLS})
        pool_files = list((tmp / "pool").glob("*.json"))
        costs = [json.loads(line) for line in (tmp / "logs" / "cost.jsonl").read_text().splitlines()]
        print(f"cost log: {len(costs)} calls, ${sum(c['cost_usd'] for c in costs):.4f} (stubbed token counts)")
        metrics.compute_metrics()

        assert results["c1"]["label"] == "PASS" and results["c1"]["outcome"] == "pool", results
        assert len(pool_files) == 1
        entry = json.loads(pool_files[0].read_text(encoding="utf-8"))
        assert entry["content"] == "Revised stub puzzle." and "reasoning_chain" not in entry
        assert len(list((tmp / "solves").glob("*_rev1_solver*.json"))) == 2, "revision was not re-solved"
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
