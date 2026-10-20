# /solve {draft_id}

## Quy trình
Với mỗi candidate, với solver_id ∈ {1, 2}:
- Solver 1: model Sonnet, prompt "solve_from_first_principles" (prompts/solver_first_principles.md): bắt đầu từ tiền đề, không dùng công thức có sẵn
- Solver 2: model Haiku, prompt "solve_with_known_methods" (prompts/solver_known_methods.md): dùng phương pháp chuẩn ngành nếu có
- tag_type=lookup: cả 2 solver chạy Sonnet có web search (đề cần đúng 1 lần tra cứu; web search không chạy trên Haiku). Giữ nguyên 2 prompt khác nhau.

Cả 2 CHỈ đọc content. KHÔNG đọc answer/rubric/hints.
Lưu solves/{draft_id}_{cid}_solver{solver_id}.json gồm: solver_answer, solver_reasoning, unsolvable, solver_model, solver_prompt_style.
Khi /vet giải lại đề đã sửa, file có hậu tố _rev{n}: solves/{draft_id}_{cid}_rev{n}_solver{solver_id}.json.

## Ràng buộc
- 2 solver dùng 2 model khác nhau (Sonnet + Haiku), trừ đề lookup. Đây là fix cho vấn đề "2 solver gần như 1".
- Nếu solver thấy thiếu dữ kiện, ghi "unsolvable: thiếu X" thay vì đoán.
- Reasoning bắt buộc, không chỉ đáp án cuối.

## Chạy
`python3 -m engine.solve {draft_id}` (cần `ANTHROPIC_API_KEY` và `pip install anthropic`).
