# Báo cáo: Thiết kế dữ liệu cho Giai đoạn 1

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

| Mục | Thông tin |
| --- | --- |
| Học viên | … |
| Giảng viên hướng dẫn | TS. Mai Đức Thọ |
| Ngày | 07/11/2026 |
| Nội dung | Trả lời các câu hỏi về dữ liệu nêu trong buổi trao đổi gần nhất |

## Tóm tắt

Báo cáo trả lời năm câu hỏi về dữ liệu đã được nêu trong buổi trao đổi: (1) tạo bộ dữ liệu theo dạng nào; (2) xử lý mất cân bằng dữ liệu ra sao; (3) dữ liệu có đặc điểm gì và từ đó chọn mô hình nào; (4) thu thập dữ liệu thế nào, bắt đầu từ việc hiểu dữ liệu thật rồi mới tạo dữ liệu tổng hợp; (5) chuẩn hóa dữ liệu ra sao. Các số liệu trích dẫn đã được đối chiếu với toàn văn các bài báo gốc và mã nguồn của PyPI.

Các đề xuất chính:

1. **Lớp âm:** dùng các tên gói thật mà chính LLM gợi ý trong cùng lượt sinh mã (ký hiệu N2), thay vì lấy ngẫu nhiên từ registry. Nhãn chia thành 4 loại thay vì 2.
2. **Mất cân bằng:** khi huấn luyện, xử lý bằng trọng số lớp. Khi đánh giá, giữ nguyên tỷ lệ thực tế và báo cáo TPR@1%FPR cùng Precision theo tỷ lệ cơ sở.
3. **Mô hình:** chỉ 13,4% tên ảo giác cách tên thật 1–2 ký tự [1], nên tín hiệu chủ yếu nằm ở cấp từ. Cần so sánh 1D-CNN mức ký tự với một baseline n-gram và một mô hình subword.
4. **Nguồn dữ liệu:** kết hợp bộ dữ liệu công khai (0pstech, CC BY 4.0) với dữ liệu tự sinh theo quy trình của Spracklen et al. [1], đối chiếu với bản chụp registry mới.
5. **Chuẩn hóa:** áp dụng chuẩn PEP 503 cho cả hai lớp. Ràng buộc tấn công ở Giai đoạn 2 cần bổ sung luật chặn tên gần giống của PyPI.

## 1. Định nghĩa lớp và cấu trúc bộ dữ liệu

Lớp dương là tên gói do LLM tạo ra nhưng không phải gói mà người dùng cần. Việc chọn lớp âm quyết định mô hình học được gì, nên được cân nhắc giữa ba phương án:

| Lớp âm | Ưu điểm | Nhược điểm |
| --- | --- | --- |
| N1. Tên lấy ngẫu nhiên trên toàn PyPI | Dễ thu thập | Phân bố khác xa lớp dương (nhiều tên cá nhân, tên thử nghiệm). Mô hình dễ học khác biệt về phong cách đặt tên thay vì dấu hiệu đáng ngờ |
| **N2. Tên gói thật do chính LLM gợi ý trong cùng lượt sinh mã** | Cùng nguồn và cùng phân bố với lớp dương. Thu được đồng thời khi sinh dữ liệu | Thiên về các gói phổ biến |
| N3. Top-N gói phổ biến | Nhãn sạch | Quá dễ phân biệt, làm kết quả lạc quan |

**Đề xuất dùng N2 làm lớp âm chính.** N1 (lấy mẫu) và các gói mới đăng trên RSS của PyPI được dùng riêng để đo FPR trong điều kiện thực tế. Lựa chọn này có ảnh hưởng đáng kể đến kết quả: trong bài toán tương tự về tên miền DGA, Peck et al. [6] ghi nhận chỉ riêng việc đổi danh sách tên miền lành (Alexa sang Qname) đã làm kết quả phát hiện thay đổi rõ rệt.

**Phân loại nhãn.** Đề xuất chia nhãn thành 4 loại:

