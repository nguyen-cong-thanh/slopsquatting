# Báo cáo: Thiết kế dữ liệu cho Giai đoạn 1

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

**Giảng viên hướng dẫn:** TS. Mai Đức Thọ · **Ngày:** 07/11/2026

## Tóm tắt

Báo cáo này trả lời các câu hỏi về dữ liệu nêu trong buổi trao đổi gần nhất: dữ liệu gồm những gì, lấy từ đâu, bao nhiêu, cấu trúc ra sao, xử lý mất cân bằng và chuẩn hóa thế nào, và chọn mô hình nào.

| Câu hỏi | Trả lời ngắn |
| --- | --- |
| Dữ liệu dùng để làm gì? | Huấn luyện bộ phát hiện D0. D0 nhận vào một tên gói Python và cho biết tên đó do LLM bịa ra hay là gói thật. |
| Gồm những mẫu nào? | **Mẫu nhãn 1:** tên gói do LLM bịa. **Mẫu nhãn 0:** tên gói thật mà chính LLM gợi ý trong cùng câu trả lời. |
| Lấy từ đâu? | Chủ yếu tự sinh: gửi 5.000 câu hỏi lập trình Python cho mỗi mô hình trong 4 LLM của đề cương, rồi tách tên gói từ câu trả lời. Bổ sung 1.066 tên bịa từ một bộ dữ liệu công khai. |
| Bao nhiêu? | Dự kiến 3.500–5.500 tên bịa (nhãn 1, không trùng nhau). Số tên thật (nhãn 0) sẽ đo ở bước thử nghiệm nhỏ. Ngoài ra có 10.000 tên gói thật lấy ngẫu nhiên từ PyPI để đo tỷ lệ báo nhầm. |
| Có cấu trúc không? | Có. Hai bảng: bảng **lượt gợi ý** (mỗi lần LLM nhắc tới một tên là một dòng) và bảng **tên gói** (mỗi tên một dòng, kèm nhãn). Xem mục 4. |
| Phạm vi | Chỉ hệ sinh thái PyPI (Python). npm chuyển sang phần mở rộng. |
| Chi phí | Khoảng 80 USD tiền gọi API. |

## 1. Thuật ngữ

| Thuật ngữ | Nghĩa trong báo cáo này |
| --- | --- |
| Tên gói | Tên dùng để cài thư viện Python, ví dụ `requests` trong lệnh `pip install requests`. |
| Registry | Kho gói chính thức, ở đây là PyPI (pypi.org). |
| Tên bịa (ảo giác) | Tên gói LLM gợi ý nhưng không phải gói thật cần dùng. Ví dụ phổ biến nhất: tên không hề có trên PyPI. |
| Nhãn, mẫu nhãn 1, mẫu nhãn 0 | D0 là bộ phân loại hai lớp. Mỗi tên gói trong dữ liệu được gắn nhãn 1 (tên bịa, đáng ngờ) hoặc nhãn 0 (tên thật, bình thường). Trong tài liệu học máy, hai nhóm này còn gọi là **lớp dương** và **lớp âm**. |
| D0, D′ | D0: bộ phát hiện cơ sở, huấn luyện ở Giai đoạn 1. D′: bộ phát hiện sau khi huấn luyện đối kháng ở Giai đoạn 2. |
| PHR (tỷ lệ ảo giác) | Trong tất cả các lượt LLM gợi ý tên gói, bao nhiêu phần trăm là tên bịa. |
| FPR (tỷ lệ báo nhầm) | Trong các tên gói thật, bao nhiêu phần trăm bị D0 báo nhầm là đáng ngờ. |
| TPR (tỷ lệ phát hiện) | Trong các tên bịa, bao nhiêu phần trăm bị D0 phát hiện. |
| TPR@1%FPR | Tỷ lệ phát hiện khi chỉnh ngưỡng sao cho D0 chỉ báo nhầm 1 trên 100 tên thật. Đây là cách so sánh các bộ phát hiện ở cùng mức báo nhầm. |

