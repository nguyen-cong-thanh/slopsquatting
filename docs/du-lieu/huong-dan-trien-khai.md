# Hướng dẫn triển khai theo hai mục tiêu

**Ngày:** 09/11/2026 · **Dựa trên:** [thiet-ke-du-lieu.md](thiet-ke-du-lieu.md), [bao-cao-thu-nghiem-pilot.md](bao-cao-thu-nghiem-pilot.md)

Tài liệu này là danh sách việc cần làm, theo thứ tự. Mỗi bước có lệnh chạy, sản phẩm đầu ra và **điều kiện đạt** để chuyển sang bước sau.

| Mục tiêu | Trạng thái sau pilot |
| --- | --- |
| **1.** Có dữ liệu đầu vào, đo đạc, chọn mô hình, báo cáo định lượng | Đã có quy trình chạy được và số liệu sơ bộ. Còn thiếu dữ liệu tự sinh bằng LLM và 3 đặc trưng metadata |
| **2.** Chốt kế hoạch thành bài báo có tính mới | Đã có giả thuyết H1–H4, cách định vị tính mới, lộ trình. Còn thiếu bộ biến thể và thí nghiệm phòng thủ |

## Chuẩn bị chung (làm một lần)

**Phần cứng:** một máy GPU ≥ 24 GB (ví dụ RTX 4090 hoặc A10/L4 thuê theo giờ) để chạy LLM cục bộ. Máy không GPU vẫn chạy được mọi bước còn lại.

**Môi trường:**

```bash
pip install scikit-learn pandas xgboost torch rapidfuzz vllm
```

**Dữ liệu ngoài** (đặt trong `work/`, không commit):

```bash
mkdir -p work/ext/own && cd work/ext
for r in 0pstech/slopsquatting-dataset trendmicro/slopsquatting cuttalo/depscope-hallucinations-dataset Spracks/PackageHallucination; do git clone --depth 1 https://github.com/$r; done
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/ossf/malicious-packages ossf
cd ..
```

```bash
(cd ext/ossf && git ls-tree -d --name-only HEAD osv/malicious/pypi/ | sed 's#.*/##') > ossf_pypi.txt
curl -s -H 'Accept: application/vnd.pypi.simple.v1+json' https://pypi.org/simple/ -o simple.json
python ../experiments/collect/prepare_prompts.py ext/PackageHallucination/Data/Python prompts.txt
```

Kết quả mong đợi: `prompts.txt` có 18.074 câu hỏi (18.033 câu của Spracklen sau khi tách 8 dòng chứa nhiều câu đánh số).

---

## Hướng dẫn cho LLM thương mại

### Chọn mô hình

Tiêu chí, theo thứ tự ưu tiên:

1. **Được lập trình viên dùng nhiều** (kết quả có ý nghĩa thực tế).
2. **Sinh đủ tên bịa:** ≥ 500 tên bịa không trùng trên ≤ 18.074 câu hỏi.
3. **Chi phí thấp, có Batch API** (gửi theo lô, không cần trả lời ngay, giảm giá).
4. **Có mã phiên bản cố định** để người khác chạy lại được.

| Ứng viên | Bằng chứng hiện có | Ưu điểm | Rủi ro |
| --- | --- | --- | --- |
| Dòng GPT "mini" của OpenAI | Churilov (2026): GPT-5.4-mini có tỷ lệ bịa cao nhất trong 5 LLM thế hệ mới (6,10%). 0pstech: gpt-4o-mini đóng góp 1.713/2.197 tên | Nhiều tên bịa nhất trên mỗi câu hỏi; dùng phổ biến | Cần tra giá hiện hành trên trang giá của OpenAI |
| Claude Haiku 5.5 (`claude-haiku-5-5`) | Churilov (2026): Claude Haiku 4.5 có tỷ lệ bịa thấp nhất (4,62%); 0pstech: claude-haiku-4.5 chỉ 143 tên | Rẻ: 0,10 USD / 1 triệu token vào, 0,50 USD / 1 triệu token ra; Batch API giảm 50% | Có thể không đủ 500 tên riêng |
| Gemini Flash | 0pstech: gemini-2.5-flash 339 tên | Có endpoint tương thích OpenAI | Cần tra giá hiện hành |

