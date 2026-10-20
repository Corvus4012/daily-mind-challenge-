# Daily Challenge Engine

## Overview
This repo runs a daily thinking challenge for one user: 1 challenge/day, 5–15 minutes, no pressure.
When the user types a command, read its spec in `commands/` and run exactly that command, nothing extra.
- "Today" is the calendar date in Asia/Ho_Chi_Minh (UTC+7); the day resets at 00:00 Vietnam time.
- Never reveal an answer before `/submit`. Never say "quiz", "test" or "exam"; say "challenge" or "puzzle".
- Feedback is specific and non-judgmental; no raw scores like "6/10".
- Every number, quote and name in a challenge is real, or stated in the challenge as an explicit assumption.
- Talk to the user in Vietnamese.

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
- 📖 Lookup (~15%): needs 1 specific lookup, then reasoning on top of it. The fact is verified before publishing.
- 🔍 Explore (~5%): open-ended; graded on synthesis quality, not right/wrong.

## Levels
| Level | Name | What it asks |
|---|---|---|
| 1 | Novice | One reasoning step; every premise stated; at most one obvious trap. ~5 min. |
| 2 | Developing | 2–3 steps around one key idea, with one plausible trap (e.g. relative vs absolute risk). |
| 3 | Intermediate | Several steps combining two ideas; the solver must check their own result or an edge case. |
| 4 | Advanced | Build a small model from a description; interacting constraints; a counterintuitive result. |
| 5 | Expert | Solve a model with cases or an equilibrium, interpret it, and compare variants (e.g. a lemons market). ~15 min. |

## Commands
Specs live in `commands/`. Review pipeline: `gen.md` → `solve.md` → `review.md`.
Serving the user: `daily.md`, `hint.md`, `submit.md`.
