# Bảng thống kê bài báo

> Chuyển sang markdown từ `bang_thong_ke_bai_bao.xlsx` (Google Drive, sửa lần cuối 08/09/2026). File gốc có 2 sheet: **Package Hallucination** và **Adversarial Robustness**. Cột “Link” trong file gốc chỉ hiện chữ “Xem bài báo”; đường link không trích xuất được nên không đưa vào đây. Vì các ô rất dài, mỗi bài được trình bày thành một mục riêng.

## Sheet 1: Package Hallucination

| STT | Tên bài báo | Tác giả / Năm | Venue |
| --- | --- | --- | --- |
| 1 | We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs | Spracklen et al., 2025 | USENIX Security '25 |
| 2 | The Range Shrinks, the Threat Remains: Re-evaluating LLM Package Hallucinations on the 2026 Frontier-Model Cohort | Churilov, 2026 | arXiv:2605.17062 |
| 3 | Importing Phantoms: Measuring LLM Package Hallucination Vulnerabilities | Krishna, Galinkin, Derczynski, Martin, 2025 | CAMLIS 2025 / arXiv:2501.19012 |
| 4 | Beyond Typosquatting: An In-depth Look at Package Confusion | Neupane, Holmes, Wyss, Davidson, De Carli, 2023 | USENIX Security '23 |
| 5 | ConfuGuard: Using Metadata to Detect Active and Stealthy Package Confusion Attacks Accurately and at Scale | Jiang, Çakar, Lysenko, Davis, 2025 | arXiv:2502.20528 |
| 6 | CLETer: A Character-level Evasion Technique Against Deep Learning DGA Classifiers | Liu, Zhang, Huang, Fang, 2021 | EAI Trans. Security and Safety, vol. 7 no. 24 |

### 1. We Have a Package for You! (Spracklen et al., 2025)

- **Phương pháp:** Đo lường thực nghiệm trên 16 model tạo mã, 2,23 triệu mẫu mã nguồn Python/JavaScript.
- **Chỉ số Baseline:** Tỷ lệ hallucination 19,7% chung.
- **Chỉ số Tấn công:** Không (bài đo lường hiện tượng, không xây detector để tấn công).
- **Chỉ số Phòng thủ:** Không.
- **Vai trò trong đề cương:** Bài nền tảng — đặt tên slopsquatting, đo tỷ lệ open-source (21,7%) vs closed-source (5,2%).

### 2. The Range Shrinks, the Threat Remains (Churilov, 2026)

- **Phương pháp:** Lặp lại đúng phương pháp Spracklen trên 5 model 2026.
- **Chỉ số Baseline:** Tỷ lệ hallucination 4,62–6,10%.
- **Chỉ số Tấn công:** Không.
- **Chỉ số Phòng thủ:** Không.
- **Vai trò trong đề cương:** Đo lường gần nhất — 127 tên gói hallucinate chung giữa 5 model, 53 tên còn đăng ký được.

### 3. Importing Phantoms (Krishna et al., 2025)

- **Phương pháp:** Đo lường độc lập, xét thêm biến ngôn ngữ lập trình và kích thước model.
- **Chỉ số Baseline:** Tỷ lệ hallucination theo ngôn ngữ/kích thước model.
- **Chỉ số Tấn công:** Không.
- **Chỉ số Phòng thủ:** Không.
- **Vai trò trong đề cương:** Đo lường độc lập song song — dùng để tam giác hoá kết quả của Spracklen.

### 4. Beyond Typosquatting (Neupane et al., 2023)

- **Phương pháp:** Phân tích định tính, xây bộ phân loại từ dữ liệu tấn công thật.
- **Chỉ số Baseline:** 13 danh mục cơ chế gây nhầm lẫn tên gói.
- **Chỉ số Tấn công:** Không.
- **Chỉ số Phòng thủ:** Không.
- **Vai trò trong đề cương:** Nền tảng threat model — chưa gắn LLM nhưng hệ thống hoá package confusion attack.

### 5. ConfuGuard (Jiang et al., 2025)

- **Phương pháp:** Phân tích cú pháp/ngữ nghĩa tên gói + cấu trúc namespace + xác thực metadata.
- **Chỉ số Baseline:** 630 vụ tấn công thật được xác nhận.
- **Chỉ số Tấn công:** Không (chưa test trước attacker chủ động né tránh).
- **Chỉ số Phòng thủ:** FPR giảm 80% → 28%, +14s latency (so với baseline chưa lọc metadata).
- **Vai trò trong đề cương:** Cơ chế phòng thủ gần nhất hiện có — chính là khoảng trống đề tài lấp vào.

