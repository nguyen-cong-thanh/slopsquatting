# Bảng so sánh chỉ số: công trình liên quan vs. đề tài

> Chuyển sang markdown từ `detail_survey.docx` (Google Drive, sửa lần cuối 15/09/2026). Chỉ chuyển phần chữ và bảng; hình ảnh nhúng trong file gốc (nếu có) không được đưa vào.

**Slopsquatting (Package Hallucination) + Faster-GCG**

## 1. Nhóm công trình liên quan theo mức độ nghiên cứu

Các công trình không đồng nhất về độ sâu can thiệp — có bài chỉ đo hiện tượng, có bài kiểm tra tồn tại (không ML), có bài phân loại tĩnh, có bài can thiệp tầng code, có bài chặn lúc sinh mã. Xếp theo nhóm giúp thấy rõ đề tài đứng ở tầng nào.

| Nhóm (mức độ) | Công trình đại diện | Cách làm cụ thể | Chỉ số dùng | Giá trị chỉ số |
| --- | --- | --- | --- | --- |
| A — Đo lường ảo giác thuần | We Have a Package for You! (2406.10279) | Prompt LLM sinh code, đối chiếu registry để đếm tên ảo giác — không phân loại, không tấn công | PHR (Package Hallucination Rate) | 3.59% (GPT-4 Turbo) → 35.71% (CodeLlama-7B, JS) |
| A — Đo lường + phòng vệ tại inference-time | Evaluating Inference-Time Defenses (2608.22652) | So sánh decoding strategies/RAG/self-refine — vẫn đo bằng PHR, không có classifier riêng | PHR trước/sau phòng vệ | RAG: 29.7% → 18.1%; hostile prompt: PHR vọt lên 80.9–95.2% |
| B — Kiểm tra tồn tại tĩnh qua API registry (rule-based, không ML) | Kênh registry-check trong Names Can Hurt, Bayesian-Calibrated Detection | Gọi API PyPI/npm, kiểm tra tên có tồn tại không — nhị phân, không có “mô hình” để đo FPR/ASR theo nghĩa ML | Không áp dụng ASR/FPR kiểu ML | Không có số công bố (bản chất là lookup, không phải phân loại thống kê) |
| C1 — Phân loại tĩnh dựa đặc trưng tên/metadata | ConfuGuard / TypoSmart | Fine-tuned FastText + ngưỡng similarity trên đặc trưng tên gói | FPR, Precision, Recall, F1 | FPR 13% (từ 77% baseline cũ); P=1.00; R=0.87–0.91; F1=0.93–0.95; stealthy: R=0.59–0.82, F1=0.74–0.90 |
| C2 — Hệ thống nhiều lớp (registry-check + RF + retry/fallback) | Names Can Hurt (2608.23897) | Kiểm tra registry + Random Forest trên đặc trưng tên/metadata + retry nội bộ model + fallback sang model khác trong LangGraph | Tỷ lệ ảo giác còn sót (PHR sau phòng vệ), tỷ lệ khôi phục nhờ retry/fallback, khảo sát người dùng | PHR routine coding: 0–10%; PHR dưới “bait” ảo giác có chủ đích: 40–73%; retry nội bộ khôi phục ~1/4 số lần hết ngân sách thử; fallback sang model khác khôi phục thêm 16.5%; ~84% lỗi lặp lại khi model chính và fallback cùng họ; khảo sát người dùng (n=24): hài lòng 4.4/5, 21/24 muốn tiếp tục dùng |
| C3 — Phân loại có hiệu chỉnh xác suất (Bayesian calibration) | Bayesian-Calibrated Detection (2606.13918) | Lớp Bayesian bọc ngoài detector deterministic, 2 biến thể: chỉ registry-channel vs. registry+metadata | Precision, Recall, F1, Expected Calibration Error (ECE) | Registry-only: P=0.956, R=0.881, F1=0.917, ECE=0.016; +metadata: P=0.915, R=0.881, F1=0.898, ECE=0.029 (thêm metadata làm giảm precision nhẹ); stress-test hallucination rate theo từng model: 8.3–17.6%; Claude-Sonnet-4.6 có precision kênh registry thấp nhất (0.73) trong khi các model khác ≥0.97 — bằng chứng thực nghiệm thêm cho việc cần đa dạng nguồn LLM |
| D — Phòng ngừa tại tầng sinh mã (decode-time, không phải detector hậu kiểm) | PackMonitor (2602.20717) | Chặn token không hợp lệ ngay lúc LLM decode (DFA + logits masking theo danh sách gói thật) | PHR trước/sau, overhead độ trễ sinh mã, Pass@1 (HumanEval) | PHR về 0% trên cả 5 model (từ mức gốc 3.25–8.39%); overhead sinh mã chỉ ×1.07–1.28 (+0.06–0.25s); so sánh: fine-tuning (SFT) không đạt 0% (DeepSeek 2.66%, CodeLlama 10.27%) và còn làm giảm Pass@1 tới 26.9%, trong khi PackMonitor giữ Pass@1 không đổi |
| E — Có yếu tố đối kháng, nhưng ở tầng khác tên gói | One Detector Fits All (2512.04338) — tầng code; Evaluating Inference-Time Defenses — tầng prompt | Adversarial training (XGBoost) chống code obfuscation (E1); hostile prompt ép LLM ảo giác nhiều hơn (E2) | Recall@1%FPR trước/sau obfuscation và AT (E1); PHR tăng theo hostile prompt (E2) | E1 — số liệu mạnh nhất tìm được, cùng hệ sinh thái PyPI: Recall@1%FPR của XGBoost giảm từ 95.27% → 24.30% khi gói bị obfuscate; sau adversarial training, hồi phục lên 86.81%; baseline khác cùng bài: GuardDog 6.63% → 1.00%, Decision Tree 69.14% → 4.60%, Random Forest 90.54% → 12.10%. Triển khai thực tế (live2, 37 ngày): tại 1%FPR — P=18.73%, R=83.33%, F1=30.59%; tại 0.1%FPR — 2.48 TP/ngày, 2.18 FP/ngày; tại 10%FPR (enterprise) — accuracy 97.12%, 1.24 FP/ngày. E2: PHR 80.9–95.2% |
| F — Đối kháng cấp ký tự trên tên gói + AT — Đề tài của tôi | Chưa ai làm | Faster-GCG (white-box) + LLM-guided (black-box) tấn công D0, đo ASR theo ngân sách nhiễu, adversarial training ra D′, đo lại FPR | ASR, FPR, ΔFPR, Robust Accuracy | Xem Mục 2 — bảng ASR các kỹ thuật tương tự, Mục 3 — công thức & mục tiêu |

