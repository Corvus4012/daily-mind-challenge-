# /submit

Chỉ chạy khi người dùng đã viết câu trả lời. Chưa có câu trả lời thì nhắc họ viết trước.

1. `python3 engine/dmc.py reveal`: đáp án, rubric, kỹ năng của đề. Chỉ đọc ở bước này, không bao giờ trước đó.
2. Chấm theo rubric, ra một trong ba kết quả: correct / partial / incorrect (tag explore: ghi `explore`).
   **Câu trả lời dạng bảng / nhiều mục** (ma trận, xếp loại, sắp thứ tự, liệt kê): chấm từng ô theo chuẩn sau, không ước lượng chung chung.
   - Rubric chia ô thành *ô then chốt* (quyết định kết luận) và *ô thường*; ô có nhiều đáp án bảo vệ được ghi rõ các đáp án chấp nhận.
   - Ô lệch key nhưng có lập luận đúng dựa trên tiền đề của đề → tính đúng. Ô lệch key mà không có lý do → tính sai.
   - Đạt: đúng mọi ô then chốt và ≥ 80% ô thường. Một phần: sai tối đa 1 ô then chốt, hoặc đúng mọi ô then chốt nhưng < 80% ô thường. Còn lại: chưa đạt.
   - Feedback in tóm tắt: "then chốt x/y, thường a/b", rồi chỉ ra từng ô sai và vì sao.
   Rubric cũ chưa đánh dấu ô then chốt: tự xác định ô then chốt từ đáp án (ô mà đổi nhãn thì đổi kết luận) và nói rõ đã chọn những ô nào.
   Rubric đòi một lý do cụ thể nhưng người dùng đưa lý do khác cũng đúng về logic → tính đạt.
3. Viết feedback (tiếng Việt):
   - Dòng đầu: kết quả bằng lời ("đúng cả 3 câu", "đúng một phần") + số hint đã dùng. Không cho điểm số kiểu 6/10.
   - Từng câu: đúng ở đâu → gãy ở đâu → cơ chế phía sau. Cụ thể, không phán xét. Ghi nhận cách làm hay hơn đáp án mẫu nếu có.
   - Người dùng chỉ ra đề mơ hồ hoặc sai: xét thật lòng. Họ đúng thì nhận lỗi, chấm nhẹ tay câu đó, và thêm bài học vào `state/lessons.md`.
   - Một dòng "Rút ra": nguyên tắc chuyển giao được. Nếu nó nối với một lỗi cũ trong hồ sơ người học, nói ra mối nối đó.
4. Xác định `skills_missed`: kỹ năng nào trong `skills` của đề mà người dùng chưa thể hiện được.
5. `python3 engine/dmc.py close '{"result": "...", "skills_missed": [...], "notes": "1 dòng: điểm mạnh và mẫu lỗi", "answer": "nguyên văn câu trả lời", "grading": "đạt/một phần/chưa đạt từng câu + lý do ngắn"}'`
   `close` lưu đề + câu trả lời + cách chấm vào `state/archive/` để bước Reflect của `/restock` chấm lại độc lập.
6. Mẫu học tập lặp lại (lỗi xuất hiện lần 2, hoặc thế mạnh mới): cập nhật mục "Hồ sơ người học" trong `state/lessons.md`.
7. `git add state && git commit -m "Submit challenge {date}: {result}" && git push -u origin main`
8. Một dòng cuối: level nền hiện tại (`python3 engine/dmc.py status`) và kỹ năng sẽ được ôn lại, nếu có.