### 6. CLETer (Liu et al., 2021)

- **Phương pháp:** White-box, CÓ CHỦ ĐÍCH: (1) Định lượng mức ảnh hưởng của từng vị trí ký tự tới quyết định phân loại (gradient/leave-one-out). (2) Xếp hạng, chọn ra vị trí ảnh hưởng lớn nhất (thường 2 vị trí). (3) Thay bằng ký tự được TỐI ƯU HOÁ (không random) để tối đa hoá khả năng né. Vì có tín hiệu nhất quán, classifier HỌC ĐƯỢC pattern khi adversarial training. Công thức/thuật toán cốt lõi: CharacterImportance(i) = |Δoutput khi thay ký tự i| → chọn top-2, tối ưu ký tự thay thế.
- **Chỉ số Baseline:** Recall LSTM = 99,76%; Recall CNN = 99,36%.
- **Chỉ số Tấn công:** Chỉ đổi 2 ký tự: recall LSTM giảm còn 1,29%; recall CNN giảm còn 3,64%.
- **Chỉ số Phòng thủ:** Adversarial retraining LÀ chiến lược phòng thủ khả thi (khác hẳn CharBot).
- **Vai trò trong đề cương:** ĐỐI LẬP trực tiếp với CharBot cùng ngân sách 2 ký tự — bằng chứng RQ3 cần tách theo TỪNG loại tấn công.

## Sheet 2: Adversarial Robustness

| STT | Tên bài báo | Tác giả / Năm | Venue | Loại kỹ thuật |
| --- | --- | --- | --- | --- |
| 1 | HotFlip: White-Box Adversarial Examples for Text Classification | Ebrahimi, Rao, Lowd, Dou, 2018 | ACL 2018 | Kỹ thuật tấn công thuần |
| 2 | DeepDGA: Adversarially-Tuned Domain Generation and Detection | Anderson, Woodbridge, Filar, 2016 | arXiv:1610.01969 | Kỹ thuật tấn công thuần |
| 3 | MaskDGA: A Black-box Evasion Technique Against DGA Classifiers and Adversarial Defenses | Sidi, Nadler, Shabtai, 2019 | arXiv:1902.08909 | Kỹ thuật tấn công thuần |
| 4 | Adversarial DGA Domain Examples Generation and Detection | Cao, Wang, Huang, Cheng, Fu, 2020 | ACM CCRIS 2020 | Kỹ thuật tấn công thuần |
| 5 | Towards Robust Domain Generation Algorithm Classification | Drichel, Meyer, Meyer, 2024 | ACM AsiaCCS 2024 / arXiv:2404.06236 | Phòng thủ / hardening |
| 6 | Adversarial Training for Raw-Binary Malware Classifiers | Lucas, Pai, Lin, Bauer, Reiter, Sharif, 2023 | USENIX Security '23 | Cross-domain (malware) |
| 7 | TextAttack: A Framework for Adversarial Attacks, Data Augmentation, and Adversarial Training in NLP | Morris, Lifland, Yoo, Grigsby, Jin, Qi, 2020 | EMNLP 2020 (System Demos) | Framework |
| 8 | CharBot: A Simple and Effective Method for Evading DGA Classifiers | Peck, Nie, Sivaguru, Grumer, Olumofin, Yu, Nascimento, De Cock, 2019 | IEEE Access, vol. 7 | Kỹ thuật tấn công thuần |

### 1. HotFlip (Ebrahimi et al., 2018)

- **Cơ chế hoạt động:** (1) Biểu diễn mỗi ký tự dưới dạng one-hot vector qua embedding layer của detector. (2) Tính gradient loss theo hướng “muốn đổi nhãn” cho từng vị trí ký tự. (3) Ước lượng ΔLoss nếu đổi sang từng ký tự khác bằng tích vô hướng gradient × hiệu embedding — xấp xỉ tuyến tính, không cần chạy lại mô hình. (4) Chọn (vị trí, ký tự) có ΔLoss lớn nhất, thực hiện flip. (5) Lặp r lần (greedy) hoặc dùng beam search giữ b ứng viên tốt nhất mỗi bước.
- **Công thức cốt lõi:** ΔLoss ≈ ∇ₓL(x)·(e_new − e_old); argmax trên toàn bộ vị trí × ký tự.
- **Chỉ số Baseline:** Accuracy classifier sạch trước tấn công.
- **Chỉ số Tấn công:** Đổi trung bình 4,18% ký tự đạt ASR ở ngưỡng tin cậy 0,5; beam search đạt ASR > 90% ở ngưỡng 0,9.
- **Chỉ số Phòng thủ:** Lỗi phân loại sai thấp nhất còn 7,65% sau adversarial training.
- **Vai trò trong đề tài:** Kỹ thuật GỐC dùng trực tiếp cho Giai đoạn 2 — chỉ đổi “câu văn” thành “tên gói”.