**Đọc nhanh:** nhóm A/D không có detector nên không có FPR/ASR theo đúng nghĩa; nhóm B không phải ML nên cũng vậy; nhóm C có FPR/Precision/Recall/F1 (và với C2/C3 còn có số liệu hệ thống/hiệu chỉnh chi tiết) nhưng chưa ai kiểm chứng đối kháng; nhóm E có yếu tố đối kháng và nay đã có số liệu rất cụ thể (đặc biệt One Detector Fits All: 95.27% → 24.30% → 86.81%) nhưng nhắm vào code hoặc prompt, không phải tên gói. Nhóm F (đề tài của tôi) là nhóm duy nhất kết hợp cả ba: detector có FPR + đối kháng cấp ký tự trên tên gói + đo cả ASR lẫn FPR.

**Vì sao số liệu của One Detector Fits All (nhóm E) đáng chú ý hơn Lucas et al. (malware, dùng ở Mục 3):** đây là công trình cùng hệ sinh thái package (PyPI) — mức phục hồi Recall@1%FPR sau AT (24.30% → 86.81%) là bằng chứng trong-domain mạnh rằng mục tiêu ASR(D′) < 30% / < 10% và ΔFPR ≤ +5 điểm % đã đề xuất ở Mục 3 là khả thi, thậm chí có thể đặt mục tiêu tham vọng hơn nếu Faster-GCG + AT đạt hiệu quả tương tự.

## 2. Bảng ASR — kỹ thuật tấn công đối kháng tương tự

Trả lời trực tiếp góp ý #2 của thầy: ASR của Faster-GCG và các kỹ thuật họ hàng/tương tự đã công bố ở đâu, giá trị bao nhiêu — căn cứ đặt mục tiêu ASR cho D0/D′ ở Mục 3.

