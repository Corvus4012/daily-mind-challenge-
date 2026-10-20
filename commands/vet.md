# /vet {draft_id}

Phản biện độc lập. Conversation MỚI, không chia sẻ context với /gen.
(Đổi tên từ /review vì trùng với một skill có sẵn của Claude Code.)

## Điều kiện
- solves/{draft_id}_*_solver1.json VÀ _solver2.json phải có sẵn. Thiếu → dừng, báo "Chạy /solve trước".

## Quy trình cho MỖI candidate
1. Cổng solvability: đọc 2 solver output, Sonnet so với answer (prompts/compare.md). Áp dụng cho mọi level:
   - Cả 2 solver báo "unsolvable" → dead_letter reason="unsolvable".
   - ≥1 solver khớp answer → pass. Nếu chỉ 1 khớp (solver_split), chuyển tín hiệu này cho Red Team soi ambiguity.
   - Cả 2 sai NHƯNG khớp nhau → flag="answer_key_suspect", đưa vào human_review/.
   - Cả 2 sai VÀ lệch nhau → dead_letter reason="solvability_fail".
   - tag_type=explore: không so đáp án (không có đáp án duy nhất); chỉ loại khi cả 2 báo unsolvable.

2. Debate loop tối đa 2 vòng:
   - Red Team (Opus) tấn công 5 loại; có web search khi đề có claims_to_verify hoặc tag_type=lookup
   - Defender (Sonnet) phản biện
   - Judge (Opus) quyết PASS/REVISE/FAIL, chấm lại final_level
   - PASS → lưu pool/{uuid}.json, với level = final_level của Judge
   - REVISE → Reviser sửa theo revision_notes → **CHẠY LẠI 2 SOLVER** (bắt buộc, kể cả khi answer không đổi) → qua lại cổng ở bước 1 → pass mới sang vòng 2
   - FAIL → dead_letter
3. Hết 2 vòng vẫn REVISE → dead_letter reason="max_revision_exceeded"
4. Log timeline vào logs/{draft_id}_{cid}.json

## Model assignment
- So đáp án: Sonnet — prompts/compare.md (không dùng Haiku vì Haiku là solver 2, không tự chấm bài mình)
- Red Team: Opus — prompts/red_team.md
- Defender: Sonnet — prompts/defender.md
- Judge: Opus — prompts/judge.md
- Reviser: Opus — prompts/reviser.md, sửa tối thiểu theo revision_notes
- Solver: xem commands/solve.md

## Output
1 dòng per candidate: "{cid}: PASS/REVISE/FAIL — lý do 1 câu"
(REVISE = hết 2 vòng vẫn cần sửa; human_review và mọi lý do loại khác ghi FAIL kèm lý do.)

## Chạy
`python3 -m engine.review {draft_id}` (cần `ANTHROPIC_API_KEY` và `pip install anthropic`).
