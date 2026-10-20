# /solve {draft_id}

## Quy trình
Với mỗi candidate, với solver_id ∈ {1, 2}:
- Solver 1: model Sonnet, prompt "solve_from_first_principles" — bắt đầu từ tiền đề, không dùng công thức có sẵn
- Solver 2: model Haiku, prompt "solve_with_known_methods" — dùng phương pháp chuẩn ngành nếu có

Cả 2 CHỈ đọc content. KHÔNG đọc answer/rubric/hints.
Lưu solves/{draft_id}_{cid}_solver{solver_id}.json gồm: solver_answer, solver_reasoning, solver_model, solver_prompt_style.

## Ràng buộc
- 2 solver phải dùng 2 model khác nhau (Sonnet + Haiku). Đây là fix cho vấn đề "2 solver gần như 1".
- Nếu solver thấy thiếu dữ kiện, ghi "unsolvable: thiếu X" thay vì đoán.
- Reasoning bắt buộc, không chỉ đáp án cuối.

## Chạy
`python3 -m engine.solve {draft_id}` (cần `ANTHROPIC_API_KEY` và `pip install anthropic`).