## 2. Dữ liệu gồm những mẫu nào

### 2.1. Mẫu nhãn 1: tên bịa

Là tên gói LLM đưa ra khi trả lời câu hỏi lập trình, nhưng không phải gói thật cần dùng. Có hai trường hợp:

| Trường hợp | Ví dụ | Cách xác định |
| --- | --- | --- |
| (a) Tên không tồn tại trên PyPI | `vectorcache`, `chromastore` [3] | Tra PyPI trả về lỗi 404 |
| (b) Tên có trên PyPI nhưng là tên nhầm. Thường là LLM nhầm tên module trong lệnh `import` với tên gói | `pil` (gói đúng là Pillow), `skimage` (gói đúng là scikit-image), `faiss` (gói đúng là faiss-cpu) [3] | Tra PyPI trả về 200, nhưng tên nằm trong danh sách “tên module → tên gói” dựng từ các gói phổ biến; kiểm tra thủ công các trường hợp còn lại |

Trường hợp (b) cho thấy vì sao cần một bộ phát hiện học máy chứ không chỉ tra PyPI. Trong thực nghiệm của Raj và Sahu [3], khoảng một nửa số tên bị gắn cờ là tên **đã có người đăng ký** trên PyPI. Tra PyPI không phát hiện được những tên này.

### 2.2. Mẫu nhãn 0: tên thật

Có ba cách chọn tên thật làm mẫu nhãn 0:

| Cách chọn | Ví dụ | Vấn đề |
| --- | --- | --- |
| Lấy ngẫu nhiên tên trên PyPI | (nhiều tên cá nhân, tên thử nghiệm) | Nhiều tên cá nhân, tên thử nghiệm, khác hẳn kiểu tên LLM hay dùng. D0 sẽ học cách nhận ra “tên kiểu LLM” thay vì nhận ra “tên bịa”, nên kết quả đo được cao giả tạo. |
| Lấy các gói phổ biến nhất | `numpy`, `pandas` | Quá dễ phân biệt với tên bịa, kết quả cũng cao giả tạo. |
| **Lấy tên thật mà chính LLM gợi ý trong cùng câu trả lời** | LLM viết mã dùng `requests`, `numpy` và `vectorcache` → `requests`, `numpy` là nhãn 0; `vectorcache` là nhãn 1 | Thiên về gói phổ biến, nhưng cùng nguồn với tên bịa nên D0 buộc phải học đúng điểm khác nhau giữa tên thật và tên bịa. |

**Đề xuất dùng cách thứ ba.** Cách này không tốn thêm chi phí, vì tên thật và tên bịa cùng nằm trong một câu trả lời. Lựa chọn tên thật có ảnh hưởng lớn đến kết quả: trong bài toán tương tự về phát hiện tên miền độc hại, Peck et al. [6] ghi nhận chỉ riêng việc đổi danh sách tên miền lành đã làm kết quả thay đổi rõ rệt.

Tên thật lấy ngẫu nhiên trên PyPI vẫn được dùng, nhưng chỉ để **đo tỷ lệ báo nhầm** trong điều kiện thực tế (tập C, mục 3.3), không dùng để huấn luyện.

## 3. Nguồn dữ liệu và quy mô dự kiến

Bộ dữ liệu gồm 3 tập. Tập A dùng để huấn luyện và kiểm thử. Tập B và C chỉ dùng để kiểm thử.

| Tập | Mục đích | Nguồn | Quy mô dự kiến |
| --- | --- | --- | --- |
| A. Tập chính | Huấn luyện, chọn tham số và kiểm thử D0 | Tự sinh từ 4 LLM (mục 3.1) và bộ 0pstech (mục 3.2) | 3.500–5.500 tên bịa; số tên thật đo ở bước thử nghiệm nhỏ |
| B. Tập kiểm thử ngoài nguồn | Kiểm tra D0 có nhận ra tên bịa từ nguồn chưa từng thấy khi huấn luyện không | DepScope [11] và Trend Micro [12] | Phần PyPI của hai bộ này; số lượng chính xác đếm sau khi tải về |
| C. Tập đo báo nhầm | Đo tỷ lệ báo nhầm trên tên thật trong điều kiện thực tế | 10.000 tên lấy ngẫu nhiên từ PyPI, cộng các gói mới đăng thu thập liên tục trong 2–4 tuần qua RSS của PyPI | Khoảng 10.000 tên thật |

