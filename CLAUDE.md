# Daily Mind Challenge

A daily thinking challenge for one user: 1 puzzle a day, 5–15 minutes, no pressure.
Puzzles are generated and independently vetted ahead of time (`/restock`), then served instantly (`/daily`).
When the user types a command, read its spec in `commands/` and run exactly that command, nothing extra.

## Commands
| Command | Spec | What it does |
|---|---|---|
| `/daily` | `commands/daily.md` | Serve today's puzzle from the pool |
| `/hint` | `commands/hint.md` | Reveal the next of 3 hints |
| `/submit` | `commands/submit.md` | Grade the user's answer, give feedback, log the result |
| `/ask` | `commands/ask.md` | Clarify how to read the open puzzle; may decline if it would leak the solution |
| `/discuss` | `commands/discuss.md` | Discuss a suggestion about the system; may decline with reasons |
| `/restock [n]` | `commands/restock.md` | Generate n puzzles, blind-solve and review each with a fresh subagent, add the good ones to the pool |

## Rules
- "Today" is the calendar date in Asia/Ho_Chi_Minh (UTC+7); the day resets at 00:00 Vietnam time.
- Never reveal an answer before `/submit`. Never say "quiz", "test" or "exam"; say "challenge" or "puzzle".
- Feedback is specific and non-judgmental; no raw scores like "6/10".
- Every number, quote and name in a puzzle is real and verified, or stated in the puzzle as an explicit assumption.
- Talk to the user in Vietnamese.
- When serving a puzzle, output only the puzzle (see `commands/daily.md`). Keep system findings for `/discuss`.
- State changes go through `engine/dmc.py` / `engine/roll.py`, then `git commit` and `git push -u origin main`.

## Files
- `state/current.json`: today's puzzle (answer and rubric base64-encoded). `state/history.jsonl`: one line per day.
- `state/archive/`: each served puzzle with the user's answer and grading. `state/brief.md`: latest reflect brief for the puzzle writer.
- `state/lessons.md`: lessons for the puzzle writer and the learner profile. Read before `/restock` and `/submit`.
- `pool/`: vetted puzzles waiting to be served. `logs/review.jsonl`: every vetting outcome.
- `engine/roll.py`: base level and the daily roll. `engine/dmc.py`: pool and challenge state. `engine/metrics.py`: health.

## Domains (no domain on 2 consecutive days)
1. Logic & ngụy biện
2. Xác suất & thống kê đời thường
3. Kinh tế vi mô đời sống
4. Tâm lý học nhận thức
5. Khoa học & phương pháp luận
6. Ngôn ngữ & ý nghĩa
7. Đạo đức & quyết định
8. Toán trong đời
9. Lịch sử như bài học quyết định
10. Nghệ thuật & thiết kế
11. Cross-cultural reasoning
12. Media & information literacy

## Tags
- 🧠 Reason (~80%): fully self-contained; no lookup needed.
- 📖 Lookup (~15%): needs 1 specific lookup, then reasoning on top of it. The fact is verified when the puzzle is written.
- 🔍 Explore (~5%): open-ended; graded on synthesis quality, not right/wrong.

## Levels
| Level | Name | What it asks |
|---|---|---|
| 1 | Novice | One reasoning step; every premise stated; at most one obvious trap. ~5 min. |
| 2 | Developing | 2–3 steps around one key idea, with one plausible trap (e.g. relative vs absolute risk). |
| 3 | Intermediate | Several steps combining two ideas; the solver must check their own result or an edge case. |
| 4 | Advanced | Build a small model from a description; interacting constraints; a counterintuitive result. |
| 5 | Expert | Solve a model with cases or an equilibrium, interpret it, and compare variants (e.g. a lemons market). ~15 min. |

The base level moves with the last 5 graded days (avg ≥ 0.8 → up, < 0.4 → down). Daily roll: 70% base,
20% base+1, 10% base+2. Skills the user missed come back 2+ days later in a different domain.
