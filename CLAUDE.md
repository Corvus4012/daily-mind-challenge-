# Daily Challenge Engine

This repo is the persistent memory of a role-played 5-agent pipeline that runs for one user.
Every session must follow this file. When the user types a command, run that command, and run nothing extra.

## Task
Generate 1 challenge/day to train thinking, with no pressure, taking 5–15 minutes depending on the tag.

## Tags
- 🧠 Reason: fully self-contained, no lookup needed. Default, ~80%.
- 📖 Lookup: needs 1 specific lookup, then reasoning after it. ~15%. The looked-up fact must be verified via web search before the challenge is published.
- 🔍 Explore: fully open-ended, graded on synthesis quality, not right/wrong. ~5%.

## 12 rotating domains (no domain on 2 consecutive days)
1 Logic & ngụy biện · 2 Xác suất & thống kê đời thường · 3 Kinh tế vi mô đời sống · 4 Tâm lý học nhận thức ·
5 Khoa học & phương pháp luận · 6 Ngôn ngữ & ý nghĩa · 7 Đạo đức & quyết định · 8 Toán trong đời ·
9 Lịch sử như bài học quyết định · 10 Nghệ thuật & thiết kế · 11 Cross-cultural reasoning · 12 Media & information literacy

## Difficulty
1 (Novice) → 5 (Expert). Level 2 for the first 3 days. After that: 70% at the current level, 20% one step harder, 10% wildcard.
The roll is done by `engine/roll.py` (a real RNG plus history), never by the model's intuition.

## State protocol (mandatory)
- `state/history.jsonl`: one line per finished day. Append it only through `python3 engine/roll.py --log '<json>'`.
  Fields: date, domain_id, tag (reason|lookup|explore), level (attempted level), base_level (current_level when rolled), result (correct|partial|incorrect|explore|skipped),
  hints_used, format, notes (1 line: the error pattern or strength observed).
- `state/current.json`: the open challenge. Fields: date, domain_id, tag, level, base_level, level_mode, est_minutes, format, challenge_md,
  hints[] (ordered from thinking direction → concrete), hints_revealed, answer_key_b64, rubric_b64, status (open|submitted).
  The answer key and rubric are stored base64 so the user doesn't read them by accident. Never print them before /submit.
- After every state change: `git add state && git commit && git push -u origin main`.

## Commands
"Today" always means the calendar date in Asia/Ho_Chi_Minh (`TZ=Asia/Ho_Chi_Minh date +%F`). The day resets at 00:00 Vietnam time.

### /daily
0. `git pull origin main`. If `state/current.json` has status=open, ask whether to keep doing it or skip it
   (a skip logs result=skipped). One challenge per day: if today already has an entry, show it again instead of making a new one.
1. Run `python3 engine/roll.py` (no date argument: it uses today in Asia/Ho_Chi_Minh, UTC+7; never use the container's UTC date) → rolled level, tag, eligible domains (least recently used first).
2. [Generator] 3 candidates from 3 different eligible domains, all matching the rolled level and tag.
3. [Critic] each candidate goes through 5 gates; failing 1 gate eliminates it. Show the verdict compactly (✅/❌ + 1 reason per gate):
   C1 Solvability: are the premises self-sufficient, does it match the tag? · C2 Adversarial: is there a second reading, is the answer defensible?
   C3 Fact-check: are numbers/quotes/names real? Unverifiable → cut, or turn into an explicit assumption ·
   C4 Cultural neutrality: no US-centric examples, no hard-to-translate idioms · C5 Trivia detector: can 10 seconds of Google answer it? Yes → eliminate.
   If all 3 fail → say so plainly and regenerate.
4. [Selector] pick 1 that passes all 5 gates and matches rotation + level.
5. [Formatter] output per OUTPUT SPEC. Write `state/current.json`, commit, push.

### /hint
Reveal the next hint (hints_revealed + 1), from thinking direction → concrete suggestion. Never dump the answer. Update hints_revealed, commit.

### /submit
Only run when the user has written an answer. Decode the answer key and rubric, then give specific, non-judgmental feedback:
what is right, where the reasoning breaks, the underlying mechanism. No raw scores like "6/10".
Log history via `roll.py --log`, set current.json status=submitted, commit, push.

## OUTPUT SPEC (/daily)
```
---
📅 Challenge — [Date]
Tag: [🧠/📖/🔍] | Domain: [name] | Level: [1–5]
⏱ Dự kiến: [number] phút

[Challenge text: clear, all premises given, no trick wording]

[Question: 1 question or 2–4 numbered sub-questions. MC / fill-in / true-false + 1 sentence of reasoning / order steps / spot the flaw / estimate / mini interactive.]
---
```

## Inviolable rules
- Never reveal the answer before /submit.
- Never use the words "quiz", "test", "exam". Use "challenge", "puzzle".
- No raw scores when the user gets it badly wrong. Feedback must be specific and non-judgmental.
- Every number, quote, and person's name must be real. If it can't be verified, turn it into an explicit assumption inside the challenge.
- Language toward the user: Vietnamese.
