# Báo cáo: Thử nghiệm sơ bộ (pilot), lựa chọn mô hình và kế hoạch bài báo

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

**Ngày:** 09/11/2026 · **Dựa trên:** [thiet-ke-du-lieu.md](thiet-ke-du-lieu.md) · **Mã nguồn:** [`experiments/pilot/`](../../experiments/pilot/) · **Số liệu gốc:** [`results.json`](../../experiments/pilot/results/results.json)

Báo cáo trả lời hai mục tiêu:

1. Có dữ liệu đầu vào thật, đo đạc được, chọn được mô hình và báo cáo định lượng.
2. Chốt kế hoạch triển khai thành một bài báo có tính mới.

Pilot dùng **dữ liệu công khai đã có sẵn** và **metadata lấy trực tiếp từ PyPI ngày 09/11/2026**, chưa tự sinh dữ liệu bằng LLM (môi trường chạy thử không có GPU và không truy cập được HuggingFace). Vì vậy các con số dưới đây là **ước lượng sơ bộ để chốt thiết kế**, chưa phải kết quả cuối của bài báo.

## 1. Tóm tắt kết quả

| # | Phát hiện | Số liệu chính | Hệ quả cho bài báo |
| --- | --- | --- | --- |
| 1 | Rất ít tên bịa đã bị đăng ký | 50/1.214 tên bịa (4,1%) có trên PyPI; chỉ 28 tên có file phát hành; 88,3% vẫn đăng ký được | Tầng 2 thiếu mẫu dương thật → phải bổ sung gói độc hại thật và mô phỏng |
| 2 | Quy tắc tên của PyPI chặn một phần tấn công | 92 tên bịa (7,6%) không đăng ký được vì trùng sau `ultranormalize` | Điều kiện 2 của "né thành công" có tác dụng thật, cần đưa vào mô hình tấn công |
| 3 | Tầng 1 (chỉ tên): mô hình đọc ký tự vượt xa đặc trưng thủ công | AUC 0,888 (LR char n-gram), 0,868 (CharCNN) so với 0,55–0,59 (RF/XGB trên 10 đặc trưng thủ công) | Loại bỏ hướng "đặc trưng thủ công từ tên" làm mô hình chính |
| 4 | Tổng quát hóa chéo LLM giảm mạnh | TPR@1%FPR: 0,548 (cùng phân phối) → 0,232 (LLM khác) | Xác nhận giả thuyết H1; phép kiểm thử chéo LLM là bắt buộc |
| 5 | Tầng 2: metadata quyết định | AUC 0,594–0,626 (chỉ tên) → 0,880 (chỉ metadata) → 0,887 (tên + metadata) | Metadata đóng góp gần như toàn bộ năng lực; tuổi gói quan trọng nhất (16%) |
| 6 | Bộ phát hiện dùng metadata rất dễ bị né | Làm giả metadata rẻ (mô tả, link repo, số bản phát hành…) không chờ ngày nào: **80,3%** né thành công; chỉ chờ 365 ngày: 17,8% | Đây là lỗ hổng chính cần khắc phục; là trục của đóng góp khoa học |
| 7 | Giả định "tự do sửa ký tự" thổi phồng mức nguy hiểm | HotFlip trên CharCNN: 94,4% né với 1 ký tự; nhưng 0% trùng tên mà LLM thật sự sinh ra | Ủng hộ RQ2; cần dữ liệu biến thể thật để đo chính xác |

## 2. Dữ liệu đầu vào

### 2.1 Nguồn và quy mô

Mọi tên được chuẩn hóa theo PEP 503 (`Vector_Cache` → `vector-cache`) trước khi gộp, giống nhau cho mọi nhóm.

