# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Đào Trọng Khang
**Nhóm:** ColdBrew
**Ngày:** 20/09/2026

> **Nộp 1 bản / sinh viên.** Phần nhóm (lựa chọn tài liệu, thiết kế chiến lược, bộ câu hỏi đánh giá, demo) nộp chung 1 bản trong `REPORT_NHOM.md`. Chi tiết thang điểm: `docs/SCORING.md`.

**Tổng điểm phần cá nhân: 60** = Khởi động (5) + Hướng tiếp cận (10) + Hoàn thiện code (30) + Dự đoán độ tương tự (5) + Kết quả truy xuất của tôi (10).

---

## 1. Khởi động (Warm-up) — Cá nhân (5 điểm)

### Độ tương tự Cosine (Cosine Similarity) (Bài tập 1.1)

**Độ tương tự cosine cao (High cosine similarity) nghĩa là gì?**
> Độ tương tự cosine cao nghĩa là hai vector có hướng gần giống nhau, cho thấy nội dung hoặc ý nghĩa của chúng có mức độ tương đồng lớn. Trong hệ thống RAG, tài liệu có điểm cosine cao thường được xem là liên quan hơn đến câu hỏi của người dùng.

**Ví dụ có độ tương tự CAO:**
- Câu A: Người mua có thể yêu cầu hoàn tiền khi sản phẩm bị lỗi.
- Câu B: Khách hàng được quyền đề nghị hoàn tiền nếu nhận được hàng bị hư hỏng.
- Tại sao tương đồng: Hai câu dùng từ khác nhau nhưng cùng diễn đạt quyền yêu cầu hoàn tiền khi sản phẩm có lỗi.

**Ví dụ có độ tương tự THẤP:**
- Câu A: Người mua có thể yêu cầu hoàn tiền khi sản phẩm bị lỗi.
- Câu B: Người bán phải đóng gói hàng hóa đúng kích thước quy định.
- Tại sao khác: Hai câu đề cập đến hai chủ đề khác nhau: câu A nói về hoàn tiền, còn câu B nói về quy định đóng gói và vận chuyển.

**Tại sao độ tương tự cosine (cosine similarity) được ưu tiên hơn khoảng cách Euclid (Euclidean distance) cho text embeddings?**
> Cosine similarity tập trung vào góc giữa hai vector nên đo được mức độ tương đồng về ngữ nghĩa mà ít bị ảnh hưởng bởi độ lớn hoặc độ dài văn bản. Trong khi đó, khoảng cách Euclid chịu ảnh hưởng nhiều hơn bởi độ lớn vector, nên hai văn bản có ý nghĩa giống nhau vẫn có thể bị đánh giá là khác biệt.

### Bài toán tính toán Chunking (Bài tập 1.2)

**Tài liệu 10,000 ký tự, chunk_size=500, overlap=50. Bao nhiêu chunks?**
> Mỗi chunk mới tiến thêm: `500 - 50 = 450` ký tự. Số chunk là `ceil((10.000 - 500) / 450) + 1 = ceil(21,11) + 1 = 23`.

**Nếu độ chồng chéo (overlap) tăng lên 100, số lượng chunk thay đổi thế nào? Tại sao muốn độ chồng chéo nhiều hơn?**
> Khi overlap=100, bước nhảy là 500 − 100 = 400, nên số lượng tăng thành ceil((10.000 − 500)/400) + 1 = 25 chunks. Overlap lớn hơn giúp giữ ngữ cảnh ở ranh giới giữa các chunk, nhưng làm tăng dữ liệu trùng lặp và chi phí xử lý.

---

## 2. Hướng tiếp cận của tôi (My Approach) — Cá nhân (10 điểm)

Giải thích cách tiếp cận của bạn khi lập trình (implement) các phần chính trong gói `src`.

### Các hàm chia nhỏ (Chunking Functions)

**`SentenceChunker.chunk`** — hướng tiếp cận:
> Tôi dùng regex `(?<=[.!?])(?:[ \t]+|\n+)` để tách văn bản tại khoảng trắng hoặc xuống dòng ngay sau các dấu kết thúc câu `.`, `!`, `?`, rồi nhóm tối đa `max_sentences_per_chunk` câu. Các trường hợp cần xử lý gồm văn bản rỗng/toàn khoảng trắng, câu cuối không có dấu kết thúc và văn bản không chứa dấu câu; các phần rỗng sau khi tách sẽ bị loại bỏ.

**`RecursiveChunker.chunk` / `_split`** — hướng tiếp cận:
> Thuật toán lần lượt thử các dấu phân cách theo mức ưu tiên `["\n\n", "\n", ". ", " ", ""]`, ghép các phần nhỏ khi tổng độ dài chưa vượt quá `chunk_size`; phần vẫn quá dài sẽ được xử lý đệ quy bằng dấu phân cách tiếp theo. Base case là đoạn văn đã ngắn hơn hoặc bằng `chunk_size`; nếu hết dấu phân cách, văn bản được cắt trực tiếp theo số ký tự.

