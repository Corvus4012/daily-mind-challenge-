# /review {draft_id}

Phản biện độc lập. Conversation MỚI, không chia sẻ context với /gen.

## Điều kiện
- solves/{draft_id}_*_solver1.json VÀ _solver2.json phải có sẵn. Thiếu → dừng, báo "Chạy /solve trước".

## Quy trình cho MỖI candidate
1. Đọc 2 solver output. So với answer:
   - Level 1-3: cả 2 khớp answer → pass. Lệch hoặc sai → dead_letter reason="solvability_fail".
   - Level 4-5: ≥1 solver khớp → pass. Cả 2 sai NHƯNG khớp nhau → flag="answer_key_suspect", đưa vào human_review/. Cả 2 sai VÀ lệch nhau → dead_letter.

2. Debate loop tối đa 2 vòng:
   - Red Team (Opus) tấn công 5 loại
   - Defender (Sonnet) phản biện
   - Judge (Opus) quyết PASS/REVISE/FAIL
   - PASS → lưu pool/{uuid}.json
   - REVISE → Reviser sửa theo revision_notes → **CHẠY LẠI 2 SOLVER** (bắt buộc) → so đáp án như bước 1 → nếu pass solvability mới sang vòng 2
   - FAIL → dead_letter
3. Hết 2 vòng vẫn REVISE → dead_letter reason="max_revision_exceeded"
4. Log timeline vào logs/{draft_id}_{cid}.json

## Model assignment
- Red Team: Opus — prompt: prompts/red_team.md
- Defender: Sonnet — prompt: prompts/defender.md
- Judge: Opus — prompt: prompts/judge.md
- Reviser: Opus — sửa tối thiểu theo revision_notes
- Solver: xem commands/solve.md

## Output
1 dòng per candidate: "{cid}: PASS/REVISE/FAIL — lý do 1 câu"

## Chạy
`python3 -m engine.review {draft_id}` (cần `ANTHROPIC_API_KEY` và `pip install anthropic`).
