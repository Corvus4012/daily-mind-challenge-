# /restock [n]

Sinh và kiểm định n đề (mặc định 7, tức một tuần) rồi đưa vào `pool/`. Đây là nơi duy nhất sinh đề.
`/daily` cũng gọi quy trình này với n = 1 khi pool không có đề hợp.
Người dùng đã đồng ý cho lệnh này tạo subagent để giải mù và phản biện.

## 0. Chuẩn bị
- `git pull origin main`
- `python3 engine/dmc.py plan n`: danh sách slot (domain, level, tag, target_skill).
- Đọc `state/lessons.md` (bài học cho người ra đề), các mục Levels trong `CLAUDE.md`, và playbook ở cuối file này.
- `python3 engine/dmc.py skills`: bảng kỹ năng. Mỗi đề gắn 1–3 kỹ năng từ bảng này.
- **Reflect** (1 subagent mới, `model: sonnet`, mỗi lần restock một lần; bỏ qua khi `state/archive/` không có bài mới
  kể từ lần reflect trước, ghi trong dòng đầu `state/brief.md`): prompt = BRIEF REFLECT + nội dung các file archive mới
  (giải mã `answer_key_b64`, `rubric_b64`) + mục "Hồ sơ người học" trong `state/lessons.md`.
  Ghi kết quả vào `state/brief.md` (ghi đè). Người ra đề đọc brief này cùng lessons trước khi sinh.
  Chỗ reflect chấm khác session chính: KHÔNG tự sửa lịch sử; ghi vào "Ghi chú hệ thống" để trao đổi qua `/discuss`.

## 1. Sinh (session chính)
Viết 1 candidate cho mỗi slot, cộng thêm ceil(n/4) slot dự phòng (domain khác, level nền) để bù đề bị loại.
Mỗi candidate là một file JSON trong scratchpad (KHÔNG ghi vào repo khi chưa qua kiểm định):
```json
{
  "domain_id": 3, "level": 2, "tag": "reason", "format": "fill-in",
  "skills": ["unit_choice"], "est_minutes": 8,
  "challenge_md": "Toàn bộ đề + các câu hỏi con, đúng như người dùng sẽ thấy.",
  "hints": ["hướng suy nghĩ", "gợi ý cụ thể hơn", "gợi ý cụ thể nhất, vẫn không lộ đáp án"],
  "answer": "Đáp án từng câu hỏi con + cơ chế, viết để dùng khi chấm.",
  "rubric": "Mỗi câu: đạt / một phần / chưa đạt; bẫy chính; quy tắc gộp thành correct/partial/incorrect. Câu dạng bảng: liệt kê ô then chốt và các ô chấp nhận nhiều đáp án (chuẩn chấm bảng trong commands/submit.md).",
  "claims": [{"claim": "Akerlof nhận Nobel Kinh tế 2001", "source": "URL đã kiểm"}]
}
```
Tiêu chuẩn của đề:
- Tự đủ tiền đề. Mọi thuật ngữ được giải nghĩa trong đề. Biến có đơn vị và được nói rõ là liên tục hay rời rạc.
- Có đúng một đáp án bảo vệ được (trừ tag explore). Câu so sánh nêu tiêu chí đo được.
- Số liệu, trích dẫn, tên người: hoặc ghi rõ "giả định của đề", hoặc là sự thật đã kiểm bằng WebSearch ngay bây giờ (ghi vào `claims` kèm nguồn). Không lẫn hai loại.
- Không tra Google ra đáp án. Biết tên khái niệm thì không sao; tra ra chính đáp án thì loại.
- Bối cảnh trung lập, ưu tiên đời sống Việt Nam hoặc quốc tế; không lấy Mỹ làm trung tâm, không dùng idiom khó dịch.
- Độ dài: ≤ 200 từ (khoảng 300 tiếng) ở level 1–3, ≤ 300 từ ở level 4–5. 1 câu hỏi hoặc 2–4 câu hỏi con.
- Slot có `target_skill`: đề phải xoay quanh kỹ năng đó, trong domain của slot (luyện chuyển giao, không lặp lại đề cũ).
- Các đề trong cùng một lần restock dùng format khác nhau khi có thể.

## 2. Giải mù (subagent, chạy song song)
Mỗi candidate một subagent mới (`subagent_type: general-purpose`; `model: sonnet` cho level 1–3, `opus` cho level 4–5).
Tạo tất cả trong cùng một lượt để chúng chạy song song, rồi đợi kết quả của từng agent.
Prompt = BRIEF GIẢI MÙ + `challenge_md`. Tuyệt đối không đưa answer, rubric, hints hay claims.
Đề tag lookup: thay dòng "không tra web" trong brief bằng "được dùng WebSearch, chỉ để tra đúng dữ kiện đề yêu cầu".