| Nhóm | Nguồn | Số tên (không trùng) | Có trên PyPI | Có metadata (có file) | Vai trò |
| --- | --- | ---: | ---: | ---: | --- |
| Tên bịa (`halluc`) | 0pstech (1.081 tên PyPI; gpt-4o-mini, gemini-2.5-flash, claude-haiku-4.5), Trend Micro (14 LLM/agent × 100 câu hỏi), DepScope | 1.214 | 50 | 28 | Lớp dương tầng 1; một phần lớp dương tầng 2 |
| Tên thật do LLM gợi ý (`real_llm`) | Trend Micro: tên trong câu trả lời có trên PyPI | 291 | 291 | 291 | **Tập giữ riêng chính** để đặt ngưỡng FPR = 1% |
| Gói thật tham chiếu (`real_ref`) | Danh sách gói của thí nghiệm RAG trong Spracklen và cộng sự (2025) | 9.983 | 9.965 | 9.965 | Lớp âm khi huấn luyện |
| Gói độc hại (`malicious`) | OpenSSF malicious-packages (thư mục `osv/malicious/pypi`) | 11.992 | 270 | 124 | Lớp dương tầng 2 |
| Gói PyPI ngẫu nhiên (`random_pypi`) | Lấy mẫu 10.000 tên từ PyPI Simple API (935.693 dự án) | 10.000 | 10.000 | 9.718* | Tập phụ đo FPR; lớp âm tầng 2 |

\* Số gói có ít nhất một file phát hành. Gói PyPI mới (≤ 60 ngày tuổi) trong tập âm tầng 2: 600 gói, dùng làm tập phụ "gói mới".

**Metadata thu được (12 đặc trưng, PyPI JSON API):** tuổi gói, số ngày từ lần phát hành cuối, số bản phát hành, số file, độ dài tóm tắt, độ dài mô tả, có tác giả/email, có giấy phép, số phụ thuộc, số classifier, số project URL, có link repo (GitHub/GitLab/Bitbucket).

**Chưa thu được:** số lượt tải (pypistats và BigQuery bị chặn trong môi trường chạy thử), số sao GitHub (API bị chặn), trạng thái "verified URL" (không có trong JSON API). Ba đặc trưng này cần bổ sung ở giai đoạn chính.

### 2.2 Thống kê mô tả (E0)

**Trạng thái đăng ký của 1.214 tên bịa (ngày 09/11/2026):**

| Trạng thái | Số tên | Tỷ lệ |
| --- | ---: | ---: |
| Chưa có trên PyPI và đăng ký được | 1.072 | 88,3% |
| Chưa có trên PyPI nhưng bị chặn bởi `ultranormalize` | 92 | 7,6% |
| Có trên PyPI, có file phát hành | 28 | 2,3% |
| Có trên PyPI, không có file (giữ chỗ / đã gỡ) | 22 | 1,8% |

- Có 20 gói khớp từ khóa "research/slopsquat/placeholder/security" trong tóm tắt (ví dụ một gói ghi "Benign slopsquatting research package"), tức là một phần tên bịa đã bị **nhà nghiên cứu** giữ chỗ chứ không phải kẻ tấn công.
- Chỉ 3 tên được đăng ký **sau** ngày 0pstech ghi nhận lần đầu: chưa có bằng chứng kẻ tấn công đang săn tên bịa từ bộ dữ liệu công khai này.

**Tỷ lệ tên bịa theo LLM trong Trend Micro (tính trên lượt gợi ý):** từ 1,6% (gemini-2.5-pro) đến 13,1% (codex CLI agent). Ba chế độ agent (codex CLI 13,1%, claude CLI 7,9%, Cursor 6,2%) cao hơn mọi LLM gọi trực tiếp (1,6–5,3%). Đây là quan sát phụ đáng kiểm chứng: **coding agent bịa tên nhiều hơn LLM gọi trực tiếp**.

**Tính lặp lại giữa các LLM:**

- 0pstech: 0 tên do hơn một LLM sinh ra.
- Trend Micro (cùng 100 câu hỏi cho 14 LLM): 33/117 tên bịa (28,2%) do ít nhất 2 LLM sinh ra; trung bình 2,56 tên bịa khác nhau trên mỗi câu hỏi có ảo giác (62 câu).

Hai con số trái ngược nhau cho thấy mức lặp lại phụ thuộc mạnh vào bộ câu hỏi; cần đo trực tiếp bằng thí nghiệm hỏi lại (mục 6.2).

## 3. Phương pháp đo

### 3.1 Thiết kế định lượng

