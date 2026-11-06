# Thiết kế dữ liệu cho đề tài Slopsquatting

> Cập nhật ngày 06/11/2026. Bản markdown của tài liệu [Thiết kế dữ liệu cho đề tài Slopsquatting](https://claude.ai/artifact/GFnobrA2pf8FQNpAxV1Gkt).

## Bối cảnh và tóm tắt

Tài liệu này trả lời các câu hỏi về dữ liệu rút ra sau buổi trao đổi với TS. Mai Đức Thọ. Các số liệu đã được đối chiếu với toàn văn 8 bài báo và mã nguồn PyPI.

Các câu hỏi cần giải quyết:

1. Tạo gói dữ liệu kiểu gì?
2. Xử lý mất cân bằng dữ liệu thế nào?
3. Dữ liệu có đặc điểm gì, từ đó chọn model nào cho hợp lý?
4. Lấy dữ liệu thế nào: hiểu dữ liệu thật trước, rồi mới tạo dữ liệu tổng hợp?
5. Chuẩn hóa dữ liệu ra sao?

Tóm tắt câu trả lời:

- **Quyết định gốc là chọn lớp âm.** Đề xuất dùng chính các tên gói thật mà LLM gợi ý trong cùng lượt sinh code (gọi là N2). Nhãn nên có 4 loại thay vì 2.
- **Mất cân bằng có hai loại.** Khi train thì nhẹ (5–22% mẫu dương), xử lý bằng class weight. Khi triển khai thì nặng, xử lý bằng cách báo cáo TPR@1%FPR và Precision theo tỷ lệ thực, không cân bằng lại tập test.
- **Tín hiệu chủ yếu nằm ở cấp từ, không phải lỗi gõ.** Chỉ 13,4% tên ảo giác cách tên thật 1–2 ký tự. Vì vậy cần so 1D-CNN ký tự với baseline n-gram và một mô hình subword.
- **Có nguồn dữ liệu công khai dùng được ngay** (0pstech, CC BY 4.0, 1.066 tên PyPI). Phần còn lại tự sinh theo quy trình của Spracklen, với snapshot registry mới.
- **Chuẩn hóa theo PEP 503 cho cả hai lớp.** Ràng buộc tấn công phải tính thêm luật chặn tên gần giống của PyPI (ultranormalization).

## 1. Tạo gói dữ liệu kiểu gì: định nghĩa các lớp

Đề xuất dùng **N2 làm lớp âm chính**, và gán nhãn 4 loại thay vì 2. Lớp dương đã rõ: tên do LLM bịa ra. Lớp âm thì có 3 lựa chọn:

| Lớp âm | Ưu điểm | Nhược điểm |
| --- | --- | --- |
| N1. Tên lấy ngẫu nhiên trên toàn PyPI | Dễ lấy | Phân bố khác hẳn lớp dương (nhiều tên rác, tên cá nhân). Mô hình dễ học “phong cách” thay vì học “đáng ngờ” |
| **N2. Tên gói thật do chính LLM gợi ý trong cùng lượt sinh code** | Cùng nguồn, cùng phân bố với lớp dương. Có sẵn miễn phí khi tự sinh dữ liệu | Thiên về gói phổ biến |
| N3. Top-N gói phổ biến | Sạch | Quá dễ phân biệt |

N1 (lấy mẫu) và các gói mới trên RSS PyPI vẫn dùng để đo FPR thực tế. Bằng chứng lựa chọn này quan trọng: CharBot ghi nhận chỉ cần đổi danh sách tên miền lành từ Alexa sang Qname, kết quả phát hiện đã khác đáng kể.

**Nhãn nên có 4 loại:**

| Nhãn | Ví dụ | Tra registry bắt được không? |
| --- | --- | --- |
| Tên thật, đúng ý | `requests`, `numpy` | Không cần bắt |
| Tên không tồn tại (404) | `vectorcache`, `chromastore` | Có |
| Tên module hoặc tên nhầm, nhưng đã có người đăng ký | `pil` (Pillow), `skimage` (scikit-image), `faiss` (faiss-cpu) | **Không**, registry trả về 200 |
| Tên của hệ sinh thái khác | 8,7% tên Python bịa là gói npm có thật | Tuỳ hệ sinh thái |

Loại thứ ba là lý do D0 cần tồn tại. Trong Names Can Hurt, một nửa số tên bị gắn cờ là tên đã có người đăng ký. Tra registry không bắt được các tên này. Đây là câu trả lời mạnh nhất cho câu hỏi “vì sao cần ML”.

**Mỗi bản ghi trong gói dữ liệu nên có các trường:**

- `name_raw`, `name_normalized`, `ecosystem`
- `label` (4 loại ở trên), `label_source` (tự động hay kiểm thủ công)
- `source_model`, `prompt_id`, `heuristic` (H1/H2/H3), `temperature`, `repeat_count`
- `first_seen`, `registry_status`, `check_date`
- `nearest_real_pkg`, `edit_distance`, `group_id` (nhóm tên gần giống, dùng khi chia tập), `split`

## 2. Mất cân bằng dữ liệu

Cần tách hai loại mất cân bằng: khi train thì xử lý bằng trọng số lớp, khi triển khai thì xử lý bằng cách chọn đúng thước đo.

**Khi train.** Với lớp âm N2, tỷ lệ dương là tỷ lệ tự nhiên: 5,2% với model thương mại, 21,7% với model mở (Spracklen). Model 2026 ở mức 4,62–6,10% (Churilov). Cách xử lý:

- Dùng `class_weight` hoặc weighted sampler, có thể thêm focal loss.
- **Không dùng SMOTE.** SMOTE nội suy trong không gian đặc trưng, nên mẫu sinh ra không phải tên gói hợp lệ. Điều này mâu thuẫn với ràng buộc problem-space của chính đề cương.
- Không nhân bản tên trước khi chia tập.
- Không tăng cường dữ liệu bằng nhiễu ký tự ở Giai đoạn 1. Làm vậy là đã ngầm huấn luyện đối kháng, khiến so sánh D0 với D′ mất ý nghĩa.

**Khi triển khai (base rate).** Ngoài đời, tên đáng ngờ hiếm hơn nhiều. Không cân bằng lại tập test. Báo cáo TPR@1%FPR và PR-AUC, rồi quy ra Precision theo tỷ lệ thực π:

```math
\text{Precision} = \frac{\text{TPR} \cdot \pi}{\text{TPR} \cdot \pi + \text{FPR} \cdot (1 - \pi)}
```

Ví dụ với TPR = 0,90 và FPR = 1%: π = 5% cho Precision khoảng 83%; π = 0,1% chỉ còn khoảng 8%. ODFA gặp đúng hiện tượng này: Precision chỉ 18,73% ở FPR 1% khi triển khai thật. Arp et al. gọi đây là lỗi P8 (Base Rate Fallacy).

**Cỡ mẫu cần cho tập test** (khoảng tin cậy 95%):

| Đại lượng cần đo | Sai số mong muốn | Số mẫu cần |
| --- | --- | --- |
| FPR quanh 1% | ±0,2 điểm % | khoảng 10.000 tên âm |
| TPR quanh 90% | ±2,6 điểm % | khoảng 500 tên dương **duy nhất** |

Names Can Hurt cũng tự nhận: mỗi lát test chỉ có 2–12 mẫu dương, cần khoảng 30 mẫu mới kết luận được.

**Chống rò rỉ khi chia tập.** Names Can Hurt chia ngẫu nhiên theo dòng, làm 72,9% dòng test trùng tên với tập train. Họ phải chạy lại với cách chia theo tên duy nhất. Quy trình đề xuất:

1. Khử trùng lặp sau khi chuẩn hóa.
2. Gom tên gần giống thành nhóm (edit distance ≤ 2 hoặc cùng gốc), rồi chia theo nhóm.
3. Thêm hai kiểu chia phụ: theo model nguồn (train 3 LLM, test LLM thứ 4) và theo thời gian. Theo Spracklen, 81% tên bịa chỉ do một model sinh ra, nên chia theo model sẽ khó nhưng có ý nghĩa.

## 3. Đặc điểm dữ liệu và lựa chọn model

Phần lớn tên ảo giác là tổ hợp từ nghe hợp lý, không phải lỗi gõ. Vì vậy cần so 1D-CNN ký tự với một baseline n-gram và một mô hình subword trước khi chốt D0.

**Dữ liệu có 3 đặc điểm:**

- **Chuỗi ngắn, bảng chữ nhỏ.** Sau chuẩn hóa PyPI chỉ còn `[a-z0-9-]`, tức 37 ký tự.
- **Ít lỗi gõ.** Trên 76.489 tên Python bịa (Spracklen): 13,4% cách tên thật gần nhất 1–2 ký tự, 37,9% cách 3–5, 48,6% cách từ 6 trở lên.
- **Tín hiệu từ tên có thể yếu.** Trong Names Can Hurt, 82% tín hiệu đến từ 2 đặc trưng metadata: số maintainer (57,6%) và có link GitHub hay không (24,5%). Một luật OR đơn giản trên hai đặc trưng này đạt F1 ngang Random Forest.

**Hệ quả:** cần làm thí nghiệm pilot đo **trần tín hiệu của tên** ngay từ đầu. Nếu mô hình chỉ dùng tên mà không phân biệt được N2 với lớp dương, Giai đoạn 2 mất nền.

**Bộ model so sánh đề xuất:**

| Model | Vai trò | Có gradient cho Faster-GCG? |
| --- | --- | --- |
| LogReg hoặc XGBoost trên TF-IDF n-gram ký tự (1–5) cùng đặc trưng thủ công | Baseline mạnh, dễ giải thích. Arp et al. (lỗi P6) cảnh báo việc thiếu baseline đơn giản | Không, chỉ tấn công được kiểu black-box |
| 1D-CNN ký tự (D0 theo đề cương) | Model chính | Có |
| fastText subword, hoặc CodeBERT/transformer nhỏ | Kiểm tra giả thuyết “tín hiệu nằm ở cấp từ” | Có |

Đặc trưng thủ công có thể lấy theo Names Can Hurt: độ dài, số đoạn, chữ số, tiền tố `py-`/`python-`, từ “hype” (super, pro, ai), từ chung chung (helper, tools), độ giống với top-15.000 tên PyPI.

Quy tắc chọn: nếu baseline n-gram đã gần trần, mạng nơ-ron không đáng thêm phức tạp. Khi đó nên báo cáo thẳng, vì đó cũng là một kết quả.

## 4. Nguồn và cách lấy dữ liệu

Hiểu dữ liệu thật trước bằng các bộ công khai, sau đó mới tự sinh theo quy trình của Spracklen, với snapshot registry mới.

### 4.1. Nguồn công khai để làm EDA

| Nguồn | Nội dung | Giấy phép / truy cập |
| --- | --- | --- |
| [0pstech/slopsquatting-dataset](https://github.com/0pstech/slopsquatting-dataset) | 2.170 tên (PyPI 1.066, npm 820) tính đến 05/11/2026. Có trường `models`, `tasks`, `first_seen`, `registry_status`. Không dùng prompt đối kháng | CC BY 4.0. Nguồn tốt nhất hiện có |
| [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset) | Tên quan sát từ traffic thật của AI agent, 19 hệ sinh thái | CC-BY-NC-SA |
| [Trend Micro](https://github.com/trendmicro/slopsquatting) | 100 tác vụ web-dev, file JSONL gồm model, task, dependencies, tên ảo giác | MIT |
| [Spracklen](https://github.com/Spracks/PackageHallucination) | 205.474 tên duy nhất. Repo chỉ công bố prompt và danh sách gói thật | Phải xin quyền. Đã gửi email, sau 1 tuần chưa phản hồi; kế hoạch không phụ thuộc nguồn này |
| [Churilov](https://github.com/churik5/slopsquatting-replication-2026) | 127 tên mà cả 5 model cùng bịa | Đang giữ lại theo cam kết công bố có trách nhiệm |

EDA cần xem: phân bố độ dài và số đoạn, ký tự phân tách, các từ hay gặp, khoảng cách tới gói thật gần nhất, và tỷ lệ 4 loại nhãn. Kết quả EDA cũng là thước đo để kiểm tra dữ liệu tự sinh có lệch phân bố không.

### 4.2. Tự sinh dữ liệu

Dùng 4 bộ prompt của Spracklen (`SO_AT`, `SO_LY`, `LLM_AT`, `LLM_LY`; tổng 20.163 câu từ Stack Overflow và 19.806 câu do LLM sinh). Trích tên gói bằng đủ 3 heuristic của Spracklen:

1. H1: đọc lệnh `pip install` trong code. Lệnh này chỉ xuất hiện ở 7% output, nên không đủ nếu dùng riêng.
2. H2: đưa đoạn code vừa sinh lại cho model, hỏi “cần cài gói nào”.
3. H3: hỏi model “tác vụ này cần gói nào”.

**Không lấy tên từ câu lệnh `import`.** Tên module khác tên gói: `cv2` là opencv-python, `sklearn` là scikit-learn. Churilov có đọc `import`, và các “ảo giác” nhiều nhất của bài là tên module bị nhầm: `rest-framework`, `objc`, `opengl`, `mpl-toolkits`.

Cần ghi lại mọi tên được gợi ý, cả thật lẫn bịa, để có lớp N2. Lưu cả tần suất lặp lại: theo Spracklen, 43% tên bịa lặp lại cả 10/10 lần, 39% không lặp lại lần nào. Tên lặp lại nhiều mới là mục tiêu thật của kẻ tấn công.

**Không có dữ liệu Spracklen vẫn đủ, nhưng phải đo sản lượng bằng pilot.** Hai mốc ước tính chênh nhau nhiều:

- Cận trên, theo cách làm của Spracklen (H1–H3): mỗi code sample cho khoảng 3,9 lượt tên gói (khoảng 2,24 triệu lượt trên 576.000 sample), và 47% lượt ảo giác là tên duy nhất. Với 10.000 prompt mỗi model, PHR 5% cho khoảng 900 tên duy nhất; PHR 20% (model mở) cho khoảng 3.600.
- Cận dưới, theo Churilov (chỉ trích từ code, không có H2/H3): khoảng 40.000 prompt mỗi model ở PHR 4,62% cho hơn 1.300 lượt ảo giác, tức chỉ vài trăm tên duy nhất.

Pilot cần đo **số tên ảo giác duy nhất trên 1.000 prompt** cho từng model, rồi mới quyết định quy mô. Model mở rẻ như CodeLlama-13B vừa cho nhiều mẫu dương vừa tốn ít chi phí nhất.

### 4.3. Xác minh nhãn

- **Tự chụp danh sách gói thật, có ghi ngày.** Danh sách của Spracklen chụp ngày 10/01/2024 (500.565 tên PyPI). Churilov vẫn dùng danh sách này cho dữ liệu tháng 4/2026, nên gói đăng ký sau 01/2024 bị tính nhầm là ảo giác.
- **Tên bịa nhưng sau đó có người đăng ký** (`first_seen` trước ngày đăng ký) rất có thể là gói slopsquat thật. Không xếp vào lớp âm.
- **Kiểm thủ công một mẫu** để báo cáo độ chính xác của nhãn. Nên kiểm đủ nhiều tên bị gắn cờ: Library Hallucinations chỉ kiểm 24 tên, nên con số 95,8% có khoảng tin cậy rộng 79,8–99,3%.
- **Với npm:** API replication cũ đã ngừng từ 29/05/2025, cần kiểm tra cách tải danh sách tên mới trước khi viết pipeline.

### 4.4. Dữ liệu tổng hợp (synthetic)

Nếu dùng LLM sinh thêm tên giả cho đủ số lượng:

- Chỉ dùng để train, không bao giờ dùng để test. Tập test chỉ chứa ảo giác thật.
- Không dùng cùng cơ chế với tấn công LLM-guided ở Giai đoạn 2. Nếu dùng, D0 đã được huấn luyện ngầm trên kiểu tấn công black-box, làm sai lệch ASR. Arp et al. gọi dạng này là lỗi P9 (chỉ đánh giá trong phòng thí nghiệm).

## 5. Chuẩn hóa dữ liệu

Chuẩn hóa cả hai lớp giống hệt nhau theo quy tắc của registry. Ràng buộc tấn công phải tính thêm luật chặn tên gần giống của PyPI.

### 5.1. PyPI

Trước hết bóc bỏ version specifier, extras (`requests[security]>=2.0`), URL, `git+…`, đường dẫn local và comment. Sau đó chỉ giữ tên hợp lệ theo regex của [PyPA](https://packaging.python.org/en/latest/specifications/name-normalization/), dùng với `re.IGNORECASE`. Regex kết thúc bằng `\Z`, không phải `$` (PyPA sửa từ tháng 8/2025):

```
^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])\Z
```

Rồi chuẩn hóa theo PEP 503:

```python
import re

def normalize(name):
    return re.sub(r"[-_.]+", "-", name).lower()
```

### 5.2. Luật chặn tên gần giống của PyPI (ultranormalization)

Mã nguồn PyPI ([warehouse](https://github.com/pypi/warehouse)) có hàm `ultranormalize_name`: bỏ `.` `_` `-`, đổi `l`/`i` thành `1`, `o` thành `0`, rồi đổi sang chữ thường. Nếu tên mới trùng với project đã có sau phép biến đổi này, PyPI từ chối đăng ký (`ProjectNameUnavailableSimilarError`). PyPI còn có danh sách tên cấm. Theo Churilov, hai lớp chặn này loại 68/109 tên mà cả 5 model cùng bịa.

Hệ quả cho Giai đoạn 2: bước 5 trong kịch bản Faster-GCG phải kiểm tra thêm luật này. Các phép đổi kiểu `o↔0` hay `l↔1` thường vô dụng với kẻ tấn công vì bị chặn. Đây là ràng buộc problem-space cụ thể và kiểm chứng được, nên đưa vào đề cương.

### 5.3. npm

- Chữ thường, tối đa 214 ký tự, an toàn cho URL, không bắt đầu bằng `.` hoặc `_` ([validate-npm-package-name](https://github.com/npm/validate-npm-package-name)).
- Tên scoped `@scope/name`: tách scope thành đặc trưng riêng. Nhiều tên scoped không đăng ký được, ví dụ `@ember/*` chỉ tổ chức Ember mới dùng được.
- Registry còn tên cũ có chữ hoa, nên phải chuẩn hóa cả lớp âm.

### 5.4. Ba điểm phương pháp

1. **Chuẩn hóa hai lớp y hệt nhau.** LLM hay viết tên kiểu import với dấu `_`, còn PyPI dùng `-`. Nếu không chuẩn hóa, mô hình chỉ cần học “có dấu `_` thì là ảo giác”. Arp et al. gọi đây là lỗi P4 (tương quan giả).
2. **Chỉ học tham số chuẩn hóa trên tập train.** Từ vựng n-gram, trọng số TF-IDF, danh sách top-N dùng tính Levenshtein đều chỉ lấy từ tập train. Arp et al. gọi việc tính trên toàn bộ dữ liệu là lỗi P3 (data snooping).
3. **Mã hóa đầu vào:** bảng chữ 37 ký tự cộng PAD/UNK. Độ dài tối đa đặt theo p99 thực tế từ EDA, không đoán trước. Faster-GCG phải tìm kiếm trên dạng đã chuẩn hóa, vì đổi `_` thành `-` không tạo ra tên mới.

## 6. Đính chính số liệu sau khi đọc toàn văn

Có 4 chỗ trong các bản khảo sát trước cần sửa. Các số liệu còn lại đã khớp với bản gốc.

| Số liệu | Ghi trước đây | Bản gốc ghi |
| --- | --- | --- |
| Tỷ lệ lỗi gõ (Spracklen) | 13% là lỗi gõ lệch 1 ký tự | 13,4% có khoảng cách Levenshtein 1–2; 37,9% cách 3–5; 48,6% cách từ 6 trở lên |
| Cách trích tên (Spracklen) | Lấy từ `pip install` | 3 heuristic H1–H3; `pip install` chỉ có ở 7% output; không dùng `import` |
| Độ chính xác nhãn (Library Hallucinations) | Kiểm thủ công 200 mẫu, đúng 95,8% | Lấy mẫu 200 response; 23/24 response bị gắn cờ là đúng; khoảng tin cậy Wilson 79,8–99,3% |
| Danh sách gói thật (Churilov) | Không nêu | Dùng lại danh sách Spracklen chụp 10/01/2024 cho dữ liệu tháng 4/2026 |

**Đã khớp với bản gốc:**

- **Spracklen:** PHR 19,7% (440.445 lượt); 205.474 tên duy nhất; 5,2% / 21,7%; 43% / 39% lặp lại; 8,7% (6.705/76.489) là gói npm; gói đã xóa chỉ chiếm 0,17%.
- **Churilov:** PHR 4,62–6,10%; dùng Wilson, Holm và χ²; 127 tên cả 5 model cùng bịa, 53 tên còn đăng ký được.
- **ODFA:** 95,27% → 24,30% → 86,81%; Precision 18,73% ở FPR 1%; 2,18 cảnh báo sai/ngày; 3.190 gói độc hại + 3.368 gói bình thường; bài nêu FPR 1% là “common practice”.
- **CharBot:** sau retrain, LSTM.MI chỉ đạt 55,19% / 52,67% ở FPR 0,1%. Bài xếp “White-box adversarial training” vào hướng tương lai, đúng như điểm tính mới (3) trong báo cáo v3.
- **Names Can Hurt:** 82% tín hiệu = 57,6% + 24,5% từ hai đặc trưng metadata.

## 7. Kế hoạch làm tiếp và câu hỏi cần thầy cho ý kiến

Bước tiếp theo là một thí nghiệm pilot nhỏ để đo trần tín hiệu của tên, trước khi sinh dữ liệu đầy đủ.

- [ ] Tải bộ 0pstech và Trend Micro. Không chờ dữ liệu Spracklen: email đã gửi, sau 1 tuần chưa phản hồi.
- [ ] Chụp danh sách gói PyPI hiện tại, có ghi ngày.
- [ ] EDA trên dữ liệu thật. Chốt định nghĩa lớp âm (N2), 4 loại nhãn và schema dữ liệu.
- [ ] Pilot: khoảng 300 prompt, 2 model rẻ, cộng bộ 0pstech. Train baseline n-gram để đo trần tín hiệu của tên.
- [ ] Nếu trần đủ cao: sinh dữ liệu đầy đủ, chia tập theo nhóm, theo model và theo thời gian.
- [ ] Cập nhật bước 5 của kịch bản Faster-GCG với luật ultranormalization của PyPI.

**Câu hỏi cần thầy cho ý kiến:**

1. Dùng N2 (tên thật do LLM gợi ý) làm lớp âm chính có phù hợp không?
2. Nếu pilot cho thấy tên chứa ít tín hiệu, có nên thêm đặc trưng ngữ cảnh (prompt, tác vụ) hoặc metadata không? Việc này sẽ đổi phạm vi “bộ phát hiện chỉ dùng tên” trong đề cương.
3. Có giữ npm trong phạm vi chính không, hay để sang phần mở rộng?

## Tài liệu tham khảo

Các bài đã đọc toàn văn:

- [Spracklen et al., We Have a Package for You! (USENIX Security 2025)](https://arxiv.org/abs/2406.10279)
- [Churilov, The Range Shrinks, the Threat Remains (2026)](https://arxiv.org/abs/2605.17062)
- [Raj & Sahu, Names Can Hurt (2026)](https://arxiv.org/abs/2608.23897)
- [Twist et al., Library Hallucinations in LLM-Generated Code (2026)](https://arxiv.org/abs/2509.22202)
- [Hillah et al., Bayesian-Calibrated Detection of Hallucinated Package Imports (2026)](https://arxiv.org/abs/2606.13918)
- [One Detector Fits All (ODFA)](https://arxiv.org/abs/2512.04338)
- [Peck et al., CharBot (IEEE Access 2019)](https://arxiv.org/abs/1905.01078)
- [Arp et al., Dos and Don'ts of Machine Learning in Computer Security (USENIX Security 2022)](https://arxiv.org/abs/2010.09470)

Dữ liệu và đặc tả kỹ thuật:

- [0pstech/slopsquatting-dataset](https://github.com/0pstech/slopsquatting-dataset) · [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset) · [Trend Micro slopsquatting](https://github.com/trendmicro/slopsquatting) · [Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination)
- [PyPA: Name normalization](https://packaging.python.org/en/latest/specifications/name-normalization/) · [PyPI warehouse: ultranormalize_name](https://github.com/pypi/warehouse/blob/main/warehouse/migrations/versions/d18d443f89f0_ultranormalize_name_function.py) · [validate-npm-package-name](https://github.com/npm/validate-npm-package-name)
- [Thông báo thay đổi API replication của npm (02/2025)](https://github.blog/changelog/2025-02-26-changes-and-deprecation-notice-for-npm-replication-apis/)
