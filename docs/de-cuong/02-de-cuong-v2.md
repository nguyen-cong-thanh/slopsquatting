# Đề cương luận văn thạc sĩ (bản 2)

> Chuyển sang markdown từ `de_cuong_v2.docx` (Google Drive, sửa lần cuối 10/09/2026).

**Chuyên ngành:** An toàn thông tin

## Tên đề tài

**Phương án chính:** “Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn”

**Phương án tên tiếng Anh:** “Adversarially Robust Detection of Slopsquatting Attacks in LLM-Generated Code: A Multi-Threat-Model and Cross-Ecosystem Study”

## I. Mục tiêu nghiên cứu

Xây dựng và đánh giá một cơ chế phát hiện tấn công Slopsquatting trong mã nguồn được sinh bởi mô hình ngôn ngữ lớn, có khả năng duy trì hiệu quả phát hiện trước nhiều dạng đối tượng tấn công chủ động điều chỉnh tên gói để né tránh (adversarial evasion) — bao gồm cả tấn công có tri thức nội bộ hệ thống (white-box) và tấn công thực tế không có tri thức nội bộ (black-box) — thay vì chỉ đo lường tỷ lệ ảo giác hoặc phát hiện tĩnh như các nghiên cứu hiện có. Nghiên cứu đồng thời công bố một bộ dữ liệu benchmark mở nhằm tạo cơ sở so sánh cho các nghiên cứu tiếp theo trong lĩnh vực này.

## II. Đối tượng và phạm vi nghiên cứu

**Đối tượng nghiên cứu:** tên gói phần mềm do mô hình ngôn ngữ lớn gợi ý trong quá trình sinh mã, tập trung vào hệ sinh thái PyPI (Python), mở rộng đồng thời sang npm (JavaScript) nhằm đánh giá khả năng tổng quát hóa liên hệ sinh thái (cross-ecosystem generalization) của bộ phát hiện.

**Phạm vi nghiên cứu:** thực hiện trong môi trường mô phỏng có kiểm soát; không đăng ký bất kỳ tên gói nào lên registry công khai trong suốt quá trình thử nghiệm, nhằm bảo đảm đạo đức nghiên cứu.

## III. Phương pháp nghiên cứu

### 3.1. Giai đoạn 1: Xây dựng dữ liệu và bộ phát hiện cơ sở

- Thu thập tên gói do mô hình ngôn ngữ lớn gợi ý, bằng cách prompt bốn mô hình ngôn ngữ lớn đa nguồn: GPT-4o, Claude Sonnet (thương mại, closed-source, hai nhà cung cấp khác nhau), CodeLlama-13B, DeepSeek-Coder-7B (mã nguồn mở, code-specialized) — nhằm tránh thiên lệch khi chỉ dựa vào một nguồn LLM duy nhất.
- Đối chiếu kết quả với danh sách gói thật trên PyPI và npm qua API công khai để xác định các tên gói bị ảo giác.
- Trích xuất đặc trưng của tên gói: chuỗi n-gram ký tự, khoảng cách Levenshtein tới các gói phổ biến, và biểu diễn embedding.
- Huấn luyện bộ phát hiện cơ sở D0 (1D-CNN trên chuỗi ký tự), có đối chiếu với Random Forest và XGBoost.
- Đánh giá bằng Precision, Recall, F1-score, AUC-ROC và FPR. Mục tiêu tham chiếu: FPR ≤ 1–5% trên tập gói thật; Precision/Recall/F1 tương đương hoặc vượt baseline ConfuGuard/TypoSmart (P≈1.00, F1≈0.93–0.95).

### 3.2. Mô hình mối đe dọa (Threat Model)

Nghiên cứu hình thức hóa mối đe dọa theo bốn trục, dựa trên taxonomy NIST AI.100-2 (2025) và khung Realizability của Pierazzi et al.:

| Trục | Nội dung |
| --- | --- |
| Attacker Knowledge | White-box (ứng với Faster-GCG): attacker có đầy đủ tri thức kiến trúc và trọng số D0. Black-box/query-based (ứng với LLM-guided): attacker chỉ quan sát nhãn đầu ra. |
| Attacker Capability | Giới hạn ở test-time evasion (can thiệp tại thời điểm sử dụng); không bao gồm data poisoning lên tập huấn luyện D0. |
| Attacker Goal | Targeted evasion: khiến D0/D′ phân loại nhầm tên gói ảo giác thành hợp lệ. |
| Realizability | Mọi tấn công bị ràng buộc trong problem-space (Pierazzi et al.): kết quả cuối cùng luôn phải là tên gói hợp lệ, có thể đăng ký thực tế trên registry — không chấp nhận tấn công feature-space phi thực tế. |

Đề tài đối chiếu hai threat model tương ứng hai kỹ thuật tấn công ở Giai đoạn 2: white-box (Faster-GCG) — kịch bản đánh giá cận trên (worst-case) chuẩn trong nghiên cứu robustness, không phải giả định về năng lực attacker thực tế; và black-box/query-based (LLM-guided) — phản ánh sát hơn kịch bản tấn công thực tế, khi attacker chỉ quan sát được kết quả đầu ra.

### 3.3. Giai đoạn 2: Đánh giá và tăng cường độ bền vững adversarial

**(a) Tấn công gradient-based — Faster-GCG (white-box).** Áp dụng Faster-GCG (Li et al., 2024) — bản cải tiến hiệu quả của Greedy Coordinate Gradient (GCG, Zou et al., 2023), vốn là hậu duệ của HotFlip (Ebrahimi et al., 2018) — điều chỉnh từ cấp độ token sang cấp độ ký tự phù hợp với tên gói ngắn.

