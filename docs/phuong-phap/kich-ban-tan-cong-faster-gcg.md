# Kịch bản tấn công white-box: Faster-GCG

> Chuyển sang markdown từ `Kich_ban_tan_cong_FasterGCG.docx` (Google Drive, sửa lần cuối 10/09/2026). Hình 1 trong bản gốc là sơ đồ kiến trúc, xem bản vẽ lại ở [kien-truc-phuong-phap.md](kien-truc-phuong-phap.md).

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

## 1. Threat Model — tóm tắt

Kịch bản dưới đây là kịch bản tấn công chính của đề tài, chạy dưới threat model white-box: kẻ tấn công có bản sao đầy đủ mô hình phát hiện cơ sở D0 (kiến trúc, trọng số, cách tiền xử lý), thực hiện tấn công né tránh có chủ đích tại thời điểm sử dụng (test-time evasion), không can thiệp vào quá trình huấn luyện D0. Toàn bộ quá trình bị ràng buộc trong problem-space: mọi tên gói sinh ra phải hợp lệ theo quy tắc đặt tên của registry (PyPI/npm) và có thể đăng ký thực tế — không phải một cấu trúc lý tưởng hóa chỉ tồn tại trong không gian đặc trưng.

Kỹ thuật tấn công được chọn là Faster-GCG (Li et al., 2024) — bản cải tiến hiệu quả của GCG (Zou et al., 2023), vốn là hậu duệ trực tiếp của HotFlip (Ebrahimi et al., 2018). Faster-GCG bắt buộc phải truy cập gradient của D0, nên chỉ vận hành được trong điều kiện white-box; đây là kịch bản đánh giá cận trên (worst-case) chuẩn trong nghiên cứu robustness, không phải giả định về năng lực attacker thực tế ngoài đời.

## 2. Sơ đồ vị trí trong kiến trúc bài toán

Sơ đồ bám theo đúng luồng dữ liệu của đề cương: Giai đoạn 1 xây dựng D0 từ tên gói bị bốn LLM hallucinate một cách tự nhiên; Giai đoạn 2 tách hai nhánh tấn công có threat model khác nhau — Faster-GCG (white-box, đường liền, đọc trực tiếp trọng số và gradient của D0) và LLM-guided (black-box, đường đứt, chỉ trao đổi qua truy vấn/nhãn) — cả hai gộp lại thành một tập adversarial duy nhất để huấn luyện D′, bộ phát hiện bền vững, sản phẩm cuối cùng.

*Hình 1. Vị trí của Faster-GCG (nhánh white-box) và LLM-guided (nhánh black-box) trong kiến trúc hai giai đoạn của đề tài.* Xem [kien-truc-phuong-phap.md](kien-truc-phuong-phap.md).

## 3. Kịch bản tấn công chi tiết (8 bước)

| Bước | Hành động | Ghi chú |
| --- | --- | --- |
| 0. Điều kiện tiên quyết | Attacker có bản sao đầy đủ D0 (mã nguồn mở / rò rỉ / reverse engineering): biết kiến trúc 1D-CNN, trọng số, cách tiền xử lý (tokenize ký tự, embedding). | Điều kiện Attacker Knowledge — white-box. |
| 1. Chọn mục tiêu | Lấy một tên gói từ tập dữ liệu ảo giác thu được ở Giai đoạn 1 (do LLM tự nhiên hallucinate khi làm tác vụ coding thông thường) mà D0 đã phát hiện đúng là khả nghi. Ví dụ: `torch-utilzz`. | Xem bảng phân biệt (A)/(B) bên dưới. |
| 2. Tính gradient tại mọi vị trí | Đưa tên gói vào D0, tính gradient của loss theo từng vị trí ký tự đồng thời trong lớp embedding (khác HotFlip: không xét tuần tự từng vị trí). | Bước đặc trưng của họ GCG. |
| 3. Lấy mẫu ứng viên có trọng số | Chọn tập ứng viên thay thế theo temperature-controlled sampling (ưu tiên ứng viên gradient tốt), áp distance regularization để loại thay thế cách xa trong không gian embedding. | Cải tiến riêng của Faster-GCG so với GCG gốc. |
| 4. Đánh giá song song & chọn tốt nhất | Đánh giá loss thực tế của các ứng viên đã lọc, bỏ qua ứng viên đã thử trước đó (visited-suffix marking), chọn thay thế tốt nhất. Ví dụ: `torch-utilzz` → `torch-utilz2`. | Nhanh hơn GCG chuẩn khoảng 7–8 lần. |
| 5. Kiểm tra ràng buộc problem-space | Tên gói mới phải: (a) hợp lệ theo quy tắc đặt tên PyPI/npm, và (b) chưa tồn tại thật trên registry. | Bắt buộc — đảm bảo tính thực tế, tránh feature-space vô nghĩa. |
| 6. Lặp lại | Nếu D0 vẫn phát hiện đúng, lặp lại bước 2–5, giới hạn trong một ngân sách nhiễu (ví dụ tối đa 2–3 ký tự thay đổi). | Dừng khi thành công hoặc hết ngân sách. |
| 7. Ghi nhận kết quả | D0 phân loại sai → tính là tấn công thành công, đưa vào ASR. D0 vẫn đúng → thất bại. | Công thức ASR chỉ tính trên tập D0 đã đúng ban đầu. |

