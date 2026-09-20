# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** ColdBrew
**Thành viên:** Đào Trọng Khang; các thành viên còn lại bổ sung trước khi nộp
**Ngày:** 20/09/2026

> **Nộp 1 bản / nhóm.** Phần cá nhân (hướng tiếp cận, kết quả riêng, dự đoán…) mỗi thành viên nộp riêng trong `REPORT_CANHAN.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần nhóm: 40** = Lựa chọn tài liệu (10) + Thiết kế chiến lược (15) + Chất lượng truy xuất (10) + Thuyết trình (5).

---

## 1. Lựa chọn tài liệu (Document Set Quality) — Nhóm (10 điểm)

### Chủ đề (Domain) & Lý Do Chọn

**Chủ đề:** Chính sách và quy định vận hành Sàn TMĐT Shopee Việt Nam

**Tại sao nhóm chọn chủ đề này?**
> Chủ đề có nhiều câu hỏi thực tế về trả hàng, vận chuyển, tranh chấp và đăng bán, đồng thời chứa các con số và điều kiện có thể kiểm chứng rõ ràng. Các tài liệu cùng miền nhưng khác đối tượng buyer/seller cũng phù hợp để thử metadata filtering và so sánh chiến lược chunking.

### Danh sách tài liệu (Data Inventory)

| # | Tên tài liệu | Nguồn (Source URL) | Ngày lấy / Phiên bản | Số ký tự | Metadata đã gán |
|---|--------------|------------|--------------------|----------|-----------------|
| 1 | Điều khoản Dịch vụ | https://help.shopee.vn/portal/4/article/77243 | 20/09/2026 / not-stated | 84.306 | `doc_id`, `source_url`, `retrieved_at`, `document_version`, `audience` |
| 2 | Quy chế hoạt động Sàn TMĐT Shopee.vn | https://help.shopee.vn/portal/4/article/77245 | 20/09/2026 / not-stated | 79.155 | Như trên; `audience=both` |
| 3 | Quy định đăng bán sản phẩm | https://help.shopee.vn/portal/4/article/77246 | 20/09/2026 / not-stated | 22.234 | Như trên; `audience=seller` |
| 4 | Chính sách Vận chuyển Shopee | https://help.shopee.vn/portal/4/article/77250 | 20/09/2026 / not-stated | 25.270 | Như trên; `audience=seller` |
| 5 | Chính sách Trả hàng và Hoàn tiền | https://help.shopee.vn/portal/4/article/77251 | 20/09/2026 / not-stated | 20.096 | Như trên; `audience=buyer` |
| 6 | Điều khoản Dịch vụ Shopee Mall | https://help.shopee.vn/portal/4/article/77262 | 20/09/2026 / not-stated | 34.449 | Như trên; `audience=both` |
| 7 | Quy trình giải quyết tranh chấp/khiếu nại | https://help.shopee.vn/portal/4/article/77265 | 20/09/2026 / not-stated | 5.178 | Như trên; `audience=both` |

**Danh sách kiểm tra quản trị dữ liệu (Data governance checklist):**
- [x] Tập tài liệu (Corpus) chỉ chứa nguồn công khai/được phép dùng và không chứa dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Mỗi tài liệu có `source_url`, `retrieved_at`, `document_version` (hoặc `not-stated`) trong metadata.

### Cấu trúc Metadata (Metadata Schema)

| Trường metadata | Kiểu | Ví dụ giá trị | Tại sao hữu ích cho truy xuất (retrieval)? |
|----------------|------|---------------|-------------------------------|
| `doc_id` | string | `77250` | Liên kết chunk với tài liệu gốc và đối chiếu gold span. |
| `source_url` | string | `https://help.shopee.vn/portal/4/article/77250` | Truy vết câu trả lời về nguồn chính thức. |
| `retrieved_at` | date string | `2026-09-20` | Biết thời điểm thu thập chính sách có thể thay đổi. |
| `document_version` | string | `not-stated` | Theo dõi phiên bản hoặc minh bạch khi nguồn không nêu phiên bản. |
| `audience` | enum string | `buyer`, `seller`, `both` | Lọc trước theo đối tượng để tránh nhầm quy định Người Mua/Người Bán. |

---

## 2. Thiết kế chiến lược (Strategy Design) — Nhóm (15 điểm)

> Mỗi thành viên thử **một chiến lược khác nhau** trên cùng bộ tài liệu; nhóm tổng hợp và so sánh ở đây.

### Phân tích đường cơ sở (Baseline Analysis)

Chạy `ChunkingStrategyComparator().compare()` trên 2-3 tài liệu:

| Tài liệu | Chiến lược (Strategy) | Số lượng Chunk | Độ dài trung bình | Giữ được ngữ cảnh không? |
|-----------|----------|-------------|------------|-------------------|
| Toàn bộ corpus (7 file) | FixedSizeChunker (`chunk_size=1800`, `overlap=200`) | 168 | 1773.5 | Giữ độ dài ổn định nhưng có thể cắt giữa câu/điều khoản. |
| Toàn bộ corpus (7 file) | SentenceChunker (`8 câu/chunk`) | 219 | 1207.1 | Giữ trọn câu tốt hơn nhưng độ dài chunk dao động. |
| Toàn bộ corpus (7 file) | RecursiveChunker (`chunk_size=1800`) | 171 | 1552.0 | Ưu tiên ranh giới đoạn/câu nên mạch lạc hơn, nhưng không có overlap. |

### Chiến lược của từng thành viên

> Mỗi thành viên điền một khối dưới đây (copy thêm nếu nhóm có nhiều hơn 3 người).

**Thành viên 1 — Đào Trọng Khang**
- **Loại chiến lược:** Recursive
- **Mô tả & lý do chọn cho chủ đề này:** Văn bản chính sách có cấu trúc đoạn, dòng và câu rõ ràng nên chiến lược recursive ưu tiên các ranh giới lớn trước khi phải cắt theo ký tự. Cách này giảm số chunk bị cắt giữa điều khoản so với fixed-size, dù vẫn có rủi ro mất thông tin tại ranh giới vì chưa có overlap.
- **Code snippet (nếu custom):**
```python
RecursiveChunker(chunk_size=1800)
```

**Thành viên 2 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

**Thành viên 3 — [Tên]**
- **Loại chiến lược:**
- **Mô tả & lý do chọn:**
- **Code snippet (nếu custom):**

### So Sánh Giữa Các Thành Viên

| Thành viên | Chiến lược (Strategy) | Điểm truy xuất (/10) | Điểm mạnh | Điểm yếu |
|-----------|----------|----------------------|-----------|----------|
| Cấu hình so sánh A | FixedSize | 2/10 | Độ dài chunk ổn định; Q4 đạt Top-1 | Cắt giữa câu và bỏ lỡ anchor ở Q1, Q2, Q3, Q5 |
| Cấu hình so sánh B | Sentence | 1/10 | Bảo toàn câu, tạo chunk ngắn hơn | Chỉ Q4 có gold hit ở Top-2 |
| Đào Trọng Khang | Recursive | 2/10 | Giữ đoạn/câu tự nhiên; Q2 và Q4 có gold hit | Không có overlap; các danh sách dài vẫn dễ rơi sai section |

**Chiến lược nào tốt nhất cho chủ đề này? Tại sao?**
> FixedSize và Recursive cùng đạt 2/10, nhưng Recursive phù hợp hơn về chất lượng chunk vì ưu tiên ranh giới đoạn và câu thay vì cắt cứng giữa nội dung. Tuy nhiên, FixedSize đưa Q4 lên Top-1 còn Recursive tìm được thêm Q2 ở Top-3, cho thấy không có chiến lược nào thắng tuyệt đối và cần cải thiện bằng heading/overlap hoặc reranking.

---

## 3. Câu hỏi đánh giá & Chất lượng truy xuất (Retrieval Quality) — Nhóm (10 điểm)

### Câu hỏi đánh giá & Câu trả lời chuẩn (nhóm thống nhất)

> **Đúng 5 câu hỏi**, đa dạng, có thể kiểm chứng; **ít nhất 1 câu** cần lọc metadata mới trả lời tốt. Đây là bộ câu hỏi chung cho mọi thành viên chạy.

| # | Câu hỏi (Query) | Câu trả lời chuẩn (Gold Answer) | Chunk nào chứa thông tin? |
|---|-------|-------------------------------|--------------------------|
| 1 | Mua hàng trên Shopee Mall, sau khi yêu cầu trả hàng được chấp thuận thì phải gửi trả sản phẩm trong bao nhiêu ngày? | 06 ngày lịch; dùng bao bì ban đầu và Phiếu Trả Hàng của Shopee. | `77262_2628_3865` |
| 2 | Hàng bị hư hại trong quá trình vận chuyển thì phải khiếu nại trong vòng bao nhiêu ngày? | Người Bán khiếu nại hàng hoàn hư hại trong 03 ngày; thất lạc trong 07 ngày từ khi chuyển hoàn thành công. | `77250_14001_14778` |
| 3 | Người mua được yêu cầu trả hàng/hoàn tiền trong những trường hợp nào? | Không/thiếu hàng, hàng giả, lỗi/hư hại, giao sai, khác mô tả, hết hạn, có thỏa thuận hoặc Trả hàng COM đủ điều kiện. | `77251_2180_3085` |
| 4 | Quy trình giải quyết tranh chấp của Shopee gồm mấy bước và Shopee đưa ra hướng giải quyết trong bao lâu? | 4 bước; hướng giải quyết trong 07 ngày làm việc từ khi nhận đủ hồ sơ, có thể lâu hơn nếu phức tạp. | `77265_907_2658` hoặc `77245_14121_15870` |
| 5 | Những nội dung nào bị nghiêm cấm đăng bán trên Shopee? | Nội dung phản động, bạo lực, khiêu dâm, thông tin rác, xúc phạm, sản phẩm độc hại, tài liệu bí mật và hàng cấm/hạn chế. | `77246_1279_2847` hoặc `77245_52118_52876` |