| Hạn chế của GCG gốc | Giải pháp của Faster-GCG |
| --- | --- |
| Xếp hạng ứng viên theo gradient không chính xác | Distance regularization — phạt thay thế cách xa trong không gian embedding |
| Lấy mẫu đều ngẫu nhiên, lãng phí ngân sách | Temperature-controlled sampling — ưu tiên ứng viên chất lượng cao |
| ~6% biến thể bị đánh giá lặp lại | Visited-suffix marking — tránh đánh giá lại các biến thể đã thử |

Faster-GCG đạt hiệu quả lấy mẫu gấp 8 lần và giảm thời gian chạy thực tế khoảng 7 lần so với GCG chuẩn, đồng thời đạt tỷ lệ thành công cao hơn trong cùng ngân sách hạn chế — yếu tố quan trọng cho tính khả thi thời gian của luận văn.

**(b) Tấn công sinh bởi LLM — LLM-guided generation (black-box).** Sử dụng một LLM độc lập (không truy cập nội bộ D0) làm bộ sinh biến thể — prompt LLM tạo tên gói biến đổi từ tên gốc theo naming convention của registry, sau đó dùng nhãn đầu ra của D0 để lọc biến thể né tránh thành công.

**Ràng buộc chung (problem-space realizability):** tên gói sau nhiễu phải hợp lệ theo quy tắc đặt tên registry, chưa tồn tại thật, và đủ hợp lý để một LLM có khả năng gợi ý trong thực tế.

**Các bước thực nghiệm:**

- Đo Attack Success Rate (ASR) và ngân sách nhiễu tối thiểu: ASR = (số mẫu D0 phát hiện đúng ban đầu, sau nhiễu bị phân loại sai) / (tổng số mẫu D0 phát hiện đúng ban đầu).
- Adversarial training: huấn luyện lại D0 bằng tập mẫu tấn công kết hợp cả hai kỹ thuật (Faster-GCG + LLM-guided) → D′, nhằm tăng khả năng tổng quát hóa trước nhiều loại attacker. Mục tiêu: ASR của D′ giảm xuống dưới 30% (tốt) hoặc dưới 10% (rất tốt).
- Đánh giá lại D′ bằng cả hai kỹ thuật, đo đánh đổi FPR trên tập gói thật — mục tiêu FPR không tăng quá +5 điểm % so với D0.

### 3.4. Công cụ và môi trường thực hiện

- **Ngôn ngữ/framework:** Python, PyTorch hoặc TensorFlow.
- **Nguồn dữ liệu đối chiếu:** API công khai PyPI và npm.
- **Môi trường triển khai thử nghiệm:** middleware/plugin tại tầng API Gateway (Kong Gateway), đánh giá độ trễ và khả năng triển khai thực tế.

### 3.5. Kế hoạch mở rộng

Trong trường hợp quỹ thời gian cho phép, nghiên cứu mở rộng theo hai hướng sau; nếu không đủ thời gian triển khai đầy đủ, các hướng này được trình bày như định hướng phát triển trong phần Kết luận:

- **Certified defense:** khảo sát và thử nghiệm randomized smoothing cho văn bản (theo hướng Text-CRS, Zeng et al.), cho phép chứng minh cận dưới về độ bền vững (certified robustness radius) thay vì chỉ báo cáo tỷ lệ thực nghiệm.
- **Đánh giá transferability (gray-box):** tấn công tạo trên một mô hình surrogate rồi kiểm tra hiệu quả trên D0/D′ thật, nhằm trả lời câu hỏi thực tiễn khi attacker chỉ biết loại kiến trúc (CNN character-level) mà không biết chính xác trọng số.

## IV. Kết quả dự kiến

- Bộ dữ liệu tên gói ảo giác tổng hợp từ bốn LLM (GPT-4o, Claude Sonnet, CodeLlama-13B, DeepSeek-Coder-7B), đối chiếu registry trên cả PyPI và npm.
- **AdvSlop-Bench:** bộ dữ liệu benchmark mở, công bố công khai (GitHub/Hugging Face): (1) tập tên gói hallucinated; (2) tập adversarial examples từ cả hai kỹ thuật tấn công kèm nhãn thành công/thất bại và ngân sách nhiễu; (3) D0, D′ cùng script tái lập thực nghiệm. Đây là benchmark đầu tiên phục vụ nghiên cứu adversarial robustness cho bài toán slopsquatting detection.
- Bộ phát hiện D0 và D′, cùng bộ chỉ số đánh giá so sánh trên cả hai threat model (white-box và black-box).
- Số liệu định lượng về mức độ dễ bị tấn công của các bộ phát hiện hiện nay trước tấn công Slopsquatting có chủ đích, phân tách theo từng kỹ thuật tấn công.
- Phân tích khả năng tổng quát hóa liên hệ sinh thái (PyPI → npm) của bộ phát hiện.
- Đề xuất kiến trúc triển khai thực tế tại tầng API Gateway hoặc quy trình tích hợp liên tục (CI/CD), phù hợp với bối cảnh phát triển phần mềm doanh nghiệp.

## Tài liệu tham khảo chính

1. Ebrahimi et al. — HotFlip: White-Box Adversarial Examples for Text Classification, ACL 2018.
2. Zou et al. — Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG), 2023.
3. Li et al. — Faster-GCG: Efficient Discrete Optimization Jailbreak Attacks against Aligned Large Language Models, arXiv 2410.15362, 2024.
4. NIST AI.100-2 (2025) — Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations.
5. Pierazzi et al. — Intriguing Properties of Adversarial ML Attacks in the Problem Space, ACM TOPS.
6. Zeng et al. — Text-CRS: A Generalized Certified Robustness Framework against Textual Adversarial Attacks.
7. Spracklen et al. — We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs, USENIX Security 2025.