**Mục tiêu cuối cùng của attacker (Attacker Goal):** khiến developer vô tình cài đặt gói nguy hiểm mà attacker đã đăng ký thật trên registry với cái tên đã né tránh được cả D0 lẫn D′, không bị cảnh báo.

## 4. Phân biệt: Ảo giác tự nhiên và tấn công LLM-guided

Đây là điểm dễ gây hiểu nhầm logic (“dùng ảo giác để tấn công ảo giác”) nên cần làm rõ khi trình bày: (A) là hiện tượng tự nhiên, không chủ đích, đóng vai trò nguồn dữ liệu ở Giai đoạn 1; (B) là một kỹ thuật tấn công có chủ đích ở Giai đoạn 2, trong đó LLM chỉ đóng vai trò công cụ sinh biến thể có kiểm soát, không hề bị ảo giác khi thực hiện đúng yêu cầu của attacker.

|  | (A) Ảo giác tự nhiên | (B) Tấn công LLM-guided |
| --- | --- | --- |
| Chủ đích | Không chủ đích (lỗi mô hình) | Có chủ đích (attacker yêu cầu rõ ràng) |
| Vai trò trong đề tài | Nguồn dữ liệu Giai đoạn 1 (huấn luyện D0) | Kỹ thuật tấn công Giai đoạn 2 (đánh giá D0/D′) |
| LLM đóng vai | “Nạn nhân” bị lỗi | Công cụ sinh biến thể có kiểm soát |
| Input | Tác vụ coding thông thường | Prompt tấn công cụ thể, có mục tiêu né detector |

## 5. Định nghĩa ASR liên quan trực tiếp threat model

ASR (Attack Success Rate) = (số mẫu ban đầu D0 phát hiện đúng, sau khi nhiễu bị phân loại sai) / (tổng số mẫu ban đầu D0 phát hiện đúng). Công thức chỉ tính trên tập D0 đã đúng ban đầu — tấn công vào mẫu D0 vốn đã sai là vô nghĩa và sẽ làm pha loãng, sai lệch con số.

## 6. Tài liệu tham khảo

1. Ebrahimi et al. — HotFlip: White-Box Adversarial Examples for Text Classification, ACL 2018 (nền tảng kỹ thuật).
2. Zou et al. — Universal and Transferable Adversarial Attacks on Aligned Language Models (GCG), 2023.
3. Li et al. — Faster-GCG: Efficient Discrete Optimization Jailbreak Attacks against Aligned Large Language Models, arXiv 2410.15362, 2024 (kỹ thuật tấn công chính thức được chọn).
4. NIST AI.100-2 (2025) — Adversarial Machine Learning: A Taxonomy and Terminology of Attacks and Mitigations.
5. Pierazzi et al. — Intriguing Properties of Adversarial ML Attacks in the Problem Space, ACM TOPS.
6. Adversarial Robustness in URL-Based Phishing Detection: Problem-Space Evaluation and Robust Feature Engineering, MDPI Applied Sciences 2025.
