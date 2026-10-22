# /daily

Phục vụ đề hôm nay từ `pool/` (đề đã được giải mù và phản biện từ trước), nên đề có ngay.

1. `git pull origin main`
2. `python3 engine/dmc.py pick`, xử lý theo `status`:
   - `already`: hôm nay đã có đề. Đang mở thì in lại đề; đã nộp thì nói hôm nay đã xong, hẹn mai.
   - `open_previous` (exit 3): đề ngày trước chưa nộp. Hỏi người dùng làm tiếp hay bỏ.
     Bỏ → `python3 engine/dmc.py close '{"result": "skipped"}'` rồi chạy lại `pick`.
   - `empty` (exit 2): pool không có đề hợp domain và level hôm nay. Chạy `commands/restock.md` với đúng 1 slot
     (domain = phần tử đầu của `roll.eligible_domain_ids`, level = `roll.rolled_level`, tag = `roll.rolled_tag`), rồi `pick` lại.
     Báo trước một dòng rằng sẽ mất vài phút. Roll cố định theo ngày nên `pick` lần sau ra cùng level và tag.
     Đề bị loại thì thử domain kế tiếp trong danh sách; trượt 2 lần thì báo thật với người dùng và đề nghị `/restock`.
   - `picked`: đề đã được chuyển sang `state/current.json`. In theo OUTPUT SPEC.
3. `git add state pool && git commit -m "Serve challenge {date}" && git push -u origin main`
4. Nếu `pool_left` < 4: thêm một dòng cuối "Pool còn {n} đề, gõ /restock để bổ sung".

## Làm thêm
Người dùng muốn thêm một đề sau khi đã nộp đề hôm nay ("làm thêm", "/daily extra"):
`python3 engine/dmc.py pick --extra`. Đề thêm được ghi vào lịch sử như một ngày bình thường (có `"extra": true`),
nên vẫn tính vào level nền, kỹ năng và vòng xoay domain. Pool rỗng thì làm như trường hợp `empty` ở trên.

## Giữ đầu ra sạch
Tin nhắn phục vụ đề chỉ gồm đề theo OUTPUT SPEC, cộng tối đa 1 dòng trạng thái pool. Kể cả khi phải restock tại chỗ:
không kể quá trình, không nêu dữ kiện đã tra, nguồn, kết quả giải mù/phản biện, hay sự cố kỹ thuật.
Phát hiện về hệ thống thì ghi vào mục "Ghi chú hệ thống" trong `state/lessons.md` và chỉ trao đổi khi người dùng gõ `/discuss`.

## OUTPUT SPEC
```
---
📅 Challenge — {dd/mm/yyyy}
Tag: {🧠 Reason | 📖 Lookup | 🔍 Explore} | Domain: {tên} | Level: {level}
⏱ Dự kiến: {est_minutes} phút

{challenge_md}
---
`/hint` để mở gợi ý (3 bậc) · Viết câu trả lời rồi gõ `/submit`.
```
Không in bảng Critic, không in kỹ năng mục tiêu (lộ hướng giải). Có thể thêm một dòng nhỏ:
"Đề đã qua giải mù và phản biện độc lập."