**Đề xuất (tối ưu token, chốt ở mục [Phương án chốt](#phương-án-chốt-tối-ưu-token)):** thử **Claude Haiku 5.5 trước** vì rẻ nhất. Chỉ thử GPT mini nếu Haiku không đạt ngưỡng 500 tên bịa không trùng. Như vậy không tốn token cho ứng viên thứ hai khi không cần.

### Chạy với OpenAI hoặc Gemini (API tương thích OpenAI)

Dùng `generate.py`, chỉ đổi biến môi trường:

```bash
export LLM_BASE_URL=https://api.openai.com/v1 LLM_API_KEY=<khóa> LLM_MODEL=<mã mô hình có ngày phiên bản>
python ../experiments/collect/generate.py gen --prompts prompts.txt --index simple.json --out ext/own/pilot_gpt.jsonl --limit 500 --workers 4
```

Với Gemini, đặt `LLM_BASE_URL` là endpoint tương thích OpenAI của Google (`https://generativelanguage.googleapis.com/v1beta/openai`). Khi chạy toàn bộ, nên dùng Batch API của nhà cung cấp để giảm chi phí; `generate.py` hiện gọi từng câu.

### Chạy với Claude (Message Batches API, giảm 50%)

Dùng [`generate_claude_batch.py`](../../experiments/collect/generate_claude_batch.py) (SDK chính thức `anthropic`, cài bằng `pip install anthropic`, khóa trong `ANTHROPIC_API_KEY`).

Gửi lô chạy thử:

```bash
python ../experiments/collect/generate_claude_batch.py submit-gen --prompts prompts.txt --limit 500 --manifest pilot_haiku.manifest.json
```

Lô thường xong trong vòng 1 giờ (tối đa 24 giờ). Thu kết quả và gắn nhãn:

```bash
python ../experiments/collect/generate_claude_batch.py collect --manifest pilot_haiku.manifest.json --index simple.json --out ext/own/pilot_haiku.jsonl
```

Lệnh `collect` in ra số token thực tế đã dùng, dùng để ngoại suy chi phí chạy toàn bộ. Hỏi lại để thu biến thể (bước 2.2):

```bash
python ../experiments/collect/generate_claude_batch.py submit-requery --src ext/own/full_haiku.jsonl --n 10 --max-names 500 --manifest var_haiku.manifest.json
```

### Thiết lập cần cố định và ghi vào bài báo

| Thiết lập | Giá trị |
| --- | --- |
| Mã mô hình | Đúng chuỗi đã gọi, kèm ngày chạy |
| System prompt | `You are a helpful Python programming assistant. Answer with complete, runnable Python code only, without explanation.` (giống nhau cho mọi LLM; "chỉ code" để giảm token ra) |
| Độ dài tối đa | 1.024 token (API tương thích OpenAI); 3.000 token với Claude vì token suy luận cũng được tính vào giới hạn. Tên gói nằm ở đầu mã (`pip install`, `import`) nên cắt phần cuối không làm mất tên; lệnh `collect` đếm số câu bị cắt (`stop_max_tokens`) để kiểm tra |
| Nhiệt độ | 0,7 với API tương thích OpenAI. Claude API hiện không nhận tham số `temperature`; dùng cách lấy mẫu mặc định và ghi rõ trong bài |
| Mức suy luận (Claude) | `low` (mặc định của script) để giảm token suy luận; ghi rõ trong bài |

### Phương án chốt (tối ưu token)

| Vai trò | Mô hình | Lý do |
| --- | --- | --- |
| LLM chạy cục bộ (nguồn dữ liệu chính) | **Qwen2.5-Coder-7B-Instruct** trên vLLM | Không tốn token trả phí; LLM mã nguồn mở bịa nhiều hơn (21,7% theo Spracklen và cộng sự) nên dễ đạt quy mô. Chạy toàn bộ 18.074 câu và toàn bộ phần hỏi lại ở đây |
| LLM thương mại | **Claude Haiku 5.5** qua Batch API; dự phòng GPT mini | Rẻ nhất trong các mô hình có giá đã kiểm tra được (0,10 / 0,50 USD mỗi 1 triệu token, Batch giảm 50%) |

Sáu cách giảm token, theo thứ tự tác động:

1. **Dồn khối lượng sang LLM cục bộ.** Mọi thử nghiệm lặp lại, sửa lỗi bộ tách tên và hỏi lại số lượng lớn đều chạy trên Qwen trước.
2. **Thử ứng viên theo thứ tự, không song song.** Haiku 500 câu trước; chỉ thử GPT mini khi Haiku ngoại suy được < 500 tên bịa không trùng.
3. **Chỉ in code** (system prompt ở trên) và **giới hạn token ra**; đặt `--effort low` với Claude.
4. **Batch API** cho mọi lượt gọi thương mại (giảm 50%).
5. **Chạy từng đợt 2.000 câu và dừng sớm.** Hai script dùng cùng một thứ tự xáo cố định, nên các đợt `--start`/`--limit` không trùng nhau. Sau mỗi đợt chạy `count_unique.py`; dừng khi đạt ≥ 500 tên bịa không trùng, hoặc khi một đợt mới thêm < 5% tên mới.
6. **Hỏi lại trên LLM thương mại với quy mô nhỏ hơn:** 250 tên × 10 lần thay vì 500 tên; phần đầy đủ 500 tên chạy trên Qwen.

Lệnh theo đợt với Claude (đợt 2 bắt đầu ở câu 2.000):

```bash
python ../experiments/collect/generate_claude_batch.py submit-gen --prompts prompts.txt --start 2000 --limit 4000 --manifest haiku_b2.manifest.json
```

```bash
python ../experiments/collect/generate_claude_batch.py collect --manifest haiku_b2.manifest.json --index simple.json --out ext/own/full_haiku_b2.jsonl
```

```bash
python ../experiments/collect/count_unique.py ext/own/full_haiku_*.jsonl
```

### Ước tính chi phí

Chi phí ≈ số lượt × (token vào × giá vào + token ra × giá ra) × (0,5 nếu dùng Batch).

Ví dụ Claude Haiku 5.5 với các thiết lập trên, khoảng 23.000 lượt (18.074 câu + 5.000 lượt hỏi lại), giả định trung bình 100 token vào và 400 token ra mỗi lượt:

- Token vào: 2,3 triệu × 0,10 USD ≈ 0,23 USD.
- Token ra: 9,2 triệu × 0,50 USD ≈ 4,6 USD.
- Qua Batch API (giảm 50%): **khoảng 2,4 USD**; ít hơn nữa nếu dừng sớm.

Đây là ước tính; dùng số token do lệnh `collect` báo sau lần chạy thử 500 câu để tính lại. Với OpenAI và Gemini, áp cùng công thức với giá trên trang giá của nhà cung cấp.

### Lưu ý

- Không gửi dữ liệu cá nhân. Bộ câu hỏi chỉ gồm câu hỏi lập trình công khai.
- Không đăng ký tên gói nào. Danh sách tên bịa chỉ lưu cục bộ cho tới khi báo cho PyPI Security.

---

## Mục tiêu 1: Dữ liệu, đo đạc, chọn mô hình, báo cáo định lượng

### Bước 1.1 — Chạy thử nhỏ để chốt LLM và quy mô (2–3 ngày)

Khởi động LLM cục bộ:

```bash
vllm serve Qwen/Qwen2.5-Coder-7B-Instruct --port 8000
```

Gửi 2.000 câu hỏi cho LLM cục bộ:

```bash
export LLM_BASE_URL=http://localhost:8000/v1 LLM_MODEL=Qwen/Qwen2.5-Coder-7B-Instruct
python ../experiments/collect/generate.py gen --prompts prompts.txt --index simple.json --out ext/own/pilot_qwen.jsonl --limit 2000
```

Lặp lại với LLM thương mại, `--limit 500`, theo [Hướng dẫn cho LLM thương mại](#hướng-dẫn-cho-llm-thương-mại).

**Đo ngay trên file đầu ra:**

| Đại lượng | Cách tính | Dùng để |
| --- | --- | --- |
| Tỷ lệ tên bịa theo lượt gợi ý | Σ `modulenotfound_count` / Σ `module_count` | So với Spracklen (5,2% thương mại; 21,7% mã nguồn mở) |
| Số tên bịa không trùng / 1.000 câu hỏi | Đếm tên khác nhau trong `modulenotfound` | Ngoại suy quy mô cần chạy để đạt 500 tên mỗi LLM |
| Tỷ lệ báo nhầm của bộ tách tên | Kiểm tra tay 100 tên bịa ngẫu nhiên | Phải ≤ 10%; lớn hơn thì sửa quy tắc tách trong `generate.py` |

**Điều kiện đạt:** mỗi LLM ngoại suy được ≥ 500 tên bịa không trùng trong phạm vi 18.074 câu. Nếu LLM thương mại không đạt, chọn LLM thương mại khác hoặc thêm bộ câu hỏi mới (bước 1.2), không hạ mục tiêu.

**Lưu ý:** `generate.py` chỉ coi tên trong câu `import` là bịa khi câu trả lời không có lệnh `pip install` nào, để tránh nhầm `import cv2` (gói thật là `opencv-python`). Bước kiểm tra tay ở trên là bắt buộc.

### Bước 1.2 — Sinh dữ liệu đầy đủ (1–2 tuần)

```bash
python ../experiments/collect/generate.py gen --prompts prompts.txt --index simple.json --out ext/own/full_<llm>.jsonl
```

Chạy cho cả hai LLM. Lý do cần tên thật và tên bịa **trong cùng câu trả lời**: pilot cho thấy khi hai lớp lấy từ hai nguồn khác nhau, TPR bị thổi phồng (0,548 theo kiểm định chéo so với 0,367 trên tập giữ riêng).

**Điều kiện đạt:**

- ≥ 4.000 tên bịa không trùng; ≥ 500 tên riêng mỗi LLM.
- ≥ 1.521 tên thật do LLM gợi ý dùng làm tập giữ riêng (đủ để đặt ngưỡng FPR = 1% với sai số ±0,5%).

### Bước 1.3 — Bổ sung metadata còn thiếu (2–3 ngày)

| Đặc trưng | Nguồn | Cách lấy |
| --- | --- | --- |
| Lượt tải 90 ngày, số ngày có tải | BigQuery `bigquery-public-data.pypi.file_downloads` | [`experiments/collect/downloads.sql`](../../experiments/collect/downloads.sql); cần tài khoản GCP (bậc miễn phí 1 TB quét/tháng là đủ nếu lọc ngày) |
| Số sao, ngày tạo repo, số người đóng góp | GitHub REST API | Cần token (5.000 lượt/giờ); chỉ với gói có link repo |
| Link mã nguồn được PyPI xác minh / Trusted Publishing | Trang dự án PyPI hoặc API Integrity (PEP 740) | Đặc trưng **khó làm giả** quan trọng nhất cho phần phòng thủ |

**Điều kiện đạt:** ≥ 95% gói có trên PyPI có đủ metadata.

### Bước 1.4 — Dựng bộ dữ liệu và chạy đo (1 ngày)

```bash
python ../experiments/pilot/build_dataset.py ext .
python ../experiments/pilot/run_experiments.py dataset.csv . ext/slopsquatting/slopsquatting.jsonl
```

`build_dataset.py` tự đọc mọi file trong `ext/own/*.jsonl`. Trước khi chạy cần sửa hai chỗ trong `run_experiments.py`:

1. Thay nhóm `real_ref` bằng tên thật từ dữ liệu tự sinh làm lớp âm huấn luyện; tách 1.521 tên thật làm tập giữ riêng chính.
2. Phép kiểm thử chéo: huấn luyện trên tên của LLM A, kiểm thử trên LLM B và ngược lại (thay cho chia GPT / Gemini+Claude của pilot).

### Bước 1.5 — Chọn mô hình theo quy tắc định trước

Ghi rõ quy tắc **trước khi** xem kết quả để tránh chọn theo kết quả:

1. Chỉ số chính: TPR@1%FPR trên tập giữ riêng chính.
2. Hai mô hình chênh nhau không có ý nghĩa thống kê (khoảng tin cậy bootstrap 95% chồng lấn) → chọn mô hình có TPR kiểm thử chéo LLM cao hơn.
3. Vẫn hòa → chọn mô hình có FPR trên gói mới (≤ 60 ngày) thấp hơn, rồi đến mô hình nhanh hơn.
4. Bắt buộc giữ ít nhất một mạng nơ-ron (CharCNN) cho mốc tấn công dùng gradient.

Ứng viên từ pilot: tầng 1 là LR char n-gram và CharCNN; tầng 2 là Random Forest (chính) và XGBoost (đối chứng). Thêm fastText và CodeBERT ở bước này.

### Bước 1.6 — Báo cáo định lượng

Mỗi bảng kết quả phải có:

| Thành phần | Quy định |
| --- | --- |
| Cỡ mẫu | Ghi *n* dương, *n* âm của từng tập |
| Chỉ số | AUC-ROC, PR-AUC, TPR@1%FPR, FPR trên tập phụ (PyPI ngẫu nhiên, gói mới) |
| Khoảng tin cậy | Bootstrap 95% (≥ 1.000 lần ở bản cuối; pilot dùng 500) |
| So sánh hai mô hình | Bootstrap theo cặp cho hiệu TPR; McNemar cho quyết định tại cùng ngưỡng |
| Độ lặp lại | 5 seed ngẫu nhiên; báo trung bình ± độ lệch chuẩn |
| Ablation | Chỉ tên / chỉ metadata / cả hai |

Mẫu trình bày: dùng các bảng ở mục 4 của [bao-cao-thu-nghiem-pilot.md](bao-cao-thu-nghiem-pilot.md).

**Hoàn thành mục tiêu 1 khi:** có bảng chọn mô hình cuối trên dữ liệu tự sinh, đủ cỡ mẫu ở bước 1.2, có khoảng tin cậy và kiểm định.

---

## Mục tiêu 2: Kế hoạch thành bài báo có tính mới

### Bước 2.1 — Chốt tuyên bố tính mới (làm ngay)

Viết một đoạn cố định và dùng xuyên suốt:

> Chúng tôi đề xuất mô hình kẻ tấn công đầu tiên cho bộ phát hiện slopsquatting, trong đó kẻ tấn công chỉ được chọn **biến thể tên mà LLM thật sự gợi ý**, phải **đăng ký được trên PyPI**, và làm giả metadata trong **ngân sách có định giá**. Chúng tôi đo mức nguy hiểm bằng tỷ lệ né có trọng số tần suất (RER), cho thấy giả định "tự do sửa tên" của các nghiên cứu trước làm sai lệch mức nguy hiểm, và đề xuất bộ phát hiện bền vững theo chi phí.

Ranh giới với công trình đã có (không nhận các điểm này là mới):

- Chia đặc trưng metadata dễ/khó thao túng: MeMPtec (Halder và cộng sự, 2024).
- Huấn luyện đối kháng cho bộ phát hiện gói độc hại PyPI: Montaruli và cộng sự (2025).
- Bộ phát hiện hai tầng tra PyPI + mô hình: Raj và Sahu (2026).
- Tên bịa chung giữa nhiều LLM và kiểm tra khả năng đăng ký: Churilov (2026).

**Việc kiểm tra:** trước khi nộp bài, tìm lại trên arXiv và Google Scholar với các từ khóa "slopsquatting adversarial", "package hallucination detector evasion", "hallucinated package robust". Phạm vi khảo sát hiện tại khoảng 24 bài.

### Bước 2.2 — Bộ biến thể (đóng góp dữ liệu chính, 1 tuần)

```bash
python ../experiments/collect/generate.py requery --src ext/own/full_<llm>.jsonl --index simple.json --out ext/own/variants_<llm>.jsonl --n 10 --max-names 500
```

Mỗi dòng đầu ra có: câu hỏi, tên gốc, số lần tên gốc lặp lại trong 10 lần, mọi tên sinh ra và tần suất.

**Đo:**

- Phân phối số lần lặp lại của tên gốc (so với Spracklen: 43% lặp cả 10 lần, 39% không lặp lần nào).
- Số biến thể bịa khác nhau trên mỗi câu hỏi.
- Tỷ lệ biến thể đăng ký được theo quy tắc `ultranormalize`.

**Điểm quyết định:**

| Kết quả đo | Hướng bài báo |
| --- | --- |
| Trung bình ≥ 2 biến thể bịa đăng ký được mỗi câu hỏi | Giữ nguyên trọng tâm: tấn công né tránh thực tế cộng phòng thủ |
| < 2 biến thể (LLM gần như luôn lặp một tên) | Đổi trọng tâm sang H3: "tấn công né tránh thực tế khó hơn giả định"; phần tấn công chủ yếu dựa vào làm giả metadata |

### Bước 2.3 — Bảng chi phí làm giả metadata (2–3 ngày, chỉ đọc tài liệu)

Với mỗi đặc trưng: chi phí bằng USD hoặc số ngày chờ, nguồn trích dẫn, và có làm giả được hay không. Gợi ý phân nhóm:

| Nhóm | Đặc trưng | Chi phí |
| --- | --- | --- |
| Miễn phí, tức thì | Mô tả, tóm tắt, tác giả, giấy phép, classifier, project URL, số phụ thuộc, số bản phát hành | 0 |
| Rẻ | Tạo repo GitHub, lượt tải tự tạo, sao GitHub mua | Trích nguồn công bố về chợ mua sao và lượt tải giả |
| Phải chờ | Tuổi gói, số ngày có lượt tải | Số ngày |
| Không làm giả được | URL được PyPI xác minh từ repo không thuộc kẻ tấn công; mức đồng thuận giữa các LLM; số dự án thật phụ thuộc | — |

### Bước 2.4 — Thí nghiệm tấn công (2 tuần)

Mở rộng E3 và E4 trong `run_experiments.py`:

1. **Ngoài mẫu:** mục tiêu tấn công lấy từ phần kiểm thử của kiểm định chéo, không dùng mô hình đã thấy mục tiêu.
2. **RER theo ngân sách:** tập hành động là bộ biến thể ở bước 2.2, metadata làm giả theo bảng ở bước 2.3; vẽ RER theo ngân sách (ngày, USD).
3. **Mốc tự do sửa ký tự:** HotFlip và Faster-GCG trên CharCNN, cùng tập mục tiêu, cùng ngưỡng.
4. **Chỉ số so sánh (RQ2):** hiệu giữa tỷ lệ né khi tự do sửa ký tự và RER thực tế.

### Bước 2.5 — Phòng thủ (2 tuần)

So sánh ba cách trên cùng RER và FPR:

1. Chỉ dùng tên và đặc trưng ở hai nhóm "phải chờ" và "không làm giả được".
2. XGBoost với ràng buộc đơn điệu trên đặc trưng rẻ.
3. Huấn luyện đối kháng bằng biến thể thật và metadata giả.

**Điều kiện thành công (H4):** RER giảm ít nhất một nửa so với bộ phát hiện chuẩn, FPR trên gói mới ≤ 2%.

### Bước 2.6 — Viết bài và công bố có trách nhiệm (4 tuần)

1. Gửi danh sách tên bịa đăng ký được cho PyPI Security (security@pypi.org) trước khi nộp bài; ghi ngày gửi.
2. Viết theo cấu trúc 7 phần ở mục 7.3 của [bao-cao-thu-nghiem-pilot.md](bao-cao-thu-nghiem-pilot.md).
3. Công bố mã và số liệu tổng hợp; bộ tên đầy đủ chỉ cấp theo yêu cầu cho tới khi hết thời hạn công bố.
4. Nơi gửi: ACM AISec (thường có hạn nộp khoảng tháng 6–7), ACSAC (khoảng tháng 5–6), hoặc *Computers & Security* (không có hạn nộp cố định). Kiểm tra lại hạn nộp thực tế của năm 2027.

---

## Lịch tổng hợp

| Tuần | Mục tiêu 1 | Mục tiêu 2 |
| --- | --- | --- |
| 1 (11/2026) | 1.1 Chạy thử nhỏ | 2.1 Chốt tuyên bố tính mới |
| 2–3 | 1.2 Sinh dữ liệu đầy đủ; 1.3 Metadata | 2.3 Bảng chi phí |
| 4 (12/2026) | 1.4 Dựng bộ dữ liệu | 2.2 Bộ biến thể → **điểm quyết định** |
| 5–6 | 1.5 Chọn mô hình; 1.6 Báo cáo | — |
| 7–8 (01/2027) | — | 2.4 Tấn công |
| 9–10 (02/2027) | — | 2.5 Phòng thủ |
| 11–14 (03–04/2027) | — | 2.6 Viết bài |

## Chi phí ước tính

| Hạng mục | Ước tính |
| --- | --- |
| GPU thuê cho LLM cục bộ (khoảng 23.000 lượt × tối đa 1.500 token ≈ 35 triệu token; vLLM chạy theo lô trên một GPU 24 GB đạt cỡ 1.000–2.000 token/giây → khoảng 5–10 giờ GPU) | Khoảng 5–20 USD |
| LLM thương mại (khoảng 23.000 lượt) | Khoảng 2,4 USD với Claude Haiku 5.5 qua Batch API, chỉ code, `effort` thấp (ít hơn nếu dừng sớm); mô hình khác tính theo công thức ở [Hướng dẫn cho LLM thương mại](#ước-tính-chi-phí) |
| BigQuery | Miễn phí nếu lọc theo ngày (≤ 1 TB quét/tháng) |
| GitHub API | Miễn phí với token cá nhân |
