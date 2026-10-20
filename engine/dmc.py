#!/usr/bin/env python3
"""Daily Mind Challenge state tool: the pool of vetted puzzles and today's challenge.

Usage (run from the repo root):
  python3 engine/dmc.py status            # pool inventory, base level, skills due for review
  python3 engine/dmc.py plan N            # N restock slots (domain, level, tag, target skill)
  python3 engine/dmc.py skills            # the skill vocabulary
  python3 engine/dmc.py add FILE          # vetted candidate -> pool/ (answer/rubric base64), log "accepted"
  python3 engine/dmc.py reject FILE       # log a rejected candidate (never enters the pool)
  python3 engine/dmc.py pick              # roll today and move the best pool puzzle to state/current.json
  python3 engine/dmc.py hint              # reveal the next hint
  python3 engine/dmc.py reveal            # print answer + rubric (only after the user has answered)
  python3 engine/dmc.py close JSON        # log today's result to history and mark the challenge submitted

"Today" is the calendar date in Asia/Ho_Chi_Minh.
"""
import base64
import json
import random
import sys
import uuid
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import roll  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "pool"
CURRENT = ROOT / "state" / "current.json"
REVIEW_LOG = ROOT / "logs" / "review.jsonl"

SKILLS = {
    "false_dilemma": "Thấy phương án/nguyên nhân bị bỏ sót",
    "common_cause": "Tìm giả thuyết giải thích được mọi quan sát cùng lúc",
    "evidence_strength": "Bằng chứng có phân biệt được các giả thuyết không",
    "base_rate": "Tỉ lệ nền",
    "conditional_prob": "Xác suất có điều kiện",
    "selection_bias": "Sai lệch chọn mẫu",
    "regression_to_mean": "Hồi quy về trung bình",
    "absolute_vs_relative": "Tuyệt đối vs tương đối",
    "weighted_average": "Trung bình có trọng số",
    "unit_choice": "Chọn đơn vị/thước đo cho đúng câu hỏi",
    "nonlinearity": "Quan hệ phi tuyến (lũy tiến, nghịch đảo, lãi kép)",
    "marginal_thinking": "Tư duy biên",
    "opportunity_cost": "Chi phí cơ hội",
    "incentives": "Động cơ và phản ứng hành vi",
    "adverse_selection": "Lựa chọn ngược, thông tin bất cân xứng",
    "equilibrium": "Cân bằng, điểm bền",
    "confounding": "Biến gây nhiễu",
    "causal_inference": "Tương quan vs nhân quả",
    "experiment_design": "Thiết kế phép thử phân biệt giả thuyết",
    "ambiguity_detection": "Phát hiện câu nhiều nghĩa",
    "hidden_premise": "Tiền đề ngầm",
    "self_check": "Dùng chính kết quả của mình để kiểm lại",
    "interpret_result": "Dịch kết quả tính toán thành ý nghĩa, hành vi",
    "estimation": "Ước lượng",
    "consistency_check": "Kiểm tra nhất quán với nguyên tắc đã nêu",
    "convention_mismatch": "Quy ước khác nhau gây hiểu nhầm",
    "framing": "Cách trình bày làm lệch nhận thức",
    "source_evaluation": "Đánh giá nguồn tin",
}
TAGS = ("reason", "lookup", "explore")
REVIEW_DUE_AFTER_DAYS = 2


def today():
    return datetime.now(roll.TZ).date().isoformat()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _out(data):
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _b64(text):
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def _unb64(text):
    return base64.b64decode(text).decode("utf-8")


def load_pool():
    return [_read(p) for p in sorted(POOL.glob("*.json"))]


def due_skills(hist, on_date):
    """Skills missed at least REVIEW_DUE_AFTER_DAYS ago and not shown correctly since."""
    due = {}
    for i, h in enumerate(hist):
        for skill in h.get("skills_missed", []):
            later_ok = any(skill in g.get("skills", []) and skill not in g.get("skills_missed", [])
                           for g in hist[i + 1:])
            age = (date.fromisoformat(on_date) - date.fromisoformat(h["date"])).days
            if not later_ok and age >= REVIEW_DUE_AFTER_DAYS:
                due.setdefault(skill, {"skill": skill, "label": SKILLS.get(skill, skill),
                                       "missed_on": h["date"], "missed_in_domain": h["domain_id"]})
            elif later_ok:
                due.pop(skill, None)
    return sorted(due.values(), key=lambda d: d["missed_on"])


def _count(items, key):
    out = {}
    for it in items:
        out[it[key]] = out.get(it[key], 0) + 1
    return dict(sorted(out.items()))


