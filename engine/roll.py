#!/usr/bin/env python3
"""Daily Challenge Engine: read history, compute current level, roll today's tag/level, list eligible domains.

Usage:
  python3 engine/roll.py [YYYY-MM-DD]     # default: today in Asia/Ho_Chi_Minh
  python3 engine/roll.py --log '<json>'   # append one history entry (validated)
"""
import json
import random
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

TZ = ZoneInfo("Asia/Ho_Chi_Minh")  # the user's day resets at 00:00 Vietnam time, not UTC
ROOT = Path(__file__).resolve().parent.parent
HISTORY = ROOT / "state" / "history.jsonl"

DOMAINS = {
    1: "Logic & ngụy biện",
    2: "Xác suất & thống kê đời thường",
    3: "Kinh tế vi mô đời sống",
    4: "Tâm lý học nhận thức",
    5: "Khoa học & phương pháp luận",
    6: "Ngôn ngữ & ý nghĩa",
    7: "Đạo đức & quyết định",
    8: "Toán trong đời",
    9: "Lịch sử như bài học quyết định",
    10: "Nghệ thuật & thiết kế",
    11: "Cross-cultural reasoning",
    12: "Media & information literacy",
}
TAGS = [("reason", 0.80), ("lookup", 0.15), ("explore", 0.05)]
RESULTS = {"correct", "partial", "incorrect", "explore", "skipped"}
WARMUP_DAYS = 3
WINDOW = 5


def load():
    if not HISTORY.exists():
        return []
    return [json.loads(l) for l in HISTORY.read_text(encoding="utf-8").splitlines() if l.strip()]


def current_level(hist):
    """Start at 2. Each graded day (not explore/skipped) shifts the level using the last WINDOW graded days."""
    graded = [h for h in hist if h["result"] in {"correct", "partial", "incorrect"}]
    if len(hist) < WARMUP_DAYS:
        return 2
    level = 2
    recent = graded[-WINDOW:]
    if len(recent) < 3:
        return level
    # score: correct without hint = 1, correct with hints = 0.75, partial = 0.5, incorrect = 0
    def score(h):
        if h["result"] == "correct":
            return 1.0 if h.get("hints_used", 0) == 0 else 0.75
        return 0.5 if h["result"] == "partial" else 0.0
    # anchor on the base level at roll time (not the attempted level: stretch/wildcard days must not move the anchor)
    level = recent[-1]["base_level"]
    avg = sum(score(h) for h in recent) / len(recent)
    if avg >= 0.8:
        level += 1
    elif avg < 0.4:
        level -= 1
    return max(1, min(5, level))


def roll(today, hist, rng):
    base = current_level(hist)
    if len(hist) < WARMUP_DAYS:
        lvl, mode = 2, "warmup"
    else:
        r = rng.random()
        if r < 0.70:
            lvl, mode = base, "core"
        elif r < 0.90:
            lvl, mode = min(5, base + 1), "stretch"
        else:
            lvl, mode = min(5, base + 2), "wildcard"  # a 3-level jump (e.g. 2 -> 5) is too steep to learn from
    r = rng.random()
    acc = 0.0
    tag = TAGS[0][0]
    for name, p in TAGS:
        acc += p
        if r < acc:
            tag = name
            break
    blocked = {h["domain_id"] for h in hist[-2:]}
    last_used = {}
    for i, h in enumerate(hist):
        last_used[h["domain_id"]] = i
    eligible = sorted(
        (d for d in DOMAINS if d not in blocked),
        key=lambda d: (last_used.get(d, -1), rng.random()),
    )
    return {
        "date": today,
        "day_number": len(hist) + 1,
        "current_level": base,
        "rolled_level": lvl,
        "level_mode": mode,
        "rolled_tag": tag,
        "blocked_domains": sorted(blocked),
        "eligible_domains_least_recent_first": [f"{d}. {DOMAINS[d]}" for d in eligible],
        "eligible_domain_ids": eligible,
    }


def log_entry(raw):
    e = json.loads(raw)
    required = {"date", "domain_id", "tag", "level", "base_level", "result", "hints_used"}
    missing = required - e.keys()
    if missing:
        sys.exit(f"missing fields: {sorted(missing)}")
    if e["domain_id"] not in DOMAINS or e["result"] not in RESULTS or not 1 <= e["level"] <= 5 or not 1 <= e["base_level"] <= 5:
        sys.exit("invalid domain_id / result / level")
    e["domain"] = DOMAINS[e["domain_id"]]
    with HISTORY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print("logged:", json.dumps(e, ensure_ascii=False))


if __name__ == "__main__":
    if len(sys.argv) > 2 and sys.argv[1] == "--log":
        log_entry(sys.argv[2])
    else:
        today = sys.argv[1] if len(sys.argv) > 1 else datetime.now(TZ).date().isoformat()
        hist = load()
        print(json.dumps(roll(today, hist, random.Random()), ensure_ascii=False, indent=2))