| Nhãn | Ví dụ | Tra registry có phát hiện được không |
| --- | --- | --- |
| Tên thật, đúng mục đích | `requests`, `numpy` | Không cần phát hiện |
| Tên không tồn tại (404) | `vectorcache`, `chromastore` [3] | Có |
| Tên module hoặc tên nhầm, nhưng đã có người đăng ký | `pil` (gói đúng: Pillow), `skimage` (scikit-image), `faiss` (faiss-cpu) [3] | **Không**, registry trả về 200 |
| Tên thuộc hệ sinh thái khác | 8,7% tên Python bị bịa là gói npm có thật [1] | Tùy hệ sinh thái |

Loại thứ ba là cơ sở để cần một bộ phát hiện học máy thay vì chỉ tra registry. Raj và Sahu [3] ghi nhận khoảng một nửa số tên bị gắn cờ trong thực nghiệm của họ là tên đã có người đăng ký, nên phép kiểm tra tồn tại không phát hiện được.

**Cấu trúc một bản ghi** trong bộ dữ liệu:

| Nhóm trường | Trường |
| --- | --- |
| Tên gói | `name_raw`, `name_normalized`, `ecosystem` |
| Nhãn | `label` (4 loại ở trên), `label_source` (tự động hoặc kiểm tra thủ công) |
| Nguồn sinh | `source_model`, `prompt_id`, `heuristic` (H1/H2/H3, xem mục 4.2), `temperature`, `repeat_count` |
| Trạng thái registry | `first_seen`, `registry_status`, `check_date` |
| Phục vụ chia tập | `nearest_real_pkg`, `edit_distance`, `group_id` (nhóm tên gần giống), `split` |

## 2. Xử lý mất cân bằng dữ liệu

Cần phân biệt hai loại mất cân bằng: mất cân bằng trong tập huấn luyện và mất cân bằng khi triển khai thực tế.

### 2.1. Khi huấn luyện

Với lớp âm N2, tỷ lệ mẫu dương bằng tỷ lệ ảo giác tự nhiên của LLM (tính theo lượt gợi ý): khoảng 5,2% với mô hình thương mại và 21,7% với mô hình mã nguồn mở [1]; các mô hình năm 2026 ở mức 4,62–6,10% [2]. Đây là mức mất cân bằng vừa phải. Phương án xử lý:

- Dùng trọng số lớp (`class_weight`) hoặc lấy mẫu có trọng số; có thể thử thêm focal loss.
- **Không dùng SMOTE.** SMOTE nội suy trong không gian đặc trưng, nên mẫu sinh ra không tương ứng với tên gói hợp lệ. Điều này mâu thuẫn với ràng buộc problem-space mà đề cương đã đặt ra.
- Không nhân bản mẫu trước khi chia tập, để tránh cùng một tên xuất hiện ở cả tập huấn luyện và tập kiểm thử.
- Không tăng cường dữ liệu bằng nhiễu ký tự ở Giai đoạn 1. Làm như vậy tương đương với huấn luyện đối kháng ngầm, khiến phép so sánh giữa D0 và D′ ở Giai đoạn 2 mất ý nghĩa.

### 2.2. Khi đánh giá và triển khai

Trong thực tế, tỷ lệ tên đáng ngờ thấp hơn nhiều so với trong tập huấn luyện. Vì vậy tập kiểm thử giữ nguyên tỷ lệ, không cân bằng lại. Chỉ số chính là TPR@1%FPR và PR-AUC; Precision được quy đổi theo tỷ lệ cơ sở π:

```math
\text{Precision} = \frac{\text{TPR} \cdot \pi}{\text{TPR} \cdot \pi + \text{FPR} \cdot (1 - \pi)}
```

Ví dụ với TPR = 0,90 và FPR = 1%: khi π = 5%, Precision ≈ 83%; khi π = 0,1%, Precision chỉ còn ≈ 8%. Montaruli et al. [5] gặp đúng hiện tượng này khi triển khai thực tế (Precision 18,73% ở FPR 1%). Arp et al. [7] xếp việc bỏ qua tỷ lệ cơ sở vào nhóm lỗi phổ biến trong học máy cho an toàn thông tin (P8, *base rate fallacy*).