### 3.1. Tự sinh dữ liệu (nguồn chính của tập A)

**Câu hỏi đầu vào:** bộ câu hỏi lập trình công khai của Spracklen et al. [1], [13], gồm 20.163 câu từ Stack Overflow và 19.806 câu do LLM tạo [2], chia đều cho Python và JavaScript. Lấy ngẫu nhiên 5.000 câu Python và dùng **cùng 5.000 câu này cho cả 4 mô hình**, để so sánh được giữa các mô hình.

**Mô hình:** GPT-4o, Claude Sonnet, CodeLlama-13B, DeepSeek-Coder-7B, theo đề cương.

**Cách lấy tên gói:** theo đúng 3 bước của Spracklen et al. [1]. Mỗi câu hỏi cần 3 lượt gọi mô hình:

1. Gửi câu hỏi, nhận đoạn mã. Lấy các tên trong lệnh `pip install` nếu có. Lệnh này chỉ xuất hiện ở khoảng 7% câu trả lời [1], nên cần thêm hai bước sau.
2. Gửi lại đoạn mã vừa sinh, hỏi “cần cài những gói nào để chạy đoạn mã này”.
3. Gửi lại câu hỏi ban đầu, hỏi “tác vụ này cần những gói nào”.

Không lấy tên từ câu lệnh `import`, vì tên module thường khác tên gói (ví dụ `import cv2` nhưng gói là opencv-python). Churilov [2] có lấy từ `import`, và các “tên bịa” xuất hiện nhiều nhất trong bài thực chất là tên module bị nhầm: `rest-framework`, `objc`, `opengl`.

**Tham số gọi mô hình:** theo Spracklen et al. [1]: temperature 0,7 khi sinh mã; temperature 0,01 và tối đa 64 token khi hỏi danh sách gói (bước 2 và 3).

**Ước tính số tên bịa thu được:**

| Đại lượng | Cách tính | Kết quả |
| --- | --- | --- |
| Số lượt gợi ý tên gói | 5.000 câu × khoảng 3,9 tên mỗi câu (số liệu của Spracklen et al. [1]) | Khoảng 19.400 lượt mỗi mô hình |
| Số lượt bịa, 2 mô hình thương mại | 19.400 × 5% (tỷ lệ ảo giác của mô hình thương mại [1], [2]) × 2 mô hình | Khoảng 1.900 lượt |
| Số lượt bịa, 2 mô hình mã nguồn mở | 19.400 × 20% (tỷ lệ của mô hình mã nguồn mở [1]) × 2 mô hình | Khoảng 7.800 lượt |
| Số tên bịa không trùng nhau | Khoảng 47% số lượt bịa là tên không trùng nhau (205.474 / 440.445 trong [1]) | Khoảng 4.500 tên |

Tỷ lệ 47% được tính gộp trên 16 mô hình của Spracklen et al., nên con số cho 4 mô hình ở đây có thể thấp hơn. Vì vậy báo cáo dùng khoảng **2.500–4.500 tên bịa** từ nguồn tự sinh. Cộng với bộ 0pstech (mục 3.2), tập A có khoảng **3.500–5.500 tên bịa**. Các con số này sẽ được đo lại ở bước thử nghiệm nhỏ (mục 7) trước khi chạy toàn bộ.

Số tên thật không trùng nhau (nhãn 0) chưa ước tính được, vì các gói phổ biến như `numpy`, `pandas` lặp lại rất nhiều lần. Bước thử nghiệm nhỏ sẽ đo con số này.

**Chi phí ước tính** (giá theo file `detail_survey`; mỗi câu hỏi gồm khoảng 1.100 token đầu vào và 530 token đầu ra cho cả 3 lượt):

