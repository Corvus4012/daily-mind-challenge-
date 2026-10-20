# /gen {domain} {n}

Sinh {n} candidate đề trong domain {domain}. Chạy trong conversation riêng. KHÔNG chạy /vet trong cùng lượt.

## Input
- domain: 1 trong 12 domain
- n: mặc định 3, tối đa 5
- target_level: `base_level` trong state/current.json (level nền; không lấy `level`, vì đó có thể là level wildcard của đề hôm trước), mặc định 2

## Quy trình
1. Đọc CLAUDE.md lấy định nghĩa domain, tag-type, level descriptor.
2. Sinh {n} candidate độc lập, ưu tiên mỗi candidate một format khác nhau (MC, fill-in, T/F kèm lý do, order, spot-flaw, estimate).
3. Mỗi candidate tự kiểm 5 cổng C1-C5, ghi vào reasoning_chain.
4. Lưu drafts/{date}_{domain}.json đúng schema.
5. Output 1 dòng: "Đã sinh {n} candidate cho {domain} → drafts/{date}_{domain}.json"

## Ràng buộc
- Không cần kiến thức chuyên ngành ngoài phổ thông (trừ tag_type=lookup).
- Số liệu/quote/tên: hư cấu rõ ràng HOẶC nguồn thật ghi trong claims_to_verify. Không lẫn lộn.
- Đề ≤ 200 từ ở level 1–3, ≤ 300 từ ở level 4–5 (đề mô hình cần chỗ cho định nghĩa). Thuật ngữ chuyên ngành phải được giải nghĩa ngay trong đề.
- Nếu domain+level không khả thi, hạ level gần nhất, ghi lý do vào reasoning_chain.

## Schema
`{date}` là ngày theo giờ Việt Nam (YYYY-MM-DD); `{domain}` là số domain 1–12. `draft_id` = `{date}_{domain}`.
`engine/solve.py` và `engine/review.py` đọc đúng các trường dưới đây.

```json
{
  "draft_id": "2026-10-21_3",
  "date": "2026-10-21",
  "domain_id": 3,
  "target_level": 2,
  "candidates": [
    {
      "cid": "c1",
      "domain_id": 3,
      "level": 2,
      "tag_type": "reason | lookup | explore",
      "format": "mc | fill-in | tf-reason | order | spot-flaw | estimate",
      "content": "Đề bài, ≤ 200 từ. Đây là phần duy nhất solver được đọc.",
      "answer": "Đáp án cho từng câu hỏi con.",
      "rubric": "Tiêu chí chấm: đạt / một phần / chưa đạt.",
      "hints": ["hướng suy nghĩ", "gợi ý cụ thể hơn", "gợi ý cụ thể nhất"],
      "claims_to_verify": [{"claim": "...", "source": "..."}],
      "reasoning_chain": "Kết quả tự kiểm C1–C5, lý do hạ level nếu có."
    }
  ]
}
```
`level` của từng candidate có thể thấp hơn `target_level` khi phải hạ level. `claims_to_verify` để `[]` nếu mọi dữ kiện đều hư cấu.