### 2.3. Cỡ mẫu tập kiểm thử

Cỡ mẫu tối thiểu ước tính theo khoảng tin cậy 95% (xấp xỉ chuẩn):

| Đại lượng | Sai số mong muốn | Số mẫu cần |
| --- | --- | --- |
| FPR quanh 1% | ±0,2 điểm % | khoảng 10.000 tên âm |
| TPR quanh 90% | ±2,6 điểm % | khoảng 500 tên dương **duy nhất** |

Để so sánh, mỗi tập kiểm thử trong Raj và Sahu [3] chỉ có 2–12 mẫu dương, và chính các tác giả nhận định cần khoảng 30 mẫu mới đủ để kết luận.

### 2.4. Chống rò rỉ dữ liệu khi chia tập

Raj và Sahu [3] ban đầu chia tập ngẫu nhiên theo dòng, khiến 72,9% dòng kiểm thử trùng tên với tập huấn luyện; các tác giả phải chạy lại với cách chia theo tên duy nhất. Quy trình đề xuất:

1. Khử trùng lặp sau khi chuẩn hóa tên.
2. Gom các tên gần giống thành nhóm (khoảng cách sửa ≤ 2 hoặc cùng gốc từ), rồi chia tập theo nhóm.
3. Bổ sung hai cách chia phụ: theo mô hình nguồn (huấn luyện trên 3 LLM, kiểm thử trên LLM còn lại) và theo thời gian. Theo Spracklen et al. [1], 81% tên bị bịa chỉ do một mô hình sinh ra, nên cách chia theo mô hình là phép thử khó nhưng có giá trị về khả năng tổng quát hóa.

## 3. Đặc điểm dữ liệu và lựa chọn mô hình

### 3.1. Đặc điểm dữ liệu

- **Chuỗi ngắn, bảng ký tự nhỏ.** Sau chuẩn hóa, tên gói PyPI chỉ gồm các ký tự `[a-z0-9-]`, tức 37 ký tự.
- **Phần lớn không phải lỗi gõ.** Trên 76.489 tên Python bị bịa, Spracklen et al. [1] đo khoảng cách Levenshtein tới gói thật gần nhất: 13,4% ở mức 1–2, 37,9% ở mức 3–5 và 48,6% từ 6 trở lên. Đa số là các tổ hợp từ có vẻ hợp lý.
- **Tín hiệu từ riêng tên gói có thể yếu.** Trong Raj và Sahu [3], 82% mức quan trọng của bộ phân loại đến từ hai đặc trưng metadata: số người duy trì (57,6%) và việc có liên kết GitHub (24,5%). Một luật OR đơn giản trên hai đặc trưng này đạt F1 tương đương Random Forest.

Từ đặc điểm thứ ba, cần một **thí nghiệm thăm dò (pilot)** đo mức tín hiệu tối đa có thể khai thác từ riêng tên gói, trước khi đầu tư vào Giai đoạn 2. Nếu mô hình chỉ dùng tên không phân biệt được lớp dương với N2, phạm vi “bộ phát hiện chỉ dùng tên” trong đề cương cần được xem xét lại (xem câu hỏi 2 ở mục 7).

### 3.2. Các mô hình đề xuất so sánh

| Mô hình | Vai trò | Hỗ trợ tấn công Faster-GCG (cần gradient) |
| --- | --- | --- |
| Logistic Regression hoặc XGBoost trên TF-IDF n-gram ký tự (1–5) kết hợp đặc trưng thủ công | Baseline mạnh, dễ diễn giải; Arp et al. [7] lưu ý việc thiếu baseline đơn giản là lỗi thường gặp (P6) | Không; chỉ đánh giá được với tấn công black-box |
| 1D-CNN mức ký tự (D0 theo đề cương) | Mô hình chính | Có |
| fastText subword, hoặc CodeBERT/transformer cỡ nhỏ | Kiểm tra giả thuyết tín hiệu nằm ở cấp từ | Có |