| Kỹ thuật | Bài toán gốc | ASR | Chi phí / ngân sách |
| --- | --- | --- | --- |
| HotFlip (Ebrahimi et al. 2018) | Text classifier (sentiment, v.v.) | ~69–93% | chỉ 1–2 flip ký tự |
| Universal Adversarial Triggers (Wallace et al. 2019) | Text classifier — tấn công trực tiếp, tiền thân của GCG | Accuracy 86% → 23–29% (sentiment); ~0% (SNLI); 31.6–50% (SQuAD) | trigger 3–6 token |
| GCG gốc (Zou et al. 2023) | LLM jailbreak, white-box | 84–98% (white-box); transfer: GPT-3.5 86.6%, GPT-4 46.9%, PaLM-2 66%, Claude-2 2.1% | ~256K forward-pass/mẫu |
| Faster-GCG (Li et al. 2024) — kỹ thuật đề tài dùng | LLM jailbreak, white-box | 78.1% trung bình (tới 88.7%) | ~32K forward-pass (giảm 8×), thời gian giảm 7× |
| Adversarial training — malware classifier (Lucas et al. 2023) | Malware classifier, trước/sau AT | Displacement 90% → 5%; IPR 26% → 6%; Kreuk 84% → 30% | — |
| DomainGAN (2019) | DGA domain classifier | Detection rate giảm 96% → 48% | GAN-based |
| FENCE (Chernikova & Oprea 2022) | Traffic/domain độc hại, có ràng buộc feasibility | 79–100% tùy ngân sách nhiễu | 99% tại L2=16; 98.3–100% tại L2=20 |
| One Detector Fits All (2512.04338) — cùng hệ sinh thái PyPI | XGBoost malicious-package detector, code obfuscation + adversarial training | Recall@1%FPR: 95.27% → 24.30% (obfuscate, chưa AT) → hồi phục 86.81% (sau AT) | Số liệu in-domain mạnh nhất tìm được |
| Đề tài của tôi — Faster-GCG trên D0 (đo thực nghiệm) | Slopsquatting D0, chưa phòng thủ | Chưa có số liệu — dự kiến 70–95%+, đo theo từng ngân sách nhiễu k=1,2,3 | đo số forward-pass/mẫu thực tế |
| Đề tài của tôi — D′ sau adversarial training (mục tiêu) | Slopsquatting, bền vững | < 30% (tốt), < 10% (rất tốt) | — |

**Đọc nhanh:** ASR của các kỹ thuật họ GCG/HotFlip khi tấn công trực tiếp classifier hoặc LLM dao động rộng (~70–98% white-box), nhưng sau adversarial training luôn giảm mạnh — mức giảm rõ nhất và cùng hệ sinh thái với đề tài là One Detector Fits All (95.27% → 24.30%, rồi phục hồi 86.81% sau AT). Đây là căn cứ chính cho mục tiêu ASR(D′) < 30% / < 10% ở Mục 3.

## 3. Công thức các con số của đề tài

| Chỉ số | Công thức | Giải thích 1 câu | Mục tiêu đề xuất |
| --- | --- | --- | --- |
| Precision | TP / (TP + FP) | Trong số tên gói D0 báo “khả nghi”, bao nhiêu % thực sự ảo giác/độc hại | ≈ 1.00 |
| Recall | TP / (TP + FN) | Trong số tên gói thực sự ảo giác/độc hại, D0 bắt được bao nhiêu % | ≥ 0.87–0.91 |
| F1 | 2×P×R / (P+R) | Trung bình điều hòa Precision & Recall | ≥ 0.93–0.95 |
| FPR | FP / (FP + TN) | Trong số tên gói hợp lệ, bao nhiêu % bị báo oan | D0 ≤ 1–5% |
| ASR | (mẫu D0 phát hiện đúng, sau nhiễu bị sai) / (mẫu D0 phát hiện đúng) | Kẻ tấn công né được bao nhiêu % trong số mẫu D0 vốn bắt được | D′ < 30% (tốt) / < 10% (rất tốt) |
| ΔFPR | FPR(D′) − FPR(D0) | Cái giá phải trả về FPR khi làm D′ bền vững hơn | ≤ +5 điểm % |
| Robust Accuracy | 1 − ASR | % mẫu tấn công không né được — càng cao càng bền vững | D′ > D0 rõ rệt |

