# /weekly

Lần chạy duy nhất của Claude mỗi tuần. Việc hằng ngày (nhận đề, gợi ý, nộp bài, hỏi đề, góp ý) diễn ra trên web app
(`docs/`, GitHub Pages); Gemini chấm bài. Lần chạy này kiểm tra lại mọi thứ và nạp đề cho tuần sau.

1. `git pull origin main`, `python3 engine/dmc.py status`.
2. **Reflect** theo `commands/restock.md` (bước Reflect) trên mọi bài trong `state/archive/` kể từ dòng đầu của `state/brief.md`.
   Bài có `grader` bắt đầu bằng `gemini:` là bài Gemini chấm: reflect chấm lại độc lập và xét mọi `appeal`.
   Chỗ reflect chấm khác: không tự sửa lịch sử; ghi vào `state/inbox.md` một mục "Chấm lại" để người dùng quyết qua web.
   Ghi `state/brief.md`.
3. **Hồ sơ người học:** cập nhật mục "Hồ sơ người học" trong `state/lessons.md` từ các mẫu reflect tìm ra.
4. **Notion:** với mỗi bài mới trong archive, thêm một dòng vào "Daily Mind Challenge — Sổ bài học"
   (data source `collection://b8f7bd64-4903-4170-aecf-cae2991330dc`) theo bước 8 của `commands/submit.md`.
5. **Hộp thư:** đọc `state/inbox.md`. Với mỗi mục chưa có trả lời, xử lý như `commands/discuss.md` và viết trả lời ngay dưới
   mục đó, mở đầu bằng `**Trả lời (Claude, {ngày}):**`. Thay đổi spec nếu đồng ý; quyết định nào cần người dùng thì hỏi trong trả lời.
6. **Restock:** đưa pool lên ít nhất 10 đề, theo `commands/restock.md`. Cơ cấu level quanh level nền B:
   khoảng 20% B − 1, 50% B, 20% B + 1, 10% B + 2 (trong 1–5); bỏ qua slot đã đủ đề cùng level trong pool.
   Web app không sinh đề tại chỗ: hết đề đúng level thì nó lấy đề gần level nhất, nên pool phải đủ trải level.
7. `git add -A state pool logs commands CLAUDE.md && git commit -m "Weekly run {date}" && git push -u origin main`.
8. Báo cáo ngắn: số đề nhận/sửa/loại (1 dòng mỗi đề, không lộ nội dung), kết quả chấm lại, mục hộp thư đã trả lời,
   rồi output của `python3 engine/metrics.py`.