Nghiên cứu theo thiết kế **thực nghiệm so sánh** (comparative experimental design): cùng dữ liệu, cùng cách chia, cùng chỉ số, chỉ thay đổi mô hình (biến độc lập) và đầu vào (chỉ tên / chỉ metadata / cả hai).

| Thành phần | Pilot |
| --- | --- |
| Biến độc lập | Nhóm mô hình (LR, RF, XGBoost, CharCNN, CharCNN+MLP); loại đầu vào; ngân sách tấn công |
| Biến phụ thuộc | AUC-ROC, PR-AUC, TPR@1%FPR, FPR trên tập phụ, tỷ lệ né thành công |
| Kiểm soát rò rỉ | `GroupKFold` 5 phần, nhóm theo token đầu của tên (các tên `fastapi-*` nằm cùng một phần) |
| Ngưỡng | Đặt sao cho FPR = 1% trên tập **tên thật do LLM gợi ý**, giữ riêng hoàn toàn khỏi huấn luyện |
| Mất cân bằng | Trọng số lớp (`class_weight=balanced`, `scale_pos_weight`, `pos_weight`); không SMOTE, không sinh mẫu bằng sửa ký tự |
| Khoảng tin cậy | Bootstrap 500 lần, khoảng 95% (phân vị 2,5–97,5) |

### 3.2 Các thí nghiệm

| Mã | Câu hỏi | Lớp dương | Lớp âm (huấn luyện) | Tập giữ riêng |
| --- | --- | --- | --- | --- |
| E1 | Chỉ dùng tên có phân biệt được tên bịa và tên thật không? | 1.214 tên bịa | 9.769 gói tham chiếu | 291 tên thật do LLM gợi ý; 9.907 gói PyPI ngẫu nhiên |
| E1-chéo | Mô hình có tổng quát hóa sang LLM khác không? | Huấn luyện: 871 tên bịa của GPT; kiểm thử: 293 tên của Gemini/Claude | 80% / 20% gói tham chiếu | — |
| E2 | Metadata đóng góp bao nhiêu ở tầng 2? | 152 gói có metadata (28 tên bịa đã đăng ký + 124 gói độc hại) | 19.304 gói thật có metadata | 291 tên thật do LLM gợi ý; 600 gói mới ≤ 60 ngày |
| E3 | Làm giả metadata (mô phỏng) né được bao nhiêu? | 152 gói dương bị phát hiện | — | Ngưỡng FPR 1% của E2 |
| E4 | Tấn công tự do sửa ký tự so với ràng buộc thực tế? | 576 tên bịa CharCNN phát hiện được | — | Ngưỡng FPR 1% của E1 |

## 4. Kết quả

### 4.1 E1 — Tầng 1, chỉ dùng tên

| Mô hình | AUC (KTC 95%) | PR-AUC | TPR@1%FPR (CV) | TPR@1%FPR (ngưỡng trên tên thật do LLM gợi ý) | FPR trên PyPI ngẫu nhiên |
| --- | --- | ---: | --- | --- | ---: |
| LR, char n-gram 2–4 | **0,888** (0,876–0,901) | **0,725** | **0,548** (0,507–0,584) | 0,367 (0,328–0,440) | 0,11% |
| CharCNN | 0,868 (0,855–0,880) | 0,674 | 0,467 (0,434–0,505) | **0,393** (0,361–0,452) | 0,12% |
| XGBoost, 10 đặc trưng thủ công | 0,590 (0,573–0,606) | 0,152 | 0,021 | 0,064 | 2,09% |
| Random Forest, 10 đặc trưng thủ công | 0,550 (0,535–0,568) | 0,126 | 0,012 | 0,053 | 2,09% |

Nhận xét:

- Đặc trưng thủ công (độ dài, entropy, tỷ lệ nguyên âm, khoảng cách Levenshtein đến gói phổ biến, hậu tố `-utils/-sdk/-ai`…) gần như không phân biệt được (AUC ≈ 0,55–0,59). Lý do: tên bịa có hình thái giống tên thật (trung vị 12 ký tự so với 11; 64% có dấu `-` so với 52%). Kết quả này khớp nhận định của Spracklen và cộng sự (2025) rằng chỉ 13,4% tên bịa lệch tên thật 1–2 ký tự.
- Mô hình học trực tiếp từ chuỗi ký tự đạt AUC ≈ 0,87–0,89, nhưng ở mức báo nhầm 1/100 chỉ bắt được 37–55% tên bịa.
- **Cảnh báo nhiễu nguồn:** lớp dương chủ yếu từ 0pstech, lớp âm từ danh sách của Spracklen. Một phần năng lực có thể đến từ khác biệt giữa hai nguồn chứ không phải giữa "bịa" và "thật". Tập giữ riêng (tên thật trong câu trả lời Trend Micro) cho TPR thấp hơn (0,37–0,39 so với 0,47–0,55), phù hợp với giả thuyết nhiễu này. Ở giai đoạn chính, tên thật và tên bịa phải lấy **từ cùng câu trả lời của cùng LLM** như thiết kế ban đầu.

### 4.2 E1-chéo — Kiểm thử chéo giữa các LLM

| Mô hình | AUC trên tên bịa của LLM khác | TPR@1%FPR (KTC 95%) |
| --- | ---: | --- |
| LR, char n-gram | 0,755 | 0,232 (0,160–0,283) |
| CharCNN | 0,746 | 0,160 (0,119–0,263) |
| XGBoost, đặc trưng thủ công | 0,602 | 0,027 |
| Random Forest, đặc trưng thủ công | 0,578 | 0,020 |

TPR@1%FPR giảm từ 0,548 xuống 0,232 với LR (giảm 58%). Bộ phát hiện chỉ dùng tên **không tổng quát hóa** tốt giữa các họ LLM.

### 4.3 E2 — Tầng 2, đóng góp của metadata

| Mô hình [đầu vào] | AUC (KTC 95%) | PR-AUC | TPR@1%FPR (CV) | TPR@1%FPR (ngưỡng trên tên thật do LLM gợi ý) | FPR trên gói mới ≤ 60 ngày |
| --- | --- | ---: | --- | --- | ---: |
| LR char n-gram [tên] | 0,626 (0,582–0,673) | 0,085 | 0,178 | 0,086 | 0,19% |
| XGBoost [tên] | 0,594 (0,544–0,640) | 0,017 | 0,046 | 0,112 | 0,19% |
| XGBoost [metadata] | 0,880 (0,851–0,905) | 0,359 | 0,395 | 0,368 | 1,71% |
| XGBoost [tên + metadata] | **0,887** (0,860–0,910) | 0,359 | 0,395 | **0,408** (0,316–0,507) | 4,00% |
| Random Forest [tên + metadata] | 0,876 (0,841–0,905) | **0,382** | **0,428** | 0,382 (0,303–0,507) | **0,38%** |
| CharCNN + MLP [tên + metadata] | 0,794 (0,755–0,833) | 0,077 | 0,145 | 0,257 | 10,48% |

**Mức quan trọng đặc trưng (XGBoost, tên + metadata), 5 đặc trưng đầu:** tuổi gói 16,0%; số phụ thuộc 6,3%; có link repo 5,6%; số bản phát hành 5,2%; số ngày từ lần phát hành cuối 5,1%.

Nhận xét:

- Ở tầng 2, metadata nâng AUC từ ≈ 0,6 lên ≈ 0,88. Thêm tên vào metadata không cải thiện có ý nghĩa thống kê (khoảng tin cậy chồng lấn).
- XGBoost báo nhầm 4% gói mới ở ngưỡng 1% → đúng rủi ro "báo nhầm mọi gói mới" mà thiết kế dữ liệu đã dự báo. Random Forest giữ FPR gói mới ở 0,38%.
- Mạng nơ-ron kết hợp kém hơn rõ rệt khi chỉ có 152 mẫu dương.
- 124/152 mẫu dương là gói độc hại OpenSSF, không phải tên bịa. Do đó E2 hiện chủ yếu đo "gói độc hại so với gói thật".

### 4.4 E3 — Làm giả metadata (chỉ mô phỏng)

Kẻ tấn công nâng các đặc trưng rẻ (tóm tắt, mô tả, tác giả, giấy phép, phụ thuộc, classifier, project URL, link repo, số bản phát hành, số file, ngày phát hành cuối) lên mức trung vị của tên thật do LLM gợi ý, rồi chờ thêm *d* ngày để tăng tuổi gói. Bộ phát hiện: XGBoost [tên + metadata].

