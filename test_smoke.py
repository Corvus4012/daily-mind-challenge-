"""Smoke test for the state tools: plan -> add/reject -> pick -> hint -> reveal -> close -> metrics.

Runs engine/ against a temporary copy of state/, so the real pool, history and logs stay untouched.
Generation and vetting happen in a Claude session (commands/restock.md), not here.

Usage: python3 test_smoke.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent


def dmc(tmp, *args, ok=True):
    proc = subprocess.run([sys.executable, "engine/dmc.py", *args], cwd=tmp, capture_output=True, text=True)
    if ok and proc.returncode != 0:
        raise AssertionError(f"dmc {args} failed: {proc.stderr or proc.stdout}")
    return proc


def candidate(domain_id, level, **over):
    c = {
        "domain_id": domain_id, "level": level, "tag": "reason", "format": "fill-in",
        "skills": ["common_cause"], "est_minutes": 8,
        "challenge_md": f"Stub puzzle for domain {domain_id}.",
        "hints": ["h1", "h2", "h3"], "answer": "đáp án mẫu", "rubric": "rubric mẫu", "claims": [],
        "review": {"solver_model": "sonnet", "first_solve_match": True, "revised": False, "issues": []},
    }
    c.update(over)
    return c


def main():
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        for d in ("engine", "state"):
            shutil.copytree(REPO / d, tmp / d, ignore=shutil.ignore_patterns("__pycache__"))
        (tmp / "state" / "current.json").unlink(missing_ok=True)

        plan = json.loads(dmc(tmp, "plan", "3").stdout)
        print("plan:", [(s["domain_id"], s["level"], s["tag"], s["target_skill"]) for s in plan["slots"]])

        files = {
            "a": candidate(1, 2), "b": candidate(2, 3, format="mc"), "c": candidate(9, 2, skills=["unit_choice"]),
            "bad": candidate(4, 2, hints=["only one"]),
            "rej": dict(candidate(5, 2), reason="trivia: googleable",
                        review={"first_solve_match": False, "issues": [{"type": "trivia", "severity": 3}]}),
        }
        for name, c in files.items():
            (tmp / f"{name}.json").write_text(json.dumps(c, ensure_ascii=False), encoding="utf-8")
        for name in ("a", "b", "c"):
            print("add:", json.loads(dmc(tmp, "add", f"{name}.json").stdout))
        bad = dmc(tmp, "add", "bad.json", ok=False)
        assert bad.returncode != 0 and "hints" in bad.stderr, bad.stderr
        print("add invalid -> rejected by validation:", bad.stderr.strip()[:70])
        print("reject:", json.loads(dmc(tmp, "reject", "rej.json").stdout))
        pool = list((tmp / "pool").glob("*.json"))
        assert len(pool) == 3 and "answer" not in json.loads(pool[0].read_text()), "answers must be encoded"

        picked = json.loads(dmc(tmp, "pick").stdout)
        print("pick:", {k: picked[k] for k in ("status", "domain", "level", "level_mode", "pool_left")})
        assert picked["status"] == "picked" and picked["pool_left"] == 2
        assert json.loads(dmc(tmp, "pick").stdout)["status"] == "already"

        for _ in range(4):
            print("hint:", json.loads(dmc(tmp, "hint").stdout))
        revealed = json.loads(dmc(tmp, "reveal").stdout)
        assert revealed["answer"] == "đáp án mẫu" and revealed["hints_revealed"] == 3
        skill = json.loads((tmp / "state" / "current.json").read_text())["skills"][0]
        assert dmc(tmp, "close", json.dumps({"result": "partial", "skills_missed": ["nope"]}), ok=False).returncode
        dmc(tmp, "close", json.dumps({"result": "partial", "skills_missed": [skill], "notes": "smoke"}))
        last = json.loads((tmp / "state" / "history.jsonl").read_text().splitlines()[-1])
        print("history:", {k: last[k] for k in ("date", "result", "hints_used", "skills", "skills_missed")})
        assert last["hints_used"] == 3 and last["skills_missed"] == [skill]
        assert dmc(tmp, "hint", ok=False).returncode != 0, "submitted challenge must not reveal more hints"

        print(subprocess.run([sys.executable, "engine/metrics.py"], cwd=tmp, capture_output=True,
                             text=True, check=True).stdout.rstrip())
    print("SMOKE TEST PASSED")


if __name__ == "__main__":
    main()