**Vì sao các mục tiêu này không phải số bịa:** FPR ≤ 1–5% và F1 ≥ 0.93–0.95 lấy từ mức ConfuGuard/TypoSmart (nhóm C — công trình gần nhất có số cụ thể); ASR < 30% / < 10% và ΔFPR ≤ +5 điểm % lấy từ mức đánh đổi quan sát được trong adversarial training cho malware classifier (Lucas et al. 2023) và từ One Detector Fits All cùng hệ sinh thái PyPI (xem bảng đầy đủ ở Mục 2). Tất cả là ngưỡng tham chiếu suy ra từ bài toán liền kề — chưa có số sẵn cho slopsquatting.

## 4. Độ trễ & phần cứng — kèm bằng chứng cụ thể

| Chỉ số | Ngân sách / giá trị đề xuất | Bằng chứng cụ thể |
| --- | --- | --- |
| Latency suy luận D0/D′ (1 tên gói) | p95 ≤ 10 ms, p99 ≤ 30 ms (CPU) | LSTM DGA classifier (Woodbridge et al. 2016, arXiv:1611.00791) — bài toán giống nhất (phân loại 1 chuỗi tên ngắn) — đạt 20ms/domain trên MacBook Pro i7 2.2GHz 2016, KHÔNG tối ưu gì. D0/D′ dùng 1D-CNN/RF nhẹ hơn LSTM, chạy trên CPU hiện đại hơn 10 năm → p95 ≤ 10ms là mục tiêu thận trọng. Bằng chứng gián tiếp thêm: HuggingFace Infinity đo được 1–4ms cho Transformer (nặng hơn D0 nhiều) trên CPU Ice Lake, seq ≤ 64 token. |
| Overhead tại Kong Gateway | ≤ 5–10% so với baseline không plugin | Đo trực tiếp bằng header X-Kong-Upstream-Latency / X-Kong-Proxy-Latency khi build Lớp 2 của kế hoạch thực nghiệm |
| So sánh round-trip API PyPI/npm | 50–300 ms | Chi phí mạng đã tồn tại sẵn trong pipeline hiện tại, không do đề tài phát sinh. |
| Throughput | ≥ 500–1000 tên gói/giây/instance | Suy từ latency suy luận (1 request ≤ 10ms → 1 luồng ~100 req/s; 4 vCPU song song → 500–1000 req/s là mục tiêu hợp lý) — CẦN đo thật bằng k6 để xác nhận, đây là ước lượng ban đầu. |
| Kích thước model | 1D-CNN ~1–10 MB; RF/XGBoost < 5 MB | Tính trực tiếp từ kiến trúc đề xuất ở mục 3.1 đề cương (vài lớp conv trên chuỗi ≤ 50 ký tự / cây giới hạn độ sâu). |
| GPU | Không cần khi suy luận; chỉ cần khi huấn luyện + Faster-GCG + AT | Tách rõ pha offline (huấn luyện, cần GPU) và pha online (suy luận, CPU đủ) — phù hợp benchmark NVIDIA FIL cho tree-ensemble suy luận quy mô nhỏ. |

**Lưu ý trung thực:** “p95 ≤ 10ms”, “throughput ≥ 500–1000/s” vẫn là mục tiêu/ước lượng có căn cứ, không phải số đã đo trên chính D0/D′ — đề cương chưa chạy thực nghiệm. Khi đo thật theo kế hoạch Lớp 1–3, thay số đo thật vào cột “giá trị đề xuất”.

## 5. Chi phí token cho Giai đoạn 1 (sinh dữ liệu từ 4 LLM)

### 5.1. Giá API hiện hành

| Model | Input ($/1M token) | Output ($/1M token) | Nguồn |
| --- | --- | --- | --- |
| GPT-4o | $2.50 | $10.00 | OpenAI pricing, tổng hợp qua KickLLM (kickllm.com/tools/gpt-4-pricing.html) |
| Claude Sonnet 5 | $2.00 | $10.00 | Anthropic pricing (platform.claude.com/docs/en/about-claude/pricing) |
| CodeLlama-13B (host qua Fireworks AI) | $0.20 | $0.20 | CloudPrice (cloudprice.net/models/meta-codellama-13b) |
| DeepSeek-Coder-7B-Base (host qua Fireworks AI) | $0.20 | $0.20 | PricePerToken (pricepertoken.com — deepseek-deepseek-coder-7b-base) |

2 model mã nguồn mở không có API chính chủ theo token — giá trên là giá host qua bên thứ ba (Fireworks AI).