| Ngân sách | Tỷ lệ né thành công |
| --- | ---: |
| Chỉ chờ 365 ngày, không sửa metadata | 17,8% |
| Sửa metadata rẻ, chờ 0 ngày | **80,3%** |
| Sửa metadata rẻ + chờ 7 ngày | 82,2% |
| Sửa metadata rẻ + chờ 30 ngày | 84,2% |
| Sửa metadata rẻ + chờ 90 ngày | 86,2% |
| Sửa metadata rẻ + chờ 365 ngày | 87,5% |

Kết luận: **bộ phát hiện tầng 2 hiện tại gần như vô hiệu trước kẻ tấn công biết làm giả metadata rẻ**. Đặc trưng khó làm giả nhất (tuổi gói) chỉ đóng góp 17,8% khả năng né khi đứng riêng. Đây là bằng chứng định lượng đầu tiên cho câu hỏi nghiên cứu 1 và là lý do cần bộ phát hiện bền vững.

*Hạn chế:* mục tiêu tấn công là 152 mẫu dương mà mô hình phát hiện được khi huấn luyện trên toàn bộ dữ liệu (trong mẫu). Giai đoạn chính phải dùng mẫu kiểm thử ngoài mẫu.

### 4.5 E4 — Tự do sửa ký tự so với ràng buộc thực tế

Tấn công HotFlip (dùng gradient theo embedding ký tự của CharCNN, thay tối đa *k* ký tự) trên 576 tên bịa mà CharCNN phát hiện được ở ngưỡng FPR 1%.

| *k* ký tự | Né (tự do) | Né + tên hợp lệ | Né + đăng ký được trên PyPI | Né + đăng ký được + trùng tên LLM thật sự sinh |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 94,4% | 94,4% | 93,9% | **0,0%** |
| 2 | 100% | 100% | 99,5% | **0,0%** |
| 3 | 100% | 100% | 99,5% | **0,0%** |

Kẻ tấn công tự do sửa ký tự gần như luôn thắng, nhưng không tên nào trong số đó trùng với tên mà LLM đã sinh ra trong dữ liệu. Nếu kẻ tấn công phải đăng ký đúng tên LLM gợi ý, mức nguy hiểm thực tế thấp hơn nhiều so với giả định của các nghiên cứu trước. Đây là tín hiệu ủng hộ câu hỏi nghiên cứu 2.

*Hạn chế:* tập "tên LLM thật sự sinh" trong pilot chỉ gồm 1.214 tên bịa, không phải biến thể hỏi lại theo từng câu hỏi. Con số 0% là cận dưới; đo đúng cần bộ biến thể ở mục 6.2.

## 5. Lựa chọn mô hình

Tiêu chí (theo thiết kế dữ liệu): TPR@1%FPR trên tập giữ riêng, độ ổn định khi kiểm thử chéo LLM, FPR trên gói mới, có gradient cho mốc tấn công tự do.

| Vai trò | Mô hình chọn | Lý do định lượng |
| --- | --- | --- |
| Tầng 1, mô hình chính (chỉ tên) | **LR trên char n-gram 2–4** | AUC 0,888, TPR@1%FPR 0,548, tốt nhất khi kiểm thử chéo (0,232); huấn luyện tính bằng giây |
| Tầng 1, mô hình có gradient | **CharCNN** | Kém LR không đáng kể (AUC 0,868; TPR trên tập giữ riêng 0,393 còn cao hơn); bắt buộc cho mốc Faster-GCG/HotFlip |
| Tầng 2, mô hình chính (tên + metadata) | **Random Forest** | TPR@1%FPR 0,428 (CV), FPR trên gói mới chỉ 0,38% so với 4% của XGBoost |
| Tầng 2, mô hình đối chứng | **XGBoost** | AUC cao nhất (0,887), có ràng buộc đơn điệu (monotone constraint) phục vụ phần phòng thủ |
| Loại bỏ | Đặc trưng thủ công từ tên; CharCNN+MLP ở tầng 2 | AUC ≈ 0,55–0,59; mạng kết hợp kém (0,794) và FPR gói mới 10,5% |
| Thử thêm ở giai đoạn chính | fastText / CodeBERT trên tên tách từ | Chưa thử trong pilot (không tải được mô hình huấn luyện sẵn) |