### Lớp EmbeddingStore

**`add_documents` + `search`** — hướng tiếp cận:
> `add_documents` chuyển nội dung của mỗi `Document` thành vector embedding rồi lưu cùng `id`, nội dung và bản sao metadata trong store in-memory. `search` tạo embedding cho câu truy vấn, tính cosine similarity với từng vector đã lưu, sắp xếp giảm dần và trả về `top_k` kết quả liên quan nhất.

**`search_with_filter` + `delete_document`** — hướng tiếp cận:
> `search_with_filter` lọc trước các bản ghi có metadata khớp hoàn toàn với `metadata_filter`, sau đó mới tính độ tương tự và chọn `top_k`, giúp kết quả chỉ thuộc phạm vi yêu cầu. `delete_document` tìm và xóa toàn bộ chunk có `metadata["doc_id"]` trùng với `doc_id` cần xóa, đồng thời trả về `True` nếu có bản ghi bị xóa và `False` nếu không tìm thấy.
### Tác tử KnowledgeBaseAgent

**`answer`** — hướng tiếp cận:
> `answer` gọi vector store để lấy `top_k` chunk liên quan nhất, đánh số từng chunk kèm nguồn rồi ghép chúng vào phần Ngữ cảnh trong prompt. Prompt yêu cầu mô hình chỉ trả lời dựa trên ngữ cảnh, trích dẫn số nguồn và nói rõ khi không đủ thông tin, giúp giảm hiện tượng bịa đặt.
---

## 3. Hoàn thiện code (Core Implementation) — Cá nhân (30 điểm)

Vượt qua bộ kiểm thử là điều kiện tính điểm phần này.

### Kết Quả Kiểm Thử (Test Results)

```text
======================== 42 passed, 1 warning in 0.12s ========================
```

**Số lượng bài test vượt qua (pass):** 42 / 42

---

## 4. Dự đoán độ tương tự (Similarity Predictions) — Cá nhân (5 điểm)

**Embedding backend:** `LocalEmbedder` với model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (vector được chuẩn hóa).

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|------|-----------|-----------|---------|--------------|-------|
| 1 | Người mua có thể yêu cầu hoàn tiền khi sản phẩm bị lỗi. | Khách hàng được quyền đề nghị hoàn tiền nếu hàng hóa bị hư hỏng. | Cao | 0.871968 | Có |
| 2 | Người bán phải đóng gói sản phẩm đúng quy định vận chuyển. | Nhà bán hàng cần đóng gói kiện hàng theo hướng dẫn giao nhận của Shopee. | Cao | 0.775356 | Có |
| 3 | Shopee xử lý khiếu nại trong vòng bảy ngày làm việc. | Người bán phải phản hồi yêu cầu hoàn tiền trong hai ngày lịch. | Thấp | 0.422857 | Có |
| 4 | Sản phẩm phải còn ít nhất ba mươi phần trăm thời hạn sử dụng. | Thực phẩm sắp hết hạn cần ghi rõ ngày hết hạn trong mô tả. | Cao | 0.165655 | Không |
| 5 | Người mua có thể yêu cầu trả hàng trên ứng dụng Shopee. | Python là một ngôn ngữ lập trình bậc cao. | Thấp | 0.047819 | Có |

**Kết quả nào bất ngờ nhất? Điều này nói gì về cách embeddings biểu diễn ý nghĩa?**
> Bất ngờ nhất là cặp 4 cùng nói về hạn sử dụng nhưng chỉ đạt `0.165655`; hai câu liên quan nhưng tập trung vào hai quy định khác nhau nên model không xem chúng là diễn đạt tương đương. Ngược lại, cặp 1 và 2 đạt điểm cao, còn cặp Shopee–Python gần 0, cho thấy embedding đa ngôn ngữ biểu diễn quan hệ ngữ nghĩa hợp lý hơn mock.

---

## 5. Kết quả truy xuất của tôi (Competition Results) — Cá nhân (10 điểm)

Chạy **5 câu hỏi đánh giá của nhóm** trên mã nguồn cá nhân của bạn trong gói `src`. **5 câu hỏi này phải trùng với các thành viên cùng nhóm** (xem `REPORT_NHOM.md`).

**Cấu hình lượt chạy:** `LocalEmbedder` với model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, `RecursiveChunker(chunk_size=1800)`, 171 chunks từ 7 tài liệu. Kết quả được chấm ở mức nội dung: `doc_id` phải thuộc gold và chunk phải chứa chuỗi `anchor`; đúng ở Top-1 được 2 điểm, đúng ở Top-2/3 được 1 điểm, vắng khỏi Top-3 được 0 điểm.