Đặc trưng thủ công tham khảo theo Raj và Sahu [3]: độ dài, số đoạn, số chữ số, tiền tố `py-`/`python-`, các từ “quảng cáo” (super, pro, ai), các từ chung chung (helper, tools), và độ tương đồng với 15.000 tên PyPI phổ biến nhất.

Nếu baseline n-gram đã đạt gần mức trần, việc dùng mạng nơ-ron cần được lý giải thêm (ví dụ để có gradient phục vụ Giai đoạn 2). Kết quả này cũng sẽ được báo cáo như một phát hiện.

## 4. Nguồn và quy trình thu thập dữ liệu

Quy trình gồm hai bước: khảo sát dữ liệu thật từ các bộ công khai, sau đó tự sinh dữ liệu theo quy trình của Spracklen et al. [1] và đối chiếu với bản chụp registry mới.

### 4.1. Khảo sát dữ liệu thật từ các nguồn công khai

| Nguồn | Nội dung | Giấy phép / truy cập |
| --- | --- | --- |
| 0pstech/slopsquatting-dataset [12] | 2.170 tên (PyPI 1.066, npm 820) tại ngày 05/11/2026; có các trường `models`, `tasks`, `first_seen`, `registry_status`; thu thập bằng tác vụ lập trình thông thường | CC BY 4.0 |
| DepScope [13] | Tên quan sát được từ lưu lượng thực của AI agent, 19 hệ sinh thái | CC BY-NC-SA 4.0 |
| Trend Micro [14] | 100 tác vụ phát triển web; mỗi bản ghi gồm mô hình, tác vụ, dependencies, tên ảo giác | MIT |
| Spracklen et al. [1], [15] | 205.474 tên duy nhất; kho mã chỉ công bố bộ prompt và danh sách gói thật | Chỉ cấp cho nhà nghiên cứu đã xác minh. Đã gửi yêu cầu; đến ngày 07/11/2026 chưa nhận được phản hồi. Kế hoạch không phụ thuộc vào nguồn này |
| Churilov [2], [16] | 127 tên mà cả 5 mô hình cùng bịa | Tạm thời chưa công bố do quy trình công bố có trách nhiệm |

Phân tích khám phá (EDA) trên các nguồn này gồm: phân bố độ dài và số đoạn, ký tự phân tách, các từ thường gặp, khoảng cách tới gói thật gần nhất, và tỷ lệ 4 loại nhãn. Kết quả EDA cũng là chuẩn để kiểm tra dữ liệu tự sinh có lệch phân bố hay không.

### 4.2. Tự sinh dữ liệu

Dùng 4 bộ prompt của Spracklen et al. [15] (`SO_AT`, `SO_LY`, `LLM_AT`, `LLM_LY`), gồm 20.163 câu hỏi từ Stack Overflow và 19.806 câu hỏi do LLM sinh [2]. Tên gói được trích bằng cả ba heuristic của Spracklen et al. [1]:

1. **H1:** đọc lệnh `pip install` trong mã sinh ra. Lệnh này chỉ xuất hiện ở 7% đầu ra, nên không đủ nếu dùng riêng.
2. **H2:** đưa đoạn mã vừa sinh lại cho chính mô hình và hỏi cần cài những gói nào.
3. **H3:** hỏi mô hình những gói cần thiết cho tác vụ ban đầu.

**Không trích tên từ câu lệnh `import`**, vì tên module khác tên gói phân phối (ví dụ `cv2` thuộc gói opencv-python, `sklearn` thuộc scikit-learn). Churilov [2] có trích từ `import`, và các “ảo giác” xuất hiện nhiều nhất trong bài thực chất là tên module bị nhầm thành tên gói: `rest-framework`, `objc`, `opengl`, `mpl-toolkits`.

Mọi tên được gợi ý, cả thật lẫn bịa, đều được ghi lại để tạo lớp N2. Tần suất lặp lại cũng được lưu: trên 500 prompt được lặp 10 lần, Spracklen et al. [1] ghi nhận 43% tên bịa xuất hiện lại ở cả 10 lần, còn 39% không lặp lại lần nào. Những tên lặp lại nhiều là mục tiêu thực sự của kẻ tấn công.