## 6. Giải pháp đề xuất và tính mới

### 6.1 Vị trí so với công trình liên quan

Khảo sát bổ sung trong lần này cho thấy hai công trình cần đặt cạnh đề tài:

- **MeMPtec** (Halder và cộng sự, WWW 2024) đã chia đặc trưng metadata thành *dễ thao túng* và *khó thao túng*, và đánh giá khả năng chống tấn công cho bài toán gói độc hại nói chung.
- **Montaruli và cộng sự** (ACSAC 2025) đã huấn luyện đối kháng bộ phát hiện gói độc hại PyPI với các ngưỡng FPR khác nhau, nhưng tấn công bằng biến đổi mã nguồn, không phải tên và metadata.
- **ConfuGuard** (Jiang và cộng sự, ICSE 2026) dùng metadata để giảm báo nhầm cho tấn công nhầm tên (typosquatting), không có mô hình kẻ tấn công.
- **Raj và Sahu** (2026) có bộ phát hiện hai tầng cho slopsquatting nhưng chưa thử trước kẻ tấn công.
- **Churilov** (2026) đo tên bịa chung giữa 5 LLM và kiểm tra khả năng đăng ký, nhưng không xây bộ phát hiện.

Vì MeMPtec đã có ý tưởng "đặc trưng dễ/khó thao túng", đề tài **không** nên nhận đóng góp ở mức "làm giả metadata". Tính mới cần đặt vào **mô hình kẻ tấn công riêng của slopsquatting**: kẻ tấn công bị ràng buộc bởi (i) tên mà LLM thật sự gợi ý, (ii) quy tắc đăng ký của PyPI, (iii) chi phí làm giả metadata có định giá, và giá trị tấn công được đo bằng **tần suất LLM gợi ý** tên đó chứ không phải tỷ lệ mẫu.

### 6.2 Giải pháp đề xuất

**(a) Dữ liệu biến thể theo câu hỏi (đóng góp dữ liệu chính).** Với 500 tên bịa, hỏi lại câu hỏi gốc 10 lần trên 2 LLM; lưu mọi tên và tần suất. Đây là tập hợp hành động duy nhất mà kẻ tấn công thực tế có thể chọn.

**(b) Thước đo "tỷ lệ né có trọng số tần suất" (đóng góp phương pháp).**

> RER(B) = Σ<sub>v ∈ V</sub> f(v) · 1[v đăng ký được] · 1[D(v, m′) = 0 với chi phí(m′) ≤ B] / Σ<sub>v ∈ V</sub> f(v)

trong đó V là tập biến thể LLM sinh, f(v) là tần suất, m′ là metadata sau khi làm giả với ngân sách B. Báo cáo RER theo đường ngân sách (ngày chờ, USD).

**(c) Bộ phát hiện bền vững theo chi phí (đóng góp phòng thủ).** Pilot cho thấy đặc trưng rẻ chi phối quyết định. Ba cách phòng thủ sẽ được so sánh trên cùng RER:

1. **Chỉ dùng đặc trưng đắt** (tuổi gói, lượt tải thật theo thời gian, URL được PyPI xác minh / Trusted Publishing) cộng với tên.
2. **Ràng buộc đơn điệu** (XGBoost monotone constraints): điểm nghi ngờ không được giảm khi đặc trưng rẻ tăng vô hạn, buộc mô hình dựa vào đặc trưng đắt.
3. **Huấn luyện đối kháng** bằng biến thể thật và metadata giả theo ngân sách.

Mỗi cách báo cáo đánh đổi: RER giảm bao nhiêu, FPR tăng bao nhiêu (đặc biệt trên gói mới).

**(d) Đặc trưng ngữ cảnh mà kẻ tấn công không điều khiển được (ý tưởng mở rộng).** Mức đồng thuận giữa nhiều LLM (bao nhiêu LLM gợi ý cùng tên cho cùng câu hỏi) và việc gói có được dự án thật nào phụ thuộc hay không. Kẻ tấn công không thay đổi được các tín hiệu này bằng cách sửa metadata của gói.