def cmd_status():
    hist, pool = roll.load(), load_pool()
    _out({
        "today": today(),
        "base_level": roll.current_level(hist),
        "pool_size": len(pool),
        "pool_by_domain": {f"{d}. {roll.DOMAINS[d]}": n for d, n in _count(pool, "domain_id").items()},
        "pool_by_level": _count(pool, "level"),
        "pool_by_tag": _count(pool, "tag"),
        "due_skills": due_skills(hist, today()),
    })


def cmd_plan(n):
    """Restock slots: levels follow the daily roll (70/20/10), domains favour thin pool + least recent use."""
    hist, pool = roll.load(), load_pool()
    base = roll.current_level(hist)
    stretch = max(1, round(n * 0.2)) if n >= 3 else 0
    wild = 1 if n >= 7 else 0
    levels = [min(5, base + 2)] * wild + [min(5, base + 1)] * stretch + [base] * (n - stretch - wild)
    tags = ["reason"] * n
    if n >= 5:
        tags[-1] = "lookup"
    if n >= 10:
        tags[-2] = "explore"
    in_pool = _count(pool, "domain_id")
    last_used = {h["domain_id"]: i for i, h in enumerate(hist)}
    rng = random.Random()
    order = sorted(roll.DOMAINS, key=lambda d: (in_pool.get(d, 0), last_used.get(d, -1), rng.random()))
    slots = [{"slot": i + 1, "domain_id": order[i % len(order)], "domain": roll.DOMAINS[order[i % len(order)]],
              "level": levels[i], "tag": tags[i], "target_skill": None} for i in range(n)]
    # Transfer practice: retest each due skill at base level, in a different domain from where it was missed.
    for d in due_skills(hist, today()):
        slot = next((s for s in sorted(slots, key=lambda s: s["level"] != base)
                     if s["target_skill"] is None and s["domain_id"] != d["missed_in_domain"]
                     and s["tag"] == "reason"), None)
        if slot:
            slot["target_skill"] = d["skill"]
    _out({"base_level": base, "slots": slots})


def _validate(c, for_pool):
    errors = []
    if c.get("domain_id") not in roll.DOMAINS:
        errors.append("domain_id must be 1-12")
    if not isinstance(c.get("level"), int) or not 1 <= c["level"] <= 5:
        errors.append("level must be an int 1-5")
    if c.get("tag") not in TAGS:
        errors.append(f"tag must be one of {TAGS}")
    unknown = [s for s in c.get("skills", []) if s not in SKILLS]
    if unknown:
        errors.append(f"unknown skills {unknown}; see `dmc.py skills`")
    if for_pool:
        for key in ("format", "challenge_md", "answer", "rubric"):
            if not isinstance(c.get(key), str) or not c[key].strip():
                errors.append(f"{key} must be a non-empty string")
        if not isinstance(c.get("hints"), list) or len(c["hints"]) != 3:
            errors.append("hints must be a list of 3 strings (direction -> concrete)")
        if not c.get("skills"):
            errors.append("skills must list at least one skill")
        if not isinstance(c.get("est_minutes"), int):
            errors.append("est_minutes must be an int")
        review = c.get("review") or {}
        if "first_solve_match" not in review:
            errors.append("review.first_solve_match is required (did the first blind solver match the key?)")
    if errors:
        sys.exit("invalid candidate: " + "; ".join(errors))


def _log_review(c, outcome, pool_id=None):
    review = c.get("review") or {}
    entry = {
        "timestamp": datetime.now(roll.TZ).isoformat(timespec="seconds"),
        "outcome": outcome,
        "pool_id": pool_id,
        "domain_id": c.get("domain_id"),
        "level": c.get("level"),
        "tag": c.get("tag"),
        "format": c.get("format"),
        "skills": c.get("skills", []),
        "first_solve_match": review.get("first_solve_match"),
        "revised": bool(review.get("revised")),
        "issues": review.get("issues", []),
        "solver_model": review.get("solver_model"),
    }
    if outcome == "rejected":
        entry["reason"] = c.get("reason") or review.get("reason")
        entry["challenge_md"] = c.get("challenge_md")
    REVIEW_LOG.parent.mkdir(parents=True, exist_ok=True)
    with REVIEW_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def cmd_add(path):
    c = _read(path)
    _validate(c, for_pool=True)
    pool_id = f"{today().replace('-', '')}-d{c['domain_id']:02d}-{uuid.uuid4().hex[:6]}"
    entry = {"id": pool_id, "created": today(),
             **{k: v for k, v in c.items() if k not in ("answer", "rubric")},
             "answer_b64": _b64(c["answer"]), "rubric_b64": _b64(c["rubric"])}
    _write(POOL / f"{pool_id}.json", entry)
    _log_review(c, "accepted", pool_id)
    _out({"added": pool_id})


def cmd_reject(path):
    c = _read(path)
    _validate(c, for_pool=False)
    _log_review(c, "rejected")
    _out({"rejected": c.get("reason") or (c.get("review") or {}).get("reason")})