## 3. Phản biện (cùng subagent)
Gửi tiếp cho chính subagent đó bằng SendMessage (`to` = agentId trả về khi tạo agent; agent đã chạy xong vẫn tiếp tục được
từ transcript; nạp tool qua ToolSearch nếu chưa có): BRIEF PHẢN BIỆN + answer + rubric + claims.
Không tiếp tục được agent cũ thì tạo agent mới, đưa `challenge_md` + lời giải mù ở bước 2 + BRIEF PHẢN BIỆN + answer + rubric + claims.

## 4. Quyết định (session chính)
- **Nhận:** lời giải mù khớp đáp án ở mọi câu hỏi con (tag explore: đề rõ, rubric dùng được), và không còn issue severity ≥ 2.
- **Sửa (tối đa 1 lần):** lời giải mù lệch đáp án, hoặc có issue severity 2–3 sửa được (thiếu tiền đề, câu mơ hồ, thuật ngữ chưa giải nghĩa, sai đáp án, level lệch).
  Sửa tối thiểu (đề, đáp án, rubric, hints đồng bộ), rồi chạy lại BƯỚC 2 với một subagent MỚI (agent cũ đã thấy đáp án). Khớp thì nhận, không thì loại.
  Nếu người phản biện chứng minh đáp án gốc sai và lời giải mù đúng: sửa đáp án, vẫn phải qua một lần giải mù mới.
- **Loại:** trivia, đề sai bản chất, hoặc bản sửa vẫn trượt.
- Phản biện chấm level khác level dự kiến: nhận theo level của phản biện, không loại.
- **Giữ đề vươn lên trong pool:** sau khi quyết định, nếu pool (cả đề vừa nhận) không còn đề nào trên level nền,
  sinh thêm 1 candidate ở level nền +1 hoặc +2 (domain khác) và cho qua đủ bước 2–4. Ngày roll ra level cao hơn
  sẽ có đề đúng level thay vì lặng lẽ nhận đề level nền.
Mỗi candidate thêm khối `review`:
`{"solver_model": "...", "first_solve_match": true|false, "revised": true|false, "issues": [{"type", "severity", "detail"}], "reason": "nếu loại"}`

## 5. Ghi và báo cáo
- Đề nhận: `python3 engine/dmc.py add FILE`. Đề loại: thêm `"reason"` rồi `python3 engine/dmc.py reject FILE`.
- Thêm vào `state/lessons.md` mọi bài học mới rút ra từ issue (ví dụ một kiểu mơ hồ lặp lại).
- `git add pool logs state && git commit -m "Restock: +k puzzles" && git push -u origin main`
  (push bị từ chối vì `/daily` vừa đẩy lên: `git pull --rebase origin main` rồi push lại.)
- Báo người dùng: 1 dòng mỗi đề (domain · level · nhận/sửa/loại · lý do ngắn), KHÔNG lộ nội dung hay đáp án đề đã nhận. Rồi in `python3 engine/metrics.py`.

## BRIEF GIẢI MÙ
```
Bạn là người giải độc lập cho một đề luyện tư duy tiếng Việt. Chỉ dùng văn bản đề dưới đây.
Không đọc file nào trong repo, không tra web. Không có đáp án hay gợi ý.
1. Giải từng câu hỏi con; viết lập luận ngắn gọn rồi đáp án cuối.
2. Ghi lại mọi chỗ bạn thấy có thể hiểu theo 2 cách, mọi thuật ngữ chưa được giải nghĩa, mọi dữ kiện bạn phải tự giả định.
3. Ước lượng thời gian một người thông minh, không chuyên ngành cần để làm.
Trả về JSON: {"answers": ["câu 1: ...", ...], "reasoning": "...", "ambiguities": [...], "undefined_terms": [...], "assumptions_made": [...], "est_minutes": n}

ĐỀ:
<challenge_md>
```

## BRIEF REFLECT
```
Bạn là người rà soát độc lập cho một hệ thống luyện tư duy. Dưới đây là các đề đã giao, đáp án, rubric,
câu trả lời nguyên văn của người học và cách session chính đã chấm. Không đọc file nào khác, không tra web.
1. Chấm lại từng bài theo rubric, chỉ dựa trên câu trả lời. Ghi bài nào bạn chấm khác và vì sao.
   Bài có trường "appeal" (người học phản đối cách chấm): xét lời phản đối độc lập, nói rõ đồng ý hay không và vì sao.
2. Tìm mẫu lặp lại: kỹ năng, dạng câu hỏi (tính toán / giải thích cơ chế / thiết kế phép thử...), mức gợi ý đã dùng.
   Mỗi mẫu phải dẫn ít nhất 2 bài làm bằng chứng.
3. Viết tối đa 6 kiến nghị cụ thể cho người ra đề (dạng đề nào, luyện bước nào, độ khó nên chỉnh ra sao).
Trả về markdown: "## Chấm lại", "## Mẫu", "## Kiến nghị". Dòng đầu: "Reflect đến ngày YYYY-MM-DD".
```