### 2. DeepDGA (Anderson et al., 2016)

- **Cơ chế hoạt động:** (1) Autoencoder học biểu diễn latent liên tục từ domain thật. (2) Generator (GAN) sinh domain mới từ nhiễu ngẫu nhiên để đánh lừa discriminator. (3) Discriminator đóng vai trò gần giống DGA classifier thật. (4) Huấn luyện đối kháng theo minimax loss GAN chuẩn. (5) Lặp theo “round”: domain né được ở round hiện tại được thêm vào tập huấn luyện classifier cho round sau.
- **Công thức cốt lõi:** min_G max_D E[log D(x_real)] + E[log(1 − D(G(z)))].
- **Chỉ số Baseline:** AUC-ROC = 0,9710 (round 0).
- **Chỉ số Tấn công:** AUC-ROC giảm còn 0,9319 sau 3 round tấn công GAN liên tiếp.
- **Chỉ số Phòng thủ:** Retrain trên mẫu adversarial giúp phát hiện tốt hơn các họ DGA chưa từng thấy.
- **Vai trò trong đề tài:** Mô hình “vòng lặp round” chính là cấu trúc Attack ↔ Adversarial training lặp lại trong Giai đoạn 2.

### 3. MaskDGA (Sidi et al., 2019)

- **Cơ chế hoạt động:** (1) Black-box — không cần biết trọng số/kiến trúc, chỉ cần query input-output. (2) Thay tạm mỗi ký tự bằng “mask” đặc biệt, quan sát xác suất phân loại đổi bao nhiêu — xấp xỉ vai trò gradient mà không cần backprop. (3) Xếp hạng vị trí theo mức ảnh hưởng, chọn vị trí quan trọng nhất để đổi ký tự (tối ưu cục bộ). (4) Đánh giá riêng 2 kiểu phòng thủ: adversarial retraining và distillation (huấn luyện lại với soft-label để làm mượt decision boundary).
- **Công thức cốt lõi:** Importance(i) ≈ |P(y\|x) − P(y\|x với ký tự i bị mask)|.
- **Chỉ số Baseline:** F1-score trung bình 0,977 (4 DGA classifier).
- **Chỉ số Tấn công:** F1-score giảm còn 0,495 dưới tấn công (mất ~50% hiệu năng).
- **Chỉ số Phòng thủ:** Đánh giá tách riêng hiệu quả của retraining vs distillation như 2 phương án phòng thủ độc lập.
- **Vai trò trong đề tài:** Kịch bản “attacker không biết kiến trúc D0” — bổ sung song song với kịch bản white-box HotFlip.

### 4. Adversarial DGA Domain Examples Generation and Detection (Cao et al., 2020)

- **Cơ chế hoạt động:** Cơ chế GAN tương tự DeepDGA, nhưng generator (DnGAN) được huấn luyện có thêm ràng buộc để domain sinh ra có phân bố entropy/thống kê ký tự gần giống domain thật hơn — nhằm né được cả các bộ lọc dựa trên entropy, không chỉ riêng ML classifier.
- **Công thức cốt lõi:** Loss GAN chuẩn + ràng buộc entropy(domain sinh ra) ≈ entropy(domain thật).
- **Chỉ số Baseline:** Detection rate cao trên 4 phương pháp ML (không nêu số cụ thể).
- **Chỉ số Tấn công:** Detection rate giảm 5–7 điểm phần trăm; entropy mẫu nhiễu ~0,89 (gần domain thật).
- **Chỉ số Phòng thủ:** Không đề cập cơ chế phòng thủ.
- **Vai trò trong đề tài:** Gợi ý bổ sung ràng buộc “độ tự nhiên” khi thiết kế attacker cho package name (tránh tên quá lộ liễu).

### 5. Towards Robust Domain Generation Algorithm Classification (Drichel et al., 2024)