### 5.2. Giả định quy mô (đề xuất ban đầu, cần chốt lại)

| Tham số | Giá trị đề xuất | Ghi chú |
| --- | --- | --- |
| Số prompt coding task riêng biệt / model | 1.500 (đã giảm từ đề xuất trước 2.500) | Vẫn đủ đa dạng tác vụ lập trình cho quy mô luận văn thạc sĩ, giảm ~40% chi phí so với đề xuất trước |
| Token input trung bình / prompt | 300 token | Gồm system prompt + mô tả tác vụ coding |
| Token output trung bình / prompt | 400 token | 1 đoạn code ngắn kèm import |
| Số lần lặp lại / prompt (k) | 1 (mặc định) | Nếu đo tính lặp lại của ảo giác (như “We Have a Package for You!”, họ dùng k=10), nhân chi phí ở bảng 5.3 theo hệ số k |

### 5.3. Bảng chi phí (đã giảm)

Công thức: Chi phí = (Input_tokens × Giá_input) + (Output_tokens × Giá_output), với Input = 1.500 × 300 = 0,45M token; Output = 1.500 × 400 = 0,60M token (mỗi model, k=1).

| Model | Input (0,45M tok) | Output (0,60M tok) | Tổng / model |
| --- | --- | --- | --- |
| GPT-4o | 0,45 × $2.50 = $1.125 | 0,60 × $10.00 = $6.00 | $7.13 |
| Claude Sonnet 5 | 0,45 × $2.00 = $0.90 | 0,60 × $10.00 = $6.00 | $6.90 |
| CodeLlama-13B | 0,45 × $0.20 = $0.09 | 0,60 × $0.20 = $0.12 | $0.21 |
| DeepSeek-Coder-7B | 0,45 × $0.20 = $0.09 | 0,60 × $0.20 = $0.12 | $0.21 |

**Tổng cả 4 model** (k=1, 1.500 prompt/model = 6.000 lượt sinh code): ≈ $14.5 (giảm từ $24.1)

#### Muốn giảm sâu hơn nữa? — lệch tỷ lệ về model rẻ

Đòn bẩy mạnh nhất không phải giảm đều 4 model, mà là giảm riêng 2 model đắt (GPT-4o, Claude Sonnet 5 — chiếm ~97% chi phí) và giữ/tăng 2 model rẻ (CodeLlama-13B, DeepSeek-Coder-7B chỉ chiếm ~3%):

| Kịch bản | GPT-4o | Claude Sonnet 5 | CodeLlama-13B | DeepSeek-Coder-7B | Tổng |
| --- | --- | --- | --- | --- | --- |
| Đều nhau — 1.500/model (mặc định) | 1.500 | 1.500 | 1.500 | 1.500 | $14.5 |
| Lệch về model rẻ — 500 (đóng) / 1.500 (mở) | 500 | 500 | 1.500 | 1.500 | $5.1 |
| Tối thiểu — 300 (đóng) / 1.000 (mở) | 300 | 300 | 1.000 | 1.000 | $3.1 |

Cách này vẫn giữ tiêu chí đa dạng 2 trục (đóng/mở, tổng quát/chuyên code) đã nêu ở câu hỏi 5 của thầy, chỉ lệch tỷ lệ đóng góp dữ liệu — 2 model mở đã rẻ đến mức tăng số lượng gần như không tốn thêm bao nhiêu.

#### Kịch bản mở rộng (nếu ngược lại cần tăng quy mô)

- k=5 (đo tính lặp lại ảo giác, giống “We Have a Package for You!”): ≈ $72.3
- Tăng lên 2.500 prompt/model như đề xuất ban đầu (10.000 lượt sinh code): ≈ $24.1
- Tăng lên 10.000 prompt/model (40.000 lượt sinh code): ≈ $96.4 (k=1)

**Nhận xét:** phần lớn chi phí luôn đến từ GPT-4o và Claude Sonnet 5, vì giá gấp ~30–60 lần so với 2 model mã nguồn mở host qua Fireworks — đây là đòn bẩy cắt giảm hiệu quả nhất.

### 5.4. Cách giảm khác — đổi version model rẻ hơn thay vì giảm số prompt