### 4.3. Ước tính sản lượng dữ liệu

Hai mốc ước tính dưới đây chênh nhau đáng kể, nên quy mô sinh dữ liệu sẽ được chốt sau khi có số đo từ pilot:

- **Mốc trên**, theo cách làm của Spracklen et al. [1] (đủ H1–H3): mỗi mẫu mã cho trung bình khoảng 3,9 lượt tên gói (khoảng 2,24 triệu lượt trên 576.000 mẫu), và khoảng 47% lượt ảo giác là tên duy nhất. Với 10.000 prompt cho mỗi mô hình, PHR 5% cho khoảng 900 tên duy nhất; PHR 20% (mô hình mã nguồn mở) cho khoảng 3.600 tên. Tỷ lệ tên duy nhất được tính gộp trên 16 mô hình, nên con số cho từng mô hình có thể khác.
- **Mốc dưới**, theo Churilov [2] (chỉ trích từ mã, không có H2/H3): khoảng 40.000 prompt cho mỗi mô hình ở PHR 4,62% cho hơn 1.300 lượt ảo giác, tương ứng vài trăm tên duy nhất.

Pilot sẽ đo **số tên ảo giác duy nhất trên 1.000 prompt** cho từng mô hình. Mô hình mã nguồn mở như CodeLlama-13B vừa cho nhiều mẫu dương vừa có chi phí thấp nhất.

### 4.4. Xác minh nhãn

- **Chụp lại danh sách gói thật, có ghi ngày.** Danh sách đi kèm Spracklen et al. [1] được chụp ngày 10/01/2024 (500.565 tên PyPI). Churilov [2] vẫn dùng danh sách này cho dữ liệu tháng 4/2026, nên các gói đăng ký sau tháng 01/2024 có thể bị tính nhầm là ảo giác.
- **Tên bị bịa nhưng sau đó có người đăng ký** (ngày `first_seen` trước ngày đăng ký) nhiều khả năng là gói slopsquatting thực sự, nên không được xếp vào lớp âm.
- **Kiểm tra thủ công một mẫu đủ lớn** để báo cáo độ chính xác của nhãn kèm khoảng tin cậy. Ví dụ, con số 95,8% của Twist et al. [4] dựa trên 24 response bị gắn cờ (23 đúng), nên khoảng tin cậy Wilson 95% còn rộng: 79,8–99,3%.
- **Với npm:** các API replication cũ đã ngừng từ ngày 29/05/2025 [11], cần xác định cách tải danh sách tên mới trước khi xây dựng pipeline.

### 4.5. Dữ liệu tổng hợp

Nếu cần dùng LLM sinh thêm tên giả để đủ số lượng:

- Dữ liệu tổng hợp chỉ dùng để huấn luyện, không dùng để kiểm thử. Tập kiểm thử chỉ gồm ảo giác thật.
- Không dùng cùng cơ chế với tấn công LLM-guided ở Giai đoạn 2. Nếu dùng, D0 đã được huấn luyện ngầm trên chính kiểu tấn công black-box, làm sai lệch ASR. Arp et al. [7] xếp việc đánh giá chủ yếu trên dữ liệu tổng hợp vào nhóm lỗi P9 (*lab-only evaluation*).

## 5. Chuẩn hóa dữ liệu

Hai lớp được chuẩn hóa theo cùng một quy tắc của registry. Ràng buộc tấn công ở Giai đoạn 2 cần tính thêm luật chặn tên gần giống của PyPI.

### 5.1. PyPI

Trước tiên loại bỏ các phần không thuộc tên gói: version specifier, extras (ví dụ `requests[security]>=2.0`), URL, `git+…`, đường dẫn cục bộ và chú thích. Sau đó chỉ giữ các tên hợp lệ theo đặc tả của PyPA [8], áp dụng với `re.IGNORECASE`; biểu thức kết thúc bằng `\Z` thay vì `$` theo bản sửa tháng 8/2025:

```
^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])\Z
```

Tiếp đó chuẩn hóa theo PEP 503 [8]:

```python
import re

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()
```

### 5.2. Luật chặn tên gần giống của PyPI

Mã nguồn PyPI [9] có hàm `ultranormalize_name`: bỏ các ký tự `.`, `_`, `-`; đổi `l` và `i` thành `1`, `o` thành `0`; rồi chuyển về chữ thường. Nếu tên mới trùng với một dự án đã có sau phép biến đổi này, PyPI từ chối đăng ký (`ProjectNameUnavailableSimilarError`). PyPI cũng duy trì một danh sách tên cấm. Theo Churilov [2], hai cơ chế này khiến 68 trong 109 tên PyPI mà cả 5 mô hình cùng bịa không thể đăng ký được.

Hệ quả cho Giai đoạn 2: bước kiểm tra ràng buộc problem-space trong kịch bản Faster-GCG (bước 5) cần bổ sung luật này. Các phép thay thế kiểu `o↔0` hay `l↔1` thường không có giá trị với kẻ tấn công vì bị chặn khi đăng ký.

### 5.3. npm

- Tên gói viết thường, tối đa 214 ký tự, an toàn cho URL, không bắt đầu bằng `.` hoặc `_` [10].
- Với tên có scope (`@scope/name`), scope được tách thành một đặc trưng riêng. Nhiều tên có scope không thể đăng ký bởi người ngoài; ví dụ `@ember/*` chỉ tổ chức Ember sử dụng được [2].
- Registry vẫn còn các tên cũ có chữ hoa, nên lớp âm cũng phải được chuẩn hóa.

### 5.4. Các lưu ý về phương pháp

1. **Chuẩn hóa hai lớp giống hệt nhau.** LLM thường viết tên theo kiểu module với dấu `_`, trong khi tên trên PyPI dùng `-`. Nếu không chuẩn hóa, mô hình có thể chỉ học quy tắc “có dấu `_` là ảo giác”, một dạng tương quan giả (P4) theo Arp et al. [7].
2. **Chỉ học các tham số tiền xử lý trên tập huấn luyện.** Từ vựng n-gram, trọng số TF-IDF và danh sách top-N dùng để tính khoảng cách Levenshtein chỉ được xây dựng từ tập huấn luyện, tránh lỗi rò rỉ dữ liệu (P3, *data snooping*) [7].
3. **Mã hóa đầu vào:** bảng 37 ký tự cộng hai ký hiệu PAD và UNK. Độ dài tối đa đặt theo phân vị 99 thu được từ EDA. Faster-GCG tìm kiếm trên dạng đã chuẩn hóa, vì các biến đổi như `_` thành `-` không tạo ra tên mới trên registry.

## 6. Những điểm cần điều chỉnh trong đề cương

| Nội dung trong đề cương v2 | Đề xuất điều chỉnh | Căn cứ |
| --- | --- | --- |
| Lớp âm chưa được định nghĩa cụ thể | Dùng N2 làm lớp âm chính; N1 và RSS PyPI dùng đo FPR thực tế | Mục 1 |
| Nhãn nhị phân (ảo giác / hợp lệ) | 4 loại nhãn, tách riêng tên nhầm đã có người đăng ký | Mục 1 |
| Chỉ số chính: Precision, Recall, F1, AUC-ROC, FPR | Chỉ số chính: TPR@1%FPR, PR-AUC, Precision theo tỷ lệ cơ sở | Mục 2.2 |
| Ràng buộc problem-space: tên hợp lệ, chưa tồn tại và đủ hợp lý để LLM gợi ý | Bổ sung luật ultranormalization và danh sách tên cấm của PyPI | Mục 5.2 |
| D0 là 1D-CNN, đối chiếu với RF/XGBoost | Bổ sung baseline n-gram và mô hình subword; làm pilot đo mức tín hiệu của tên | Mục 3 |