### Tổng hợp chất lượng truy xuất của nhóm

> Cách chấm (theo `docs/SCORING.md`): **2 điểm/câu** — top-3 chứa chunk liên quan + agent trả lời đúng (2), có liên quan nhưng thiếu/không ở top-1 (1), không có trong top-3 (0).

| # | Câu hỏi | Chiến lược tốt nhất cho câu này | Có chunk liên quan trong top-3? | Ghi chú |
|---|---------|-------------------------------|-------------------------------|---------|
| 1 | Thời hạn gửi trả hàng Shopee Mall | Không chiến lược nào | Không | Top‑3 thường đúng chủ đề/tài liệu nhưng sai section và thiếu anchor 06 ngày. |
| 2 | Hạn khiếu nại hàng hoàn hư hại | Recursive | Có, Top‑3 | FixedSize và Sentence bỏ lỡ chunk chứa “03 ngày”. |
| 3 | Các trường hợp được trả hàng/hoàn tiền | Không chiến lược nào | Không | Chunk về hoàn tiền/chi phí có điểm cao hơn chunk liệt kê điều kiện. |
| 4 | Quy trình tranh chấp và thời hạn | FixedSize | Có, Top‑1 | Sentence và Recursive cũng tìm thấy ở Top‑2. |
| 5 | Nội dung bị cấm đăng bán | Không chiến lược nào | Không | Đúng chủ đề đăng bán nhưng sai section, không có anchor “bí mật quốc gia”. |

**Lọc bằng metadata có giúp ích không? Ở câu hỏi nào?**
> A/B được chạy cho Q2 trên cả ba chiến lược. Top‑3 có filter `audience=seller` giống hệt Top‑3 không filter vì các kết quả ban đầu đã đều thuộc tài liệu seller `77250`; do đó filter không cải thiện thứ hạng trong bộ câu hỏi hiện tại. Đây là hạn chế của thiết kế benchmark: Q2 chưa tạo được phép thử có sức phân biệt, dù vẫn giữ nguyên để bảo đảm năm câu hỏi chung của nhóm.

---

## 4. Thuyết trình (Demo) & Bài học nhóm — Nhóm (5 điểm)

**Những phân tích (insights) hay nhất nhóm sẽ trình bày:**
> - Đúng `doc_id` chưa đủ: nhiều Top‑3 thuộc đúng tài liệu nhưng sai section và không chứa anchor.
> - Cosine ưu tiên độ giống chủ đề, không bảo đảm chunk chứa đúng số liệu cần trả lời.
> - A/B Q2 cho kết quả giống nhau, chứng minh metadata filter chỉ hữu ích khi tập ứng viên thực sự có tài liệu cạnh tranh khác audience.

**Bài học rút ra khi so sánh trong nhóm:**
> Cùng corpus và model embedding nhưng ranh giới chunk làm thay đổi rõ thứ hạng: FixedSize đưa Q4 lên Top‑1, Recursive tìm thêm Q2 ở Top‑3, còn Sentence tạo nhiều chunk hơn nhưng chỉ đạt 1/10. Chunk mạch lạc giúp đọc dễ hơn nhưng chưa đủ; vị trí anchor và mức độ tập trung thông tin trong chunk cũng rất quan trọng.

**Nếu làm lại, nhóm sẽ thay đổi gì trong chiến lược dữ liệu (data strategy)?**
> Nhóm sẽ làm sạch menu/phần lặp kỹ hơn, tách theo heading điều khoản và thêm overlap nhỏ để các danh sách hoặc mốc thời gian không chỉ có một cơ hội lọt Top‑k. Nhóm cũng sẽ thiết kế lại câu A/B sao cho cùng từ vựng xuất hiện ở tài liệu buyer và seller nhưng đáp án khác nhau, rồi kiểm tra metadata trước khi chốt gold set.

---

## Tự Đánh Giá (Phần Nhóm)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Lựa chọn tài liệu (Document Set Quality) | / 10 |
| Thiết kế chiến lược (Strategy Design) | / 15 |
| Chất lượng truy xuất (Retrieval Quality) | / 10 |
| Thuyết trình (Demo) | 5/ 5 |
| **Tổng phần nhóm** | **/ 40** |