Giảm số prompt (Mục 5.2–5.3) đồng nghĩa giảm luôn kích thước dataset. Có một đòn bẩy khác không đánh đổi điều đó: giữ nguyên số prompt, chỉ đổi sang bản rẻ hơn của cùng nhà cung cấp — GPT-4o → GPT-4o mini, Claude Sonnet 5 → Claude Haiku 4.5.

| Model | Input ($/1M) | Output ($/1M) | So với bản đầy đủ |
| --- | --- | --- | --- |
| GPT-4o mini | $0.15 | $0.60 | rẻ hơn GPT-4o ~16 lần (input) / ~17 lần (output) |
| Claude Haiku 4.5 | $1.00 | $5.00 | rẻ hơn Claude Sonnet 5 2 lần (cả input lẫn output) |

So sánh 3 cách giảm chi phí (đều xuất phát từ quy mô gốc 2.500 prompt/model):

| Cách giảm | Giữ nguyên kích thước dataset? | Tổng chi phí |
| --- | --- | --- |
| Bản gốc — 4 model đầy đủ, 2.500 prompt/model | Có (10.000 lượt sinh code) | $24.1 |
| Giảm số prompt xuống 1.500/model, giữ model đầy đủ | Không — còn 6.000 lượt | $14.5 |
| Đổi version rẻ (GPT-4o mini + Claude Haiku 4.5), giữ 2.500 prompt/model | Có — vẫn 10.000 lượt | $7.16 |
| Kết hợp cả hai: 1.500 prompt/model + version rẻ | Không — còn 6.000 lượt | $4.30 |

Đổi version rẻ hiệu quả hơn giảm số prompt: chi phí thấp hơn ($7.16 so với $14.5) mà không phải cắt dataset. Nếu muốn tối ưu cả hai, kết hợp cả hai cách đưa chi phí xuống còn ~$4.3.

**Lưu ý cần cân nhắc trước khi chọn (không chỉ là bài toán tiền):** đề cương đã chốt tiêu chí chọn 4 LLM ở câu hỏi 5 là “2 model đóng, tổng quát” — ngầm định là bản mạnh nhất của mỗi nhà cung cấp. GPT-4o mini/Claude Haiku là bản nhỏ hơn, yếu hơn, có thể ảo giác theo cách khác (thường nhiều hơn và kém nhất quán hơn) — nếu đổi hẳn, cần nêu rõ đây là đánh đổi chi phí lấy tính đại diện.

**Phương án cân bằng đề xuất:** dùng bản mini/haiku cho phần lớn dữ liệu (2.500 prompt/model, chi phí thấp), đồng thời chạy thêm một tập đối chiếu nhỏ (200–300 prompt) bằng đúng bản đầy đủ để kiểm tra PHR có khác biệt lớn không — nếu không khác biệt, dùng bản rẻ là hợp lý; nếu khác biệt lớn, đó là một phát hiện đáng báo cáo chứ không phải vấn đề.

Chi phí tập đối chiếu 250 prompt × 2 model đầy đủ ≈ $2.4 — không đáng kể so với khoản tiết kiệm được.

## 6. Chú thích các từ viết tắt