| Mô hình | Chi phí cho 5.000 câu hỏi |
| --- | --- |
| GPT-4o | khoảng 40 USD |
| Claude Sonnet | khoảng 37 USD |
| CodeLlama-13B | khoảng 2 USD |
| DeepSeek-Coder-7B | khoảng 2 USD |
| **Tổng** | **khoảng 80 USD** |

### 3.2. Bộ dữ liệu công khai

| Nguồn | Nội dung | Giấy phép | Dùng cho |
| --- | --- | --- | --- |
| 0pstech/slopsquatting-dataset [10] | 1.066 tên bịa trên PyPI (tại ngày 05/11/2026), thu từ các tác vụ lập trình thông thường; mỗi tên ghi kèm mô hình, tác vụ, ngày phát hiện đầu tiên | CC BY 4.0 | Tập A |
| DepScope [11] | Tên bịa quan sát được từ lưu lượng thực của các AI agent lập trình | CC BY-NC-SA 4.0 (chỉ dùng phi thương mại) | Tập B |
| Trend Micro [12] | Tên bịa từ 100 tác vụ phát triển web | MIT | Tập B |
| Spracklen et al. [1] | 205.474 tên bịa | Chỉ cấp cho nhà nghiên cứu đã xác minh. Đã gửi yêu cầu; đến 07/11/2026 chưa có phản hồi. Kế hoạch không phụ thuộc nguồn này. | Nếu được cấp: bổ sung tập A |

Trước khi sinh dữ liệu, các bộ công khai này được dùng để khảo sát đặc điểm của tên bịa thật: độ dài, số đoạn, các từ hay gặp, khoảng cách tới tên gói thật gần nhất. Kết quả khảo sát dùng để kiểm tra dữ liệu tự sinh có khác biệt bất thường so với dữ liệu thật không.

### 3.3. Danh sách gói thật trên PyPI

Cần một bản chụp danh sách toàn bộ tên gói trên PyPI để xác định tên nào có, tên nào không. Bản chụp này được tải mới và ghi ngày tải. Không dùng lại danh sách đi kèm bộ dữ liệu của Spracklen et al., vì danh sách đó chụp ngày 10/01/2024; gói nào đăng ký sau ngày đó sẽ bị tính nhầm là tên bịa.

## 4. Cấu trúc dữ liệu

Dữ liệu lưu thành 3 file.

| File | Mỗi dòng là | Dùng để |
| --- | --- | --- |
| `raw_responses.jsonl` | Một lượt gọi mô hình: câu hỏi gửi đi và câu trả lời nhận về | Lưu vết, chạy lại khi cần |
| `mentions.csv` | Một lần LLM nhắc tới một tên gói | Tính tỷ lệ ảo giác, đếm số lần lặp lại |
| `names.csv` | Một tên gói không trùng nhau, kèm nhãn | **Bảng dùng để huấn luyện và kiểm thử D0** |

### 4.1. Bảng `mentions.csv`

Cột “Ví dụ” chỉ minh họa định dạng, không phải dữ liệu thật.

| Cột | Kiểu | Ý nghĩa | Ví dụ |
| --- | --- | --- | --- |
| `mention_id` | số | Mã lượt gợi ý | 10234 |
| `prompt_id` | chuỗi | Mã câu hỏi trong bộ của Spracklen | `SO_AT_00871` |
| `model` | chuỗi | Mô hình đã gợi ý | `codellama-13b` |
| `step` | chuỗi | Lấy được ở bước nào (1: `pip install`, 2: hỏi theo mã, 3: hỏi theo tác vụ) | `2` |
| `name_raw` | chuỗi | Tên đúng như LLM viết | `Vector_Cache` |
| `name_norm` | chuỗi | Tên sau chuẩn hóa (mục 6) | `vector-cache` |

### 4.2. Bảng `names.csv`