## 7. Kế hoạch tiếp theo và đề xuất xin ý kiến

### 7.1. Các bước tiếp theo

| Bước | Nội dung | Kết quả đầu ra |
| --- | --- | --- |
| 1 | Tải bộ dữ liệu 0pstech và Trend Micro; chụp danh sách gói PyPI hiện tại | Dữ liệu thô và bản chụp registry có ghi ngày |
| 2 | EDA trên dữ liệu thật; chốt định nghĩa lớp âm, 4 loại nhãn và cấu trúc bản ghi | Báo cáo EDA |
| 3 | Pilot: khoảng 300 prompt trên 2 mô hình chi phí thấp, kết hợp bộ 0pstech; huấn luyện baseline n-gram | Số tên ảo giác duy nhất trên 1.000 prompt; mức tín hiệu tối đa của tên |
| 4 | Nếu kết quả pilot đạt yêu cầu: sinh dữ liệu đầy đủ, chia tập theo nhóm, theo mô hình và theo thời gian | Bộ dữ liệu cho Giai đoạn 1 |
| 5 | Cập nhật bước 5 trong kịch bản Faster-GCG theo luật ultranormalization | Kịch bản tấn công bản sửa |

### 7.2. Các vấn đề kính đề nghị thầy cho ý kiến

1. Việc dùng N2 (tên gói thật do LLM gợi ý) làm lớp âm chính có phù hợp không?
2. Nếu pilot cho thấy riêng tên gói chứa ít tín hiệu, có nên bổ sung đặc trưng ngữ cảnh (prompt, tác vụ) hoặc metadata không? Điều này sẽ thay đổi phạm vi “bộ phát hiện chỉ dùng tên” trong đề cương.
3. Hệ sinh thái npm nên giữ trong phạm vi chính hay chuyển sang phần mở rộng?

## Phụ lục A. Đính chính số liệu so với báo cáo khảo sát trước

Sau khi đối chiếu với toàn văn các bài báo, có 4 số liệu trong báo cáo khảo sát trước cần sửa:

| Nội dung | Báo cáo trước ghi | Bài gốc ghi |
| --- | --- | --- |
| Tỷ lệ lỗi gõ [1] | 13% là lỗi gõ lệch 1 ký tự | 13,4% có khoảng cách Levenshtein 1–2; 37,9% ở mức 3–5; 48,6% từ 6 trở lên |
| Cách trích tên gói [1] | Lấy từ lệnh `pip install` | 3 heuristic H1–H3; `pip install` chỉ có ở 7% đầu ra; không dùng `import` |
| Độ chính xác nhãn [4] | Kiểm tra thủ công 200 mẫu, đúng 95,8% | Lấy mẫu 200 response; 23/24 response bị gắn cờ là đúng; khoảng tin cậy Wilson 95%: 79,8–99,3% |
| Danh sách gói thật [2] | Không nêu | Dùng lại danh sách của Spracklen et al. chụp ngày 10/01/2024 cho dữ liệu tháng 4/2026 |

Các số liệu sau đã được xác nhận khớp với bài gốc:

- Spracklen et al. [1]: PHR 19,7% (440.445 lượt); 205.474 tên duy nhất; 5,2% (thương mại) và 21,7% (mã nguồn mở); 8,7% (6.705/76.489) tên Python bị bịa là gói npm có thật; gói đã bị xóa chỉ chiếm 0,17%.
- Churilov [2]: PHR 4,62–6,10%; dùng khoảng tin cậy Wilson, kiểm định χ² và hiệu chỉnh Holm; 127 tên cả 5 mô hình cùng bịa, 53 tên còn đăng ký được.
- Montaruli et al. [5]: TPR@1%FPR 95,27% → 24,30% khi bị tấn công → 86,81% sau huấn luyện đối kháng; Precision 18,73% ở FPR 1%; 2,18 cảnh báo sai mỗi ngày; dữ liệu 3.190 gói độc hại và 3.368 gói bình thường.
- Peck et al. [6]: sau khi huấn luyện lại, LSTM.MI chỉ phát hiện được 52,67–55,19% mẫu CharBot ở FPR 0,1%; huấn luyện đối kháng white-box được các tác giả nêu là hướng nghiên cứu tiếp theo.
- Raj và Sahu [3]: 82% mức quan trọng của bộ phân loại đến từ hai đặc trưng metadata (57,6% và 24,5%).