| Viết tắt | Tên đầy đủ | Giải thích ngắn |
| --- | --- | --- |
| FPR | False Positive Rate | Tỷ lệ dương tính giả — % gói THẬT bị báo nhầm là khả nghi/độc hại |
| ASR | Attack Success Rate | Tỷ lệ tấn công thành công — % mẫu né được bộ phát hiện sau khi bị nhiễu |
| TP / FP / FN / TN | True/False Positive/Negative | TP: đúng dương tính, báo đúng; FP: âm tính nhưng báo nhầm; FN: dương tính nhưng bỏ sót; TN: đúng âm tính, báo đúng |
| Recall@k%FPR | Recall tại điểm vận hành FPR=k% | Đo Recall (TPR) tại đúng ngưỡng mà FPR bị cố định ở k% — cách so sánh công bằng các detector khi cùng ngân sách báo sai (dùng ở nhóm E, One Detector Fits All) |
| ECE | Expected Calibration Error | Đo chênh lệch giữa xác suất model dự đoán và tỷ lệ đúng thực tế quan sát được — càng thấp thì xác suất model đưa ra càng đáng tin (dùng ở C3, Bayesian-Calibrated Detection) |
| PHR | Package Hallucination Rate | Tỷ lệ tên gói bị LLM “ảo giác” ra (không tồn tại thật trên registry). Công thức (“We Have a Package for You!”): PHR = (số lượt gói ảo giác) / (tổng số lượt gói được đề xuất) — tính trên mỗi lượt đề xuất, không phải trên mỗi tên gói duy nhất |
| AT | Adversarial Training | Huấn luyện đối kháng — huấn luyện lại detector bằng mẫu tấn công để tăng độ bền vững |
| D0 / D′ | Detector gốc / cải tiến | D0: bộ phát hiện cơ sở; D′: bộ phát hiện sau huấn luyện đối kháng (AT) |
| Pass@1 | Pass at 1 | Tỷ lệ % bài toán lập trình mà code sinh ra (1 lần sinh) vượt qua hết unit test — dùng để đo code có còn đúng chức năng sau khi áp dụng biện pháp chống ảo giác gói (PackMonitor dùng để chứng minh không đánh đổi chất lượng code) |
| HumanEval | (tên benchmark, không viết tắt) | Bộ 164 bài lập trình Python kèm unit test (Chen et al. 2021, OpenAI Codex) — benchmark chuẩn để đo Pass@1/Pass@k |
| DFA | Deterministic Finite Automaton | Máy trạng thái hữu hạn đơn định — PackMonitor dùng để mã hoá ngữ pháp tên gói hợp lệ, chặn token sai lúc LLM decode |
| SFT | Supervised Fine-Tuning | Tinh chỉnh có giám sát — huấn luyện lại trọng số model trên dữ liệu gán nhãn, đối lập với cách chặn cứng lúc decode (DFA) |
| L2 (ngân sách nhiễu) | L2-norm perturbation budget | Giới hạn khoảng cách Euclid tối đa giữa mẫu gốc và mẫu bị nhiễu — cách định lượng nhiễu cho phép trong không gian đặc trưng liên tục (dùng ở FENCE) |
| NVIDIA FIL | NVIDIA Forest Inference Library | Thư viện tăng tốc suy luận cho model dạng cây (RF/XGBoost) trên GPU — bằng chứng rằng tree-ensemble không bắt buộc cần GPU khi suy luận quy mô nhỏ |
| ML | Machine Learning | Học máy |
| RF | Random Forest | Thuật toán học máy dựa trên nhiều cây quyết định |
| XGBoost | Extreme Gradient Boosting | Thuật toán học máy dựa trên gradient boosting trên cây quyết định |
| CNN / 1D-CNN | Convolutional Neural Network | Mạng nơ-ron tích chập; bản 1 chiều dùng cho chuỗi ký tự như tên gói |
| LSTM | Long Short-Term Memory | Mạng nơ-ron hồi quy, xử lý tốt dữ liệu dạng chuỗi (domain/tên gói) |
| GCG / Faster-GCG | (Faster) Greedy Coordinate Gradient | Thuật toán tấn công đối kháng dựa gradient, tìm kiếm phối hợp trên chuỗi rời rạc |
| DGA | Domain Generation Algorithm | Thuật toán sinh tên miền tự động (thường dùng bởi malware/botnet) |
| API | Application Programming Interface | Giao diện lập trình ứng dụng — ở đây là API registry (PyPI/npm) hoặc gọi LLM |
| CPU / GPU | Central/Graphics Processing Unit | Bộ xử lý trung tâm / đồ họa (GPU thường dùng để huấn luyện mô hình) |
| RAM / vCPU | Random Access Memory / virtual CPU | Bộ nhớ truy cập ngẫu nhiên; đơn vị CPU ảo hóa |
| MTok | Million Tokens | Triệu token — đơn vị tính giá API của các LLM |
| p50 / p95 / p99 | Percentile 50/95/99 | Giá trị độ trễ mà 50%/95%/99% số lượt đo nằm dưới ngưỡng đó |
| LLM | Large Language Model | Mô hình ngôn ngữ lớn (GPT-4o, Claude, CodeLlama, DeepSeek-Coder...) |
| PyPI / npm | Python Package Index / Node Package Manager | Kho lưu trữ gói phần mềm chính thức của Python và JavaScript/Node.js |
| CI/CD | Continuous Integration/Deployment | Tích hợp liên tục / triển khai liên tục — quy trình tự động build-test-deploy |
| k6 / wrk2 | (tên công cụ) | Công cụ load-testing dùng để đo throughput và độ trễ dưới tải |