| # | Câu hỏi (Query) | Top-1 Chunk truy xuất được (tóm tắt) | Điểm Score | Có liên quan không? (Relevant) | Câu trả lời của Agent (tóm tắt) |
|---|-------|--------------------------------|-------|-----------|------------------------|
| 1 | Mua hàng trên Shopee Mall, sau khi yêu cầu trả hàng được chấp thuận thì phải gửi trả sản phẩm trong bao nhiêu ngày? | `77262#8`: cùng tài liệu Mall nhưng nói về Shopee gửi hàng hoàn lại cho Người Bán, không chứa mốc 06 ngày dành cho Người Mua. | 0.823048 | Không | Top-3 đúng chủ đề nhưng sai section và không chứa anchor, nên Agent không đủ căn cứ trả lời mốc 06 ngày. |
| 2 | Hàng bị hư hại trong quá trình vận chuyển thì phải khiếu nại trong vòng bao nhiêu ngày? | `77250#9`: thời gian Shopee xử lý khiếu nại tối đa 10 ngày, không phải hạn Người Bán gửi khiếu nại. | 0.610803 | Không | Chunk đúng `77250#8` nằm ở Top-3: hàng hoàn bị hư hại/không nguyên vẹn phải được khiếu nại trong 03 ngày. |
| 3 | Người mua được yêu cầu trả hàng/hoàn tiền trong những trường hợp nào? | `77251#10`: quy định mức hoàn tiền do Người Bán đề xuất, không chứa danh sách các trường hợp được yêu cầu trả hàng. | 0.730486 | Không | Top-3 không chứa anchor “sai kích cỡ, sai màu sắc”, nên Agent không đủ ngữ cảnh để liệt kê chính xác. |
| 4 | Quy trình giải quyết tranh chấp của Shopee gồm mấy bước và Shopee đưa ra hướng giải quyết trong bao lâu? | `77262#7`: thời hạn xử lý yêu cầu trả hàng Shopee Mall, không phải quy trình tranh chấp bốn bước. | 0.706448 | Không | Chunk đúng `77265#1` đứng Top-2: quy trình gồm 4 bước và thời hạn là 07 ngày làm việc từ khi nhận đủ hồ sơ. |
| 5 | Những nội dung nào bị nghiêm cấm đăng bán trên Shopee? | `77262#4`: danh sách sản phẩm bị loại trừ khỏi trả hàng Shopee Mall, không phải danh sách nội dung cấm đăng bán. | 0.685688 | Không | Top-3 không chứa anchor “bí mật quốc gia”, nên Agent không thể liệt kê đầy đủ các nội dung bị cấm. |

**Bao nhiêu câu hỏi trả về chunk có liên quan trong top-3?** 2 / 5 — tổng điểm retrieval theo thang 2/1/0 là **2/10**.

**Failure case tiêu biểu:** Q1 lấy đúng tài liệu `77262` ở Top-1 và Top-2 nhưng sai section; các chunk này nói về thời hạn xử lý/gửi hàng hoàn, không chứa mốc “06 (sáu) ngày lịch” mà câu hỏi cần. Cosine ưu tiên độ giống chủ đề hơn mật độ thông tin trả lời; hướng cải thiện là chunk theo heading nhỏ hơn, thêm overlap hoặc rerank theo từ khóa/mốc thời gian.

**A/B metadata filter:** Với Q2, Top-3 của cả ba chiến lược giống hệt nhau giữa lượt không filter và lượt `audience=seller`. Filter chưa tạo lợi ích vì kết quả không lọc vốn đã hoàn toàn thuộc tài liệu seller `77250`; do đó câu hỏi/metadata hiện tại chưa tạo được phép thử A/B có sức phân biệt.

**Điều hay nhất tôi học được từ thành viên khác / nhóm khác (qua demo):**
> Tôi học được rằng không nên đánh giá retrieval chỉ bằng việc `doc_id` đúng xuất hiện trong Top-3, vì chunk thuộc đúng tài liệu vẫn có thể nằm sai section và không chứa câu trả lời. Cần kiểm tra thêm anchor trong nội dung, đồng thời so sánh có/không có metadata filter để thấy rõ sự đánh đổi giữa precision và recall.

---

## Tự Đánh Giá (Phần Cá Nhân)

| Tiêu chí | Điểm tự đánh giá |
|----------|-------------------|
| Khởi động (Warm-up) | 5 / 5 |
| Hướng tiếp cận của tôi (My Approach) | 10 / 10 |
| Hoàn thiện code (Core Implementation — tests) | 30 / 30 |
| Dự đoán độ tương tự (Similarity Predictions) | 5 / 5 |
| Kết quả truy xuất của tôi (Competition Results) | 2 / 10 |
| **Tổng phần cá nhân** | **52 / 60** |