## Tài liệu tham khảo

1. J. Spracklen, R. Wijewickrama, A. H. M. N. Sakib, A. Maiti, B. Viswanath, M. Jadliwala. “We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs.” *USENIX Security Symposium*, 2025. [arXiv:2406.10279](https://arxiv.org/abs/2406.10279)
2. A. Churilov. “The Range Shrinks, the Threat Remains: Re-evaluating LLM Package Hallucinations on the 2026 Frontier-Model Cohort.” Bản tiền ấn phẩm, chưa qua bình duyệt, 2026. [arXiv:2605.17062](https://arxiv.org/abs/2605.17062)
3. A. Raj, S. Sahu. “Names Can Hurt: Spotting Slopsquatting Risks Caused by Package Name Hallucinations in Local Coding LLMs.” Bản tiền ấn phẩm, 2026. [arXiv:2608.23897](https://arxiv.org/abs/2608.23897)
4. L. Twist, M. Harman, H. Yannakoudakis, J. M. Zhang. “Library Hallucinations in LLM-Generated Code: A Risk Analysis Grounded in Developer Queries.” Bản tiền ấn phẩm, 2026. [arXiv:2509.22202](https://arxiv.org/abs/2509.22202)
5. B. Montaruli, L. Compagna, S. E. Ponta, D. Balzarotti. “One Detector Fits All: Robust and Adaptive Detection of Malicious Packages from PyPI to Enterprises.” Bản tiền ấn phẩm, 2025. [arXiv:2512.04338](https://arxiv.org/abs/2512.04338)
6. J. Peck, C. Nie, R. Sivaguru, C. Grumer, F. Olumofin, B. Yu, A. Nascimento, M. De Cock. “CharBot: A Simple and Effective Method for Evading DGA Classifiers.” *IEEE Access*, vol. 7, 2019. [arXiv:1905.01078](https://arxiv.org/abs/1905.01078)
7. D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, K. Rieck. “Dos and Don'ts of Machine Learning in Computer Security.” *USENIX Security Symposium*, 2022. [arXiv:2010.09470](https://arxiv.org/abs/2010.09470)
8. Python Packaging Authority. “Names and normalization.” [packaging.python.org](https://packaging.python.org/en/latest/specifications/name-normalization/)
9. PyPI Warehouse. Hàm `ultranormalize_name`. [github.com/pypi/warehouse](https://github.com/pypi/warehouse/blob/main/warehouse/migrations/versions/d18d443f89f0_ultranormalize_name_function.py)
10. npm. `validate-npm-package-name`. [github.com/npm/validate-npm-package-name](https://github.com/npm/validate-npm-package-name)
11. GitHub. “Changes and deprecation notice for npm replication APIs”, 02/2025. [github.blog](https://github.blog/changelog/2025-02-26-changes-and-deprecation-notice-for-npm-replication-apis/)
12. 0pstech/VDB. *slopsquatting-dataset*. [github.com/0pstech/slopsquatting-dataset](https://github.com/0pstech/slopsquatting-dataset)
13. Cuttalo. *DepScope hallucinations dataset*. [github.com/cuttalo/depscope-hallucinations-dataset](https://github.com/cuttalo/depscope-hallucinations-dataset)
14. Trend Micro. *slopsquatting*. [github.com/trendmicro/slopsquatting](https://github.com/trendmicro/slopsquatting)
15. J. Spracklen. *PackageHallucination* (mã nguồn và dữ liệu đi kèm [1]). [github.com/Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination)
16. A. Churilov. *slopsquatting-replication-2026* (mã nguồn đi kèm [2]). [github.com/churik5/slopsquatting-replication-2026](https://github.com/churik5/slopsquatting-replication-2026)