### 6.3 Giả thuyết kiểm định

| Giả thuyết | Bằng chứng pilot | Kiểm định ở giai đoạn chính |
| --- | --- | --- |
| H1: Bộ phát hiện chỉ dùng tên giảm TPR@1%FPR có ý nghĩa khi kiểm thử chéo LLM | 0,548 → 0,232 | Bootstrap theo cặp, so khoảng tin cậy; McNemar trên quyết định tại ngưỡng |
| H2: Làm giả metadata rẻ đạt RER > 50% với bộ phát hiện tầng 2 chuẩn | 80,3% (mức 0 ngày) | Đường RER theo ngân sách, ngoài mẫu |
| H3: RER thực tế (ràng buộc biến thể LLM + đăng ký) thấp hơn tỷ lệ né khi tự do sửa ký tự | 0% so với 94,4% | So sánh trên cùng tập mục tiêu, bộ biến thể thật |
| H4: Phòng thủ theo chi phí giảm RER ít nhất một nửa với FPR gói mới ≤ 2% | Chưa có | So sánh 3 cách phòng thủ ở mục 6.2(c) |

## 7. Kế hoạch triển khai bài báo

### 7.1 Cỡ mẫu cần thiết (tính từ pilot)

Ước lượng tỷ lệ *p* với sai số ±*e* ở độ tin cậy 95%: *n* = 1,96² · *p*(1 − *p*) / *e*².

| Đại lượng | Pilot | Cần | Lý do |
| --- | ---: | ---: | --- |
| Tên thật do LLM gợi ý (để đặt ngưỡng FPR = 1%, ±0,5%) | 291 | **≥ 1.521** | Với 291 mẫu, ngưỡng 1% chỉ dựa trên 3 mẫu |
| Mẫu dương tầng 2 (TPR ≈ 0,5, ±3%) | 152 | **≥ 1.067** | Khoảng tin cậy pilot rộng ±10 điểm % |
| Gói PyPI ngẫu nhiên (FPR = 0,1%, ±0,05%) | 10.000 | ≥ 15.352 | Chỉ khi muốn báo mức 1/1.000 |
| Tên bịa để kiểm thử chéo mỗi LLM | 293 | ≥ 500 | Như thiết kế dữ liệu |

### 7.2 Lộ trình

| Giai đoạn | Thời gian | Việc | Kết quả đầu ra |
| --- | --- | --- | --- |
| 1. Sinh dữ liệu | 11–12/2026 | 2 LLM (1 thương mại, 1 chạy cục bộ trên GPU, ví dụ Qwen2.5-Coder-7B); 18.033 câu hỏi Spracklen + bộ câu hỏi mới; tách tên thật/tên bịa **trong cùng câu trả lời**; bổ sung lượt tải (BigQuery), sao GitHub, URL được xác minh | ≥ 4.000 tên bịa, ≥ 1.500 tên thật giữ riêng |
| 2. Bộ biến thể | 12/2026 | 500 tên × 10 lần hỏi lại × 2 LLM; kiểm tra đăng ký bằng `ultranormalize` | Bộ biến thể có tần suất (đóng góp dữ liệu) |
| 3. Bộ phát hiện cơ sở | 01/2027 | Chạy lại E1, E2 với dữ liệu đầy đủ; thêm fastText/CodeBERT | Bảng chọn mô hình cuối |
| 4. Tấn công | 01–02/2027 | RER theo ngân sách (thực tế) và Faster-GCG/HotFlip (mốc tự do); bảng chi phí làm giả có nguồn trích dẫn | Kết quả H2, H3 |
| 5. Phòng thủ | 02–03/2027 | 3 cách phòng thủ ở mục 6.2(c); đo RER và FPR | Kết quả H4 |
| 6. Viết bài, công bố có trách nhiệm | 03–04/2027 | Gửi danh sách tên cho PyPI Security trước; viết bài | Bản thảo |

**Nơi gửi bài phù hợp:** ACM AISec (workshop của CCS), ACSAC, hoặc tạp chí *Computers & Security*. Montaruli và cộng sự đã đăng hướng tương tự ở ACSAC 2025.