## BRIEF PHẢN BIỆN
```
Đây là đáp án, rubric và các claim của người ra đề. Đối chiếu với lời giải của bạn, rồi đóng vai phản biện:
chỉ tìm lỗi, không khen.
1. Với từng câu hỏi con: lời giải của bạn có khớp đáp án không? Nếu lệch, bên nào sai, và có phải do đề hiểu được theo 2 cách?
2. Liệt kê issue, mỗi issue có type, severity (1 = cosmetic, 2 = phải sửa, 3 = chí mạng), detail và fix tối thiểu.
   type thuộc: answer_error, ambiguity, missing_premise, undefined_term, trivia, fact_error, bias, level_mismatch, too_long.
   trivia: ghi search query cụ thể sẽ ra đáp án. fact_error: claim nào sai hoặc không verify được.
3. Chấm level theo thang: 1 = 1 bước, mọi tiền đề nói rõ; 2 = 2–3 bước quanh 1 ý, có 1 bẫy hợp lý;
   3 = nhiều bước kết hợp 2 ý, phải tự kiểm kết quả; 4 = tự dựng mô hình nhỏ, nhiều ràng buộc, kết quả phản trực giác;
   5 = giải mô hình có nhiều trường hợp hoặc cân bằng, diễn giải và so sánh biến thể.
Trả về JSON: {"matches": [true, ...], "issues": [...], "level_estimate": n, "verdict": "accept|revise|reject", "one_line": "..."}

ĐÁP ÁN: <answer>
RUBRIC: <rubric>
CLAIMS: <claims>
```

## Playbook theo domain
Dạng đề cho ra đáp án kiểm chứng được, và bẫy cần tránh.
1. **Logic & ngụy biện:** chuỗi lập luận đánh số → tìm bước gãy đầu tiên và lý do; "kết luận nào suy ra được / không suy ra được". Tránh: bắt gọi tên ngụy biện (tra được).
2. **Xác suất & thống kê đời thường:** tỉ lệ nền, xác suất có điều kiện, chọn mẫu, hồi quy về trung bình, với số giả định tính tay được. Tránh: dùng nguyên bản các nghịch lý nổi tiếng (Monty Hall, ngày sinh).
3. **Kinh tế vi mô đời sống:** chi phí cơ hội, tư duy biên, chi phí chìm, động cơ, lựa chọn ngược, qua mô hình nhỏ có số. Mỗi biến kèm nghĩa đời thường.
4. **Tâm lý học nhận thức:** mô tả cơ chế (định nghĩa sẵn) + tình huống → dự đoán hành vi hoặc thiết kế can thiệp, chọn cách đo hiệu quả. Tránh: hỏi tên hiệu ứng.
5. **Khoa học & phương pháp luận:** phép thử nào phân biệt được 2 giả thuyết; nhóm đối chứng; biến gây nhiễu; kiểm định nhiều lần.
6. **Ngôn ngữ & ý nghĩa:** câu tiếng Việt nhiều nghĩa (cú pháp, phạm vi, hàm ý) → liệt kê các cách hiểu + viết lại câu không còn mơ hồ; định nghĩa vòng.
7. **Đạo đức & quyết định:** với tag reason, KHÔNG hỏi "nên làm gì". Dùng: nguyên tắc tự tuyên bố → quyết định nào mâu thuẫn; giá trị và xác suất cho sẵn → tính kỳ vọng; hai lập luận → cái nào nhất quán. Câu hỏi giá trị thật sự thì dùng tag explore.
8. **Toán trong đời:** ước lượng Fermi (đáp án là một khoảng chấp nhận), đơn vị, trung bình có trọng số, lãi kép, tỉ lệ.
9. **Lịch sử như bài học quyết định:** tình huống thật (claims kèm nguồn) hoặc hư cấu nói rõ. Hỏi: lúc đó người ra quyết định biết gì, có những phương án nào, đánh đổi gì. Tránh: hỏi kết cục (tra được).
10. **Nghệ thuật & thiết kế:** tiêu chí đo được: thứ tự mắt đọc, phân cấp thị giác, độ tương phản, nguyên lý Gestalt (định nghĩa sẵn), lưới, số thao tác; mô tả bằng chữ hoặc sơ đồ ASCII. Tránh: chấm theo gu.
11. **Cross-cultural reasoning:** quy ước cho sẵn làm tiền đề (định dạng số và ngày, cách xưng hô, lịch, đơn vị) → suy ra chỗ hiểu nhầm và cách kiểm tra qua một kênh độc lập. Tránh: khái quát hoá cả một dân tộc.
12. **Media & information literacy:** tiêu đề vs dữ liệu, tuyệt đối vs tương đối, biểu đồ cắt trục, nguồn tin, mẫu chọn lọc; dữ liệu giả định.