| Cột | Kiểu | Ý nghĩa |
| --- | --- | --- |
| `name_norm` | chuỗi | Tên gói sau chuẩn hóa. Khóa của bảng, không trùng nhau. |
| `label` | 0 hoặc 1 | 1 = tên bịa, 0 = tên thật |
| `case` | chuỗi | Với nhãn 1: `a` (không tồn tại) hoặc `b` (có trên PyPI nhưng là tên nhầm). Với nhãn 0: để trống |
| `on_pypi` | đúng/sai | Tên có trên PyPI tại ngày kiểm tra hay không |
| `check_date` | ngày | Ngày tra PyPI |
| `correct_pkg` | chuỗi | Với trường hợp `b`: gói đúng mà LLM định nói tới |
| `source` | chuỗi | `tu_sinh`, `0pstech`, `depscope`, `trendmicro` hoặc `pypi_ngau_nhien` |
| `models` | chuỗi | Các mô hình đã gợi ý tên này |
| `n_mentions` | số | Tổng số lần được gợi ý |
| `nearest_real` | chuỗi | Tên gói thật gần nhất (theo khoảng cách Levenshtein) |
| `edit_distance` | số | Số ký tự phải sửa để thành `nearest_real` |
| `group_id` | số | Nhóm các tên gần giống nhau, dùng khi chia tập (mục 5.3) |
| `split` | chuỗi | `train`, `val`, `test`, `test_B` hoặc `test_C` |

Ví dụ ba dòng (`vectorcache` và `pil` là tên bịa thật ghi nhận trong [3]):

| `name_norm` | `label` | `case` | `on_pypi` | `correct_pkg` | `nearest_real` | `edit_distance` |
| --- | --- | --- | --- | --- | --- | --- |
| `requests` | 0 | | đúng | | `requests` | 0 |
| `vectorcache` | 1 | `a` | sai | | (tính khi xử lý) | (tính khi xử lý) |
| `pil` | 1 | `b` | đúng | `pillow` | `pillow` | 3 |

## 5. Mất cân bằng dữ liệu

Mất cân bằng nghĩa là số tên bịa ít hơn nhiều so với số tên thật. Vấn đề này xuất hiện ở hai chỗ, và mỗi chỗ xử lý khác nhau.

### 5.1. Khi huấn luyện

Trong tập A, cứ khoảng 100 lượt gợi ý thì có 5–20 lượt là tên bịa, tùy mô hình [1], [2]. Nếu không xử lý, mô hình có xu hướng đoán mọi tên là tên thật mà vẫn đạt độ chính xác cao.

Cách xử lý: dùng **trọng số lớp**, tức là khi huấn luyện, phạt mô hình nặng hơn mỗi khi bỏ sót một tên bịa. Đây là cách đơn giản và không làm thay đổi dữ liệu.

Những cách **không dùng**, kèm lý do:

| Cách | Lý do không dùng |
| --- | --- |
| SMOTE (tạo mẫu mới bằng cách nội suy giữa các mẫu có sẵn) | Mẫu tạo ra là một vector đặc trưng, không ứng với tên gói nào có thật, trái với yêu cầu “mọi mẫu phải là tên gói hợp lệ” trong đề cương. |
| Nhân bản tên bịa trước khi chia tập | Cùng một tên có thể rơi vào cả tập huấn luyện lẫn tập kiểm thử, làm kết quả cao giả tạo. |
| Tạo thêm tên bịa bằng cách sửa ký tự ngẫu nhiên | Đây chính là kiểu tấn công ở Giai đoạn 2. Làm ở Giai đoạn 1 thì D0 đã được huấn luyện chống tấn công từ trước, và so sánh D0 với D′ mất ý nghĩa. |

### 5.2. Khi đánh giá

Ngoài thực tế, tên bịa còn hiếm hơn nhiều so với trong tập A. Vì vậy:

- Tập kiểm thử giữ nguyên tỷ lệ tự nhiên, không cân bằng lại.
- Chỉ số chính là **TPR@1%FPR** (tỷ lệ phát hiện khi chỉ báo nhầm 1 trên 100 tên thật), không dùng độ chính xác tổng (accuracy).
- Báo cáo thêm **Precision** (khi D0 báo động, bao nhiêu phần trăm là đúng) tính theo tỷ lệ tên bịa thực tế π:

```math
\text{Precision} = \frac{\text{TPR} \cdot \pi}{\text{TPR} \cdot \pi + \text{FPR} \cdot (1 - \pi)}
```

Ví dụ: D0 phát hiện 90% tên bịa và báo nhầm 1% tên thật. Nếu 5% tên gặp ngoài thực tế là tên bịa, thì trong các lần D0 báo động, khoảng 83% là đúng. Nếu chỉ 0,1% là tên bịa, con số này còn khoảng 8%. Montaruli et al. [5] gặp đúng hiện tượng này khi triển khai thật (chỉ 18,73% số lần báo động là đúng). Arp et al. [7] liệt kê việc bỏ qua tỷ lệ thực tế là một lỗi phổ biến trong các nghiên cứu học máy cho an toàn thông tin.

### 5.3. Chia tập và cỡ mẫu

Tập A chia theo tỷ lệ 70% huấn luyện, 15% chọn tham số, 15% kiểm thử, với hai quy tắc:

1. **Chia theo nhóm tên gần giống**, không chia theo từng dòng. Ví dụ `vector-cache` và `vectorcache` phải nằm cùng một tập. Raj và Sahu [3] chia theo từng dòng và để 72,9% dòng kiểm thử trùng tên với tập huấn luyện; các tác giả phải làm lại.
2. **Thêm một cách chia theo mô hình:** huấn luyện trên tên do 3 LLM sinh ra, kiểm thử trên LLM còn lại. Theo Spracklen et al. [1], 81% tên bịa chỉ do một mô hình sinh ra, nên đây là phép thử khó về khả năng tổng quát.

Cỡ tập kiểm thử tối thiểu (khoảng tin cậy 95%):

| Cần đo | Sai số chấp nhận | Số mẫu cần | Đáp ứng bởi |
| --- | --- | --- | --- |
| Tỷ lệ phát hiện, quanh 90% | ±2,6 điểm % | 500 tên bịa không trùng nhau | 15% của 3.500–5.500 tên bịa trong tập A (khoảng 500–800 tên) |
| Tỷ lệ báo nhầm, quanh 1% | ±0,2 điểm % | 10.000 tên thật | Tập C |

## 6. Chuẩn hóa dữ liệu

Chuẩn hóa là đưa mọi tên gói về một dạng duy nhất, để các cách viết khác nhau của cùng một gói được coi là một. PyPI quy định các tên sau là **cùng một gói** [8]: `Vector_Cache`, `vector.cache`, `VECTOR-CACHE`.

**Các bước chuẩn hóa**, áp dụng giống hệt nhau cho cả tên bịa và tên thật:

| Bước | Việc làm | Ví dụ trước → sau |
| --- | --- | --- |
| 1 | Bỏ phần không thuộc tên: phiên bản, tùy chọn cài thêm, đường dẫn, chú thích | `requests[security]>=2.0` → `requests` |
| 2 | Loại tên không hợp lệ theo quy tắc của PyPI: chỉ gồm chữ, số, `.`, `_`, `-`, bắt đầu và kết thúc bằng chữ hoặc số [8] | `-abc` → loại |
| 3 | Đổi về chữ thường, thay mọi chuỗi `.`, `_`, `-` liên tiếp bằng một dấu `-` (quy tắc PEP 503 [8]) | `Vector_Cache` → `vector-cache` |
| 4 | Khử trùng lặp trên tên đã chuẩn hóa | Hai dòng `vector-cache` → một dòng |

Mã Python cho bước 2 và 3:

```python
import re

VALID = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])\Z", re.IGNORECASE)

def normalize(name):
    if not VALID.match(name):
        return None
    return re.sub(r"[-_.]+", "-", name).lower()
```