- **Cơ chế hoạt động:** TẤN CÔNG: tổng hợp 32 kỹ thuật khác nhau (gồm cả biến thể gradient-based và black-box) để đánh giá toàn diện. PHÒNG THỦ (2 kỹ thuật hardening chính): (a) Adversarial training trên latent space — sinh nhiễu trực tiếp trong không gian embedding liên tục rồi ánh xạ ngược về ký tự hợp lệ gần nhất. (b) Discretized adversarial domains — đảm bảo mọi mẫu huấn luyện đều là domain hợp lệ về cú pháp thật, không phải điểm “ảo” trong embedding.
- **Công thức cốt lõi:** x_adv = x + ε·sign(∇ₓL) rồi discretize về ký tự hợp lệ gần nhất.
- **Chỉ số Baseline:** Detection performance trên DGA đã biết/chưa biết.
- **Chỉ số Tấn công:** 19/32 kỹ thuật đẩy False Negative Rate lên ~100% trên classifier chưa hardening.
- **Chỉ số Phòng thủ:** KHÔNG quan sát thấy đánh đổi robustness-accuracy — hardening còn cải thiện cả detection sạch.
- **Vai trò trong đề tài:** SÁT NHẤT về phương pháp — dùng làm khung tham chiếu chính cho toàn bộ Giai đoạn 2 + trả lời RQ3.

### 6. Adversarial Training for Raw-Binary Malware Classifiers (Lucas et al., 2023)

- **Cơ chế hoạt động:** (1) Chèn byte “vô hại” (padding) vào file nhị phân sao cho hành vi thực thi không đổi (functionality-preserving) nhưng đặc trưng đầu vào classifier bị lệch. (2) Đóng góp chính: tối ưu TỐC ĐỘ sinh mẫu adversarial để adversarial training khả thi ở quy mô lớn — đây là rào cản chính trước đó. (3) Phát hiện: huấn luyện với 1 họ kỹ thuật chèn byte tăng luôn robustness trước kỹ thuật khác.
- **Công thức cốt lõi:** Content-preserving byte insertion + tối ưu vị trí chèn bằng gradient.
- **Chỉ số Baseline:** Accuracy cao trên phân loại binary malicious/benign.
- **Chỉ số Tấn công:** Tăng hiệu quả/quy mô sinh mẫu tấn công (hàng trăm nghìn mẫu).
- **Chỉ số Phòng thủ:** Huấn luyện với tấn công A tăng bền vững trước tấn công B (defense transfer).
- **Vai trò trong đề tài:** CÙNG VENUE với Spracklen (USENIX Security) — lập luận mạnh cho tính cấp thiết/khoảng trống.

### 7. TextAttack (Morris et al., 2020)

- **Cơ chế hoạt động:** KHÔNG phải 1 kỹ thuật cụ thể — là framework đóng gói pipeline 4 thành phần: (1) Goal function — mục tiêu tấn công. (2) Constraints — ràng buộc phải giữ (giữ nghĩa/naming rule). (3) Transformation — cách sinh ứng viên nhiễu. (4) Search method — cách tìm kiếm (greedy/beam/genetic algorithm).
- **Công thức cốt lõi:** Pipeline: GoalFunction × Constraints × Transformation × SearchMethod.
- **Chỉ số Baseline:** Original accuracy (định nghĩa chuẩn).
- **Chỉ số Tấn công:** Chuẩn hoá Attack Success Rate, After-attack Accuracy.
- **Chỉ số Phòng thủ:** Module adversarial training tích hợp sẵn.
- **Vai trò trong đề tài:** Dùng 4 thành phần này làm KHUNG THIẾT KẾ khi viết phần Phương pháp — giúp trình bày mạch lạc.

### 8. CharBot (Peck et al., 2019)

- **Cơ chế hoạt động:** Cực đơn giản, KHÔNG dùng gradient hay query-based importance: chọn NGẪU NHIÊN 2 vị trí ký tự, thay bằng ký tự NGẪU NHIÊN khác. Không có bước “chọn lọc thông minh” — vì tính ngẫu nhiên hoàn toàn, không có tín hiệu nhất quán để classifier học khi retrain.
- **Công thức cốt lõi:** Random(2 vị trí) → Random(ký tự thay thế) — không tối ưu hoá.
- **Chỉ số Baseline:** Detection rate cao trên FANCI và LSTM.MI.
- **Chỉ số Tấn công:** LSTM.MI chỉ còn phát hiện ~55% mẫu ở FPR 0,1%, dù kỹ thuật rất đơn giản.
- **Chỉ số Phòng thủ:** Retraining trên mẫu CharBot KHÔNG phải chiến lược phòng thủ khả thi (tác giả xác nhận).
- **Vai trò trong đề tài:** Kịch bản tấn công NGẪU NHIÊN — test xem D′ có bền trước loại tấn công “không học được” không.