### 7.3 Cấu trúc bài báo dự kiến

1. Giới thiệu: slopsquatting, khoảng trống (chưa có bộ phát hiện nào được thử trước kẻ tấn công thực tế).
2. Mô hình kẻ tấn công: ba điều kiện né, thước đo RER.
3. Dữ liệu: bộ biến thể theo câu hỏi, bộ tên nhầm.
4. Bộ phát hiện hai tầng và lựa chọn mô hình.
5. Đánh giá tấn công: RER theo ngân sách, so với tự do sửa ký tự.
6. Phòng thủ theo chi phí và đánh đổi FPR.
7. Thảo luận, đạo đức, giới hạn.

### 7.4 Rủi ro và phương án

| Rủi ro | Dấu hiệu từ pilot | Phương án |
| --- | --- | --- |
| Quá ít tên bịa đã bị đăng ký thật | 28/1.214 có file | Dùng gói độc hại OpenSSF làm lớp dương bổ sung; mô phỏng metadata của gói slopsquat theo phân phối gói độc hại mới |
| Nhiễu nguồn ở tầng 1 | TPR giảm khi đổi tập âm | Lấy tên thật và tên bịa từ cùng câu trả lời; báo kết quả theo từng nguồn |
| LLM lặp lại một tên duy nhất | 0pstech: 0 tên chung; Trend Micro: 28% | Nếu biến thể rất ít, chuyển trọng tâm sang H3 ("tấn công né tránh thực tế khó hơn giả định") |
| Thiếu lượt tải và sao GitHub | Bị chặn trong môi trường chạy thử | Dùng BigQuery `bigquery-public-data.pypi` và token GitHub ở môi trường chính |

## 8. Giới hạn của pilot

- Không tự sinh dữ liệu bằng LLM; dùng bộ dữ liệu công khai nên tên thật và tên bịa không cùng nguồn (gây nhiễu ở E1).
- Tầng 2 chỉ có 152 mẫu dương, phần lớn là gói độc hại, không phải gói slopsquat.
- E3 tấn công trên mẫu trong tập huấn luyện; E4 dùng tập tên bịa thay cho bộ biến thể.
- Thiếu ba đặc trưng metadata quan trọng (lượt tải, sao GitHub, URL được xác minh).
- Không đăng ký gói nào lên PyPI, không làm giả metadata thật. Danh sách tên không được đưa vào kho mã; chỉ công bố số liệu tổng hợp.

## 9. Tái lập

Bộ dữ liệu ngoài (0pstech, Trend Micro, DepScope, Spracklen, OpenSSF) được clone vào thư mục `ext/`; xem [`experiments/pilot/README.md`](../../experiments/pilot/README.md).

## Tài liệu tham khảo bổ sung

Ngoài các tài liệu trong [thiet-ke-du-lieu.md](thiet-ke-du-lieu.md):

- Halder, S., và cộng sự (2024). *Malicious Package Detection using Metadata Information*. Proceedings of the ACM Web Conference 2024. [Consensus](https://consensus.app/papers/details/3aec62ed53ae57a08144e133179e8727/)
- Jiang, W.-X., và cộng sự (2026). *ConfuGuard: Using Metadata to Detect Active and Stealthy Package Confusion Attacks Accurately and at Scale*. ICSE 2026. [Consensus](https://consensus.app/papers/details/bc2c3eb6c05e538892a955fb2a29634d/)
- Montaruli, B., và cộng sự (2025). *One Detector Fits All: Robust and Adaptive Detection of Malicious Packages from PyPI to Enterprises*. ACSAC 2025. [Consensus](https://consensus.app/papers/details/217376daa273586d96a6b7580d94b488/)
- Taylor, M., và cộng sự (2020). *Defending Against Package Typosquatting* (TypoGard). [Consensus](https://consensus.app/papers/details/30c7b8fefd3857e182bfe9dec284d4b5/)
- Ebrahimi, J., Rao, A., Lowd, D., Dou, D. (2018). *HotFlip: White-Box Adversarial Examples for Text Classification*. ACL. [arXiv:1712.06751](https://arxiv.org/abs/1712.06751)