**Vì sao phải chuẩn hóa giống nhau cho hai nhãn:** LLM hay viết tên theo kiểu module với dấu `_`, còn tên trên PyPI thường dùng `-`. Nếu chỉ chuẩn hóa một bên, D0 có thể chỉ học quy tắc “có dấu `_` là tên bịa”, và kết quả không có giá trị.

**Đầu vào của D0:** sau chuẩn hóa, tên gói chỉ còn 37 loại ký tự (a–z, 0–9, `-`). D0 nhận chuỗi ký tự này, độ dài tối đa chọn theo độ dài thực tế đo được (phân vị 99). Các bước học từ dữ liệu như xây từ vựng n-gram chỉ được thực hiện trên tập huấn luyện, để tránh thông tin của tập kiểm thử lọt vào quá trình huấn luyện [7].

## 7. Lựa chọn mô hình

Theo Spracklen et al. [1], chỉ 13,4% tên bịa cách tên thật gần nhất 1–2 ký tự; 48,6% cách từ 6 ký tự trở lên. Nghĩa là đa số tên bịa **không phải lỗi gõ**, mà là tổ hợp từ có vẻ hợp lý. Dấu hiệu nhận biết có thể nằm ở cách ghép từ nhiều hơn ở từng ký tự. Ngoài ra, Raj và Sahu [3] ghi nhận bộ phân loại của họ dựa 82% vào thông tin ngoài tên (số người duy trì gói, có liên kết GitHub hay không), nên chưa rõ riêng tên gói chứa bao nhiêu tín hiệu.

Vì vậy đề xuất so sánh 3 mô hình:

| Mô hình | Lý do đưa vào | Dùng được cho tấn công Faster-GCG ở Giai đoạn 2? |
| --- | --- | --- |
| Logistic Regression hoặc XGBoost trên các cụm 1–5 ký tự liên tiếp (n-gram) | Mốc so sánh đơn giản, dễ giải thích. Thiếu mốc đơn giản là lỗi phổ biến theo Arp et al. [7] | Không (không có gradient); chỉ tấn công được kiểu black-box |
| 1D-CNN mức ký tự | Mô hình D0 theo đề cương | Có |
| Mô hình theo cụm từ con (fastText hoặc transformer cỡ nhỏ) | Kiểm tra giả thuyết dấu hiệu nằm ở cách ghép từ | Có |

Nếu mô hình đơn giản đã đạt kết quả gần bằng mạng nơ-ron, báo cáo sẽ nêu rõ, và lý do giữ 1D-CNN là để có gradient phục vụ Giai đoạn 2.

## 8. Ảnh hưởng tới Giai đoạn 2 và đề cương

**Ràng buộc khi tấn công.** PyPI từ chối đăng ký tên mới nếu tên đó trùng với một gói đã có sau khi bỏ `.`, `_`, `-`, đổi `l` và `i` thành `1`, đổi `o` thành `0` (hàm `ultranormalize_name` trong mã nguồn PyPI [9]). PyPI còn có danh sách tên cấm. Theo Churilov [2], hai cơ chế này khiến 68 trong 109 tên bịa chung của 5 mô hình không đăng ký được. Bước kiểm tra ràng buộc trong kịch bản Faster-GCG cần bổ sung luật này: ví dụ đổi `o` thành `0` thường vô ích với kẻ tấn công vì sẽ bị chặn.

**Các điểm cần sửa trong đề cương v2:**

| Đề cương v2 ghi | Đề xuất sửa |
| --- | --- |
| Thu thập trên PyPI và npm | Chỉ PyPI; npm chuyển sang phần mở rộng |
| Chưa nêu tên thật (nhãn 0) lấy từ đâu | Tên thật do chính LLM gợi ý trong cùng câu trả lời (mục 2.2) |
| Tên bịa = tên không có trên registry | Thêm trường hợp tên có trên PyPI nhưng là tên nhầm (mục 2.1) |
| Chỉ số: Precision, Recall, F1, AUC-ROC, FPR | Chỉ số chính: TPR@1%FPR; Precision tính theo tỷ lệ thực tế (mục 5.2) |
| Ràng buộc tấn công: tên hợp lệ, chưa tồn tại, đủ hợp lý | Thêm luật chặn tên gần giống và danh sách tên cấm của PyPI |
| D0 là 1D-CNN, so với RF/XGBoost | Thêm mô hình n-gram và mô hình theo cụm từ con (mục 7) |