def cmd_pick():
    t = today()
    if CURRENT.exists():
        cur = _read(CURRENT)
        if cur.get("date") == t:
            _out({"status": "already", "current_status": cur.get("status"), "challenge_md": cur["challenge_md"]})
            return
        if cur.get("status") == "open":
            _out({"status": "open_previous", "date": cur.get("date"), "domain_id": cur.get("domain_id")})
            sys.exit(3)
    hist = roll.load()
    # Seeded by date: re-running pick on the same day (e.g. after a just-in-time restock) gives the same roll.
    r = roll.roll(t, hist, random.Random(t))
    due = {d["skill"] for d in due_skills(hist, t)}
    rank = {d: i for i, d in enumerate(r["eligible_domain_ids"])}
    candidates = [p for p in load_pool()
                  if p["domain_id"] in rank and abs(p["level"] - r["rolled_level"]) <= 1]
    if not candidates:
        _out({"status": "empty", "roll": r})
        sys.exit(2)
    best = min(candidates, key=lambda p: (
        abs(p["level"] - r["rolled_level"]),
        p["tag"] != r["rolled_tag"],
        not (due & set(p.get("skills", []))),
        rank[p["domain_id"]],
        p["id"],
    ))
    _write(CURRENT, {
        "date": t, "pool_id": best["id"], "domain_id": best["domain_id"], "tag": best["tag"],
        "level": best["level"], "base_level": r["current_level"], "rolled_level": r["rolled_level"],
        "level_mode": r["level_mode"], "est_minutes": best["est_minutes"], "format": best["format"],
        "skills": best["skills"], "challenge_md": best["challenge_md"], "hints": best["hints"],
        "hints_revealed": 0, "answer_key_b64": best["answer_b64"], "rubric_b64": best["rubric_b64"],
        "review": best.get("review"), "status": "open",
    })
    (POOL / f"{best['id']}.json").unlink()
    _out({"status": "picked", "pool_id": best["id"], "date": t, "domain": roll.DOMAINS[best["domain_id"]],
          "tag": best["tag"], "level": best["level"], "level_mode": r["level_mode"],
          "est_minutes": best["est_minutes"], "targets_due_skill": sorted(due & set(best["skills"])),
          "challenge_md": best["challenge_md"], "pool_left": len(load_pool())})


def _current_open():
    if not CURRENT.exists():
        sys.exit("no current challenge")
    cur = _read(CURRENT)
    if cur.get("status") != "open":
        sys.exit("current challenge is already submitted")
    return cur


def cmd_hint():
    cur = _current_open()
    n = cur.get("hints_revealed", 0)
    if n >= len(cur["hints"]):
        _out({"hint": None, "note": "all hints already revealed", "hints_revealed": n})
        return
    cur["hints_revealed"] = n + 1
    _write(CURRENT, cur)
    _out({"hint_number": n + 1, "of": len(cur["hints"]), "hint": cur["hints"][n]})


def cmd_reveal():
    cur = _current_open()
    _out({"answer": _unb64(cur["answer_key_b64"]), "rubric": _unb64(cur["rubric_b64"]),
          "skills": cur.get("skills", []), "hints_revealed": cur.get("hints_revealed", 0)})


def cmd_close(raw):
    cur = _current_open()
    extra = json.loads(raw)
    missed = extra.get("skills_missed", [])
    if not set(missed) <= set(cur.get("skills", [])):
        sys.exit(f"skills_missed must be a subset of this challenge's skills {cur.get('skills')}")
    entry = {
        "date": cur["date"], "domain_id": cur["domain_id"], "tag": cur["tag"], "level": cur["level"],
        "base_level": cur["base_level"], "result": extra["result"], "hints_used": cur.get("hints_revealed", 0),
        "format": cur.get("format"), "skills": cur.get("skills", []), "skills_missed": missed,
        "notes": extra.get("notes", ""), "pool_id": cur.get("pool_id"),
    }
    roll.log_entry(json.dumps(entry, ensure_ascii=False))
    cur["status"] = "submitted"
    _write(CURRENT, cur)


def main(argv):
    cmds = {
        "status": lambda: cmd_status(),
        "plan": lambda: cmd_plan(int(argv[2]) if len(argv) > 2 else 7),
        "skills": lambda: _out(SKILLS),
        "add": lambda: cmd_add(argv[2]),
        "reject": lambda: cmd_reject(argv[2]),
        "pick": lambda: cmd_pick(),
        "hint": lambda: cmd_hint(),
        "reveal": lambda: cmd_reveal(),
        "close": lambda: cmd_close(argv[2]),
    }
    if len(argv) < 2 or argv[1] not in cmds:
        sys.exit(__doc__)
    cmds[argv[1]]()


if __name__ == "__main__":
    main(sys.argv)