## 9. Kế hoạch tiếp theo

| Bước | Việc làm | Kết quả |
| --- | --- | --- |
| 1 | Tải bộ 0pstech, DepScope, Trend Micro; chụp danh sách gói PyPI | Dữ liệu thô, danh sách PyPI có ghi ngày |
| 2 | Khảo sát đặc điểm tên bịa trong các bộ công khai | Báo cáo khảo sát dữ liệu |
| 3 | Thử nghiệm nhỏ: 300 câu hỏi trên CodeLlama-13B và DeepSeek-Coder-7B (chi phí dưới 1 USD); huấn luyện mô hình n-gram | Số tên bịa và tên thật không trùng nhau trên 1.000 câu hỏi; mức phân biệt đạt được khi chỉ dùng tên |
| 4 | Nếu bước 3 cho kết quả đủ tốt: chạy đủ 5.000 câu hỏi trên 4 mô hình | Tập A hoàn chỉnh |
| 5 | Tạo tập B và C; chia tập; huấn luyện và so sánh 3 mô hình | D0 và kết quả Giai đoạn 1 |

## 10. Các vấn đề kính đề nghị thầy cho ý kiến

1. Dùng tên thật do chính LLM gợi ý làm mẫu nhãn 0 (mục 2.2) có phù hợp không?
2. Tên có trên PyPI nhưng là tên nhầm, như `pil`, nên gắn nhãn 1 (đáng ngờ) như đề xuất ở mục 2.1, hay tách thành một nhóm riêng chỉ dùng để phân tích?
3. Nếu bước 3 cho thấy riêng tên gói chứa ít tín hiệu, có nên cho D0 dùng thêm thông tin ngoài tên (ngữ cảnh câu hỏi, thông tin của gói trên PyPI) không? Việc này làm thay đổi phạm vi “bộ phát hiện chỉ dùng tên” trong đề cương.

## Phụ lục. Đính chính số liệu trong báo cáo khảo sát trước

Sau khi đọc toàn văn các bài báo, 4 số liệu trong báo cáo khảo sát trước cần sửa:

| Nội dung | Báo cáo trước ghi | Bài gốc ghi |
| --- | --- | --- |
| Tỷ lệ lỗi gõ [1] | 13% là lỗi gõ lệch 1 ký tự | 13,4% cách tên thật 1–2 ký tự; 37,9% cách 3–5; 48,6% cách từ 6 trở lên |
| Cách lấy tên gói [1] | Lấy từ lệnh `pip install` | 3 bước (mục 3.1); `pip install` chỉ có ở 7% câu trả lời |
| Độ chính xác nhãn [4] | Kiểm tra thủ công 200 mẫu, đúng 95,8% | Lấy mẫu 200 câu trả lời; trong 24 câu trả lời bị gắn cờ, 23 đúng. Khoảng tin cậy 95%: 79,8–99,3% |
| Danh sách gói thật [2] | Không nêu | Churilov dùng danh sách chụp ngày 10/01/2024 cho dữ liệu tháng 4/2026 |

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
10. 0pstech/VDB. *slopsquatting-dataset*. [github.com/0pstech/slopsquatting-dataset](https://github.com/0pstech/slopsquatting-dataset)
11. Cuttalo. *DepScope hallucinations dataset*. [github.com/cuttalo/depscope-hallucinations-dataset](https://github.com/cuttalo/depscope-hallucinations-dataset)
12. Trend Micro. *slopsquatting*. [github.com/trendmicro/slopsquatting](https://github.com/trendmicro/slopsquatting)
13. J. Spracklen. *PackageHallucination* (mã nguồn và bộ câu hỏi đi kèm [1]). [github.com/Spracks/PackageHallucination](https://github.com/Spracks/PackageHallucination)
