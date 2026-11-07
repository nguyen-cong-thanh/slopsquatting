# Báo cáo: Thiết kế dữ liệu cho Giai đoạn 1

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

**Giảng viên hướng dẫn:** TS. Mai Đức Thọ · **Ngày:** 07/11/2026

## Tóm tắt

| Câu hỏi | Trả lời ngắn |
| --- | --- |
| Dữ liệu dùng để làm gì? | Huấn luyện bộ phát hiện D0. D0 nhận vào một tên gói Python và cho biết tên đó do LLM bịa ra hay là gói thật. |
| Gồm những mẫu nào? | **Tên bịa:** tên gói LLM đưa ra nhưng không phải gói thật cần dùng. **Tên thật:** tên gói thật mà chính LLM gợi ý trong cùng câu trả lời. |
| Lấy từ đâu? | Chủ yếu tự sinh: gửi 5.000 câu hỏi lập trình Python cho mỗi LLM trong 4 LLM của đề cương, rồi tách tên gói từ câu trả lời. Bổ sung 1.066 tên bịa từ bộ dữ liệu công khai 0pstech. |
| Bao nhiêu? | Dự kiến 3.500–5.500 tên bịa không trùng nhau. Số tên thật sẽ đo khi chạy thử. Ngoài ra lấy 10.000 tên gói thật ngẫu nhiên trên PyPI để đo tỷ lệ báo nhầm. |
| Có cấu trúc không? | Có. Hai bảng chính: bảng lượt gợi ý (mỗi lần LLM nhắc tới một tên là một dòng) và bảng tên gói (mỗi tên một dòng, kèm loại tên). |
| Phạm vi | Chỉ PyPI (Python). npm chuyển sang phần mở rộng. |
| Chi phí | Khoảng 80 USD tiền gọi API. |

## Dữ liệu gồm những gì

D0 là bộ phân loại hai lớp: **tên bịa** và **tên thật**. Trong tài liệu học máy, tên bịa là lớp dương (lớp cần phát hiện), tên thật là lớp âm.

### Tên bịa

Tên bịa (còn gọi là ảo giác) là tên gói LLM đưa ra khi trả lời câu hỏi lập trình nhưng không phải gói thật cần dùng. Có hai loại:

| Loại | Ví dụ | Cách xác định |
| --- | --- | --- |
| Tên không tồn tại | `vectorcache`, `chromastore` | Tra PyPI trả về lỗi 404 |
| Tên nhầm: có trên PyPI nhưng không phải gói đúng, thường do LLM nhầm tên module trong lệnh `import` với tên gói | `pil` (gói đúng là Pillow), `skimage` (gói đúng là scikit-image), `faiss` (gói đúng là faiss-cpu) | Tra PyPI trả về 200, nhưng tên nằm trong danh sách “tên module → tên gói” dựng từ các gói phổ biến; các trường hợp còn lại kiểm tra thủ công |

Các ví dụ trên lấy từ Raj và Sahu (2026). Trong thực nghiệm của họ, khoảng một nửa số tên bị gắn cờ là **tên nhầm đã có người đăng ký** trên PyPI. Tra PyPI không phát hiện được loại này, nên cần một bộ phát hiện học máy.

### Tên thật

Có ba cách chọn tên thật:

| Cách chọn | Vấn đề |
| --- | --- |
| Lấy ngẫu nhiên tên trên PyPI | Nhiều tên cá nhân, tên thử nghiệm, khác hẳn kiểu tên LLM hay dùng. D0 sẽ học cách nhận ra “tên kiểu LLM” thay vì nhận ra “tên bịa”, nên kết quả đo được cao giả tạo. |
| Lấy các gói phổ biến nhất, như `numpy`, `pandas` | Quá dễ phân biệt với tên bịa, kết quả cũng cao giả tạo. |
| **Lấy tên thật mà chính LLM gợi ý trong cùng câu trả lời** | Thiên về gói phổ biến, nhưng cùng nguồn với tên bịa, nên D0 buộc phải học đúng điểm khác nhau giữa tên thật và tên bịa. |

**Đề xuất dùng cách thứ ba.** Ví dụ: LLM trả lời một câu hỏi bằng đoạn mã dùng `requests`, `numpy` và `vectorcache`; khi đó `requests`, `numpy` là tên thật, `vectorcache` là tên bịa. Cách này không tốn thêm chi phí vì hai loại tên nằm trong cùng câu trả lời.

Cách chọn tên thật ảnh hưởng lớn đến kết quả: trong bài toán tương tự về phát hiện tên miền độc hại, Peck và cộng sự (2019) ghi nhận chỉ riêng việc đổi danh sách tên miền lành đã làm kết quả thay đổi rõ rệt.

Tên thật lấy ngẫu nhiên trên PyPI vẫn được dùng, nhưng chỉ để đo tỷ lệ báo nhầm trong điều kiện thực tế, không dùng để huấn luyện.

## Nguồn dữ liệu và quy mô dự kiến

Bộ dữ liệu gồm 3 tập:

| Tập | Mục đích | Nguồn | Quy mô dự kiến |
| --- | --- | --- | --- |
| Tập chính | Huấn luyện, chọn tham số và kiểm thử D0 | Tự sinh từ 4 LLM, cộng bộ 0pstech | 3.500–5.500 tên bịa; số tên thật đo khi chạy thử |
| Tập kiểm thử nguồn ngoài | Kiểm tra D0 có nhận ra tên bịa từ nguồn chưa từng thấy khi huấn luyện không | Phần PyPI của bộ DepScope và bộ Trend Micro | Đếm sau khi tải về |
| Tập đo báo nhầm | Đo tỷ lệ D0 báo nhầm tên thật trong điều kiện thực tế | 10.000 tên lấy ngẫu nhiên trên PyPI, cộng các gói mới đăng thu thập liên tục 2–4 tuần qua RSS của PyPI | Khoảng 10.000 tên thật |

### Tự sinh dữ liệu

**Câu hỏi đầu vào:** bộ câu hỏi lập trình công khai trong [kho mã của Spracklen và cộng sự](https://github.com/Spracks/PackageHallucination), gồm 20.163 câu từ Stack Overflow và 19.806 câu do LLM tạo, chia đều cho Python và JavaScript. Lấy ngẫu nhiên 5.000 câu Python, dùng **cùng 5.000 câu này cho cả 4 LLM** để so sánh được giữa các LLM.

**LLM:** GPT-4o, Claude Sonnet, CodeLlama-13B, DeepSeek-Coder-7B, theo đề cương.

**Cách lấy tên gói:** làm theo Spracklen và cộng sự (2025). Mỗi câu hỏi cần 3 lượt gọi LLM:

1. Gửi câu hỏi, nhận đoạn mã, lấy các tên trong lệnh `pip install` nếu có. Lệnh này chỉ xuất hiện ở khoảng 7% câu trả lời, nên cần thêm hai lượt sau.
2. Gửi lại đoạn mã vừa sinh, hỏi “cần cài những gói nào để chạy đoạn mã này”.
3. Gửi lại câu hỏi ban đầu, hỏi “tác vụ này cần những gói nào”.

Không lấy tên từ lệnh `import`, vì tên module thường khác tên gói (ví dụ `import cv2` nhưng gói là opencv-python). Churilov (2026) có lấy từ `import`, và các “tên bịa” xuất hiện nhiều nhất trong bài thực chất là tên module bị nhầm: `rest-framework`, `objc`, `opengl`.

**Tham số gọi LLM** (theo Spracklen và cộng sự): temperature 0,7 khi sinh mã; temperature 0,01 và tối đa 64 token khi hỏi danh sách gói.

**Ước tính số tên bịa:**

| Đại lượng | Cách tính | Kết quả |
| --- | --- | --- |
| Số lượt gợi ý tên gói | 5.000 câu × khoảng 3,9 tên mỗi câu (số liệu của Spracklen và cộng sự) | Khoảng 19.400 lượt mỗi LLM |
| Số lượt bịa của GPT-4o và Claude Sonnet | 19.400 × 5% (tỷ lệ bịa của LLM thương mại, theo Spracklen và cộng sự, Churilov) × 2 | Khoảng 1.900 lượt |
| Số lượt bịa của CodeLlama-13B và DeepSeek-Coder-7B | 19.400 × 20% (tỷ lệ bịa của LLM mã nguồn mở, theo Spracklen và cộng sự) × 2 | Khoảng 7.800 lượt |
| Số tên bịa không trùng nhau | Khoảng 47% số lượt bịa là tên không trùng nhau (205.474 tên trên 440.445 lượt, theo Spracklen và cộng sự) | Khoảng 4.500 tên |

Tỷ lệ 47% được tính gộp trên 16 LLM trong bài của Spracklen và cộng sự, nên với 4 LLM con số có thể thấp hơn. Vì vậy báo cáo dùng khoảng **2.500–4.500 tên bịa** từ nguồn tự sinh. Cộng 1.066 tên của bộ 0pstech, tập chính có khoảng **3.500–5.500 tên bịa**. Các con số này sẽ được đo lại khi chạy thử, trước khi chạy toàn bộ.

Số tên thật không trùng nhau chưa ước tính được, vì các gói phổ biến như `numpy`, `pandas` lặp lại rất nhiều lần. Lần chạy thử sẽ đo con số này.

**Chi phí ước tính** (giá theo file `detail_survey`; mỗi câu hỏi gồm khoảng 1.100 token đầu vào và 530 token đầu ra cho cả 3 lượt):

| LLM | Chi phí cho 5.000 câu hỏi |
| --- | --- |
| GPT-4o | khoảng 40 USD |
| Claude Sonnet | khoảng 37 USD |
| CodeLlama-13B | khoảng 2 USD |
| DeepSeek-Coder-7B | khoảng 2 USD |
| **Tổng** | **khoảng 80 USD** |

### Bộ dữ liệu công khai

| Bộ dữ liệu | Nội dung | Giấy phép | Dùng cho |
| --- | --- | --- | --- |
| [0pstech](https://github.com/0pstech/slopsquatting-dataset) | 1.066 tên bịa trên PyPI (tại ngày 05/11/2026), thu từ các tác vụ lập trình thông thường; mỗi tên ghi kèm LLM, tác vụ, ngày phát hiện đầu tiên | CC BY 4.0 | Tập chính |
| [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset) | Tên bịa quan sát được từ lưu lượng thực của các AI agent lập trình | CC BY-NC-SA 4.0 (chỉ dùng phi thương mại) | Tập kiểm thử nguồn ngoài |
| [Trend Micro](https://github.com/trendmicro/slopsquatting) | Tên bịa từ 100 tác vụ phát triển web | MIT | Tập kiểm thử nguồn ngoài |
| Spracklen và cộng sự | 205.474 tên bịa | Chỉ cấp cho nhà nghiên cứu đã xác minh. Đã gửi yêu cầu; đến 07/11/2026 chưa có phản hồi. Kế hoạch không phụ thuộc nguồn này. | Nếu được cấp: bổ sung tập chính |

Trước khi tự sinh dữ liệu, các bộ công khai này được dùng để khảo sát đặc điểm của tên bịa thật: độ dài, số đoạn, các từ hay gặp, khoảng cách tới tên gói thật gần nhất. Kết quả dùng để kiểm tra dữ liệu tự sinh có khác biệt bất thường so với dữ liệu thật không.

### Danh sách gói thật trên PyPI

Để biết tên nào có trên PyPI, cần tải mới danh sách toàn bộ tên gói và ghi ngày tải. Không dùng lại danh sách đi kèm bài của Spracklen và cộng sự, vì danh sách đó chụp ngày 10/01/2024: gói nào đăng ký sau ngày đó sẽ bị tính nhầm là tên bịa. Churilov (2026) mắc đúng lỗi này khi dùng danh sách đó cho dữ liệu tháng 4/2026.

## Cấu trúc dữ liệu

Dữ liệu lưu thành 3 file:

| File | Mỗi dòng là | Dùng để |
| --- | --- | --- |
| `raw_responses.jsonl` | Một lượt gọi LLM: câu hỏi gửi đi và câu trả lời nhận về | Lưu vết, chạy lại khi cần |
| `mentions.csv` | Một lần LLM nhắc tới một tên gói | Tính tỷ lệ bịa, đếm số lần lặp lại |
| `names.csv` | Một tên gói không trùng nhau, kèm loại tên | Huấn luyện và kiểm thử D0 |

### Bảng `mentions.csv`

| Cột | Ý nghĩa | Ví dụ minh họa |
| --- | --- | --- |
| `prompt_id` | Mã câu hỏi trong bộ của Spracklen và cộng sự | `SO_AT_00871` |
| `model` | LLM đã gợi ý | `codellama-13b` |
| `source_turn` | Lượt lấy được tên: `pip_install`, `hoi_theo_ma` hoặc `hoi_theo_tac_vu` | `hoi_theo_ma` |
| `name_raw` | Tên đúng như LLM viết | `Vector_Cache` |
| `name_norm` | Tên sau chuẩn hóa | `vector-cache` |

### Bảng `names.csv`

| Cột | Ý nghĩa |
| --- | --- |
| `name_norm` | Tên gói sau chuẩn hóa, không trùng nhau |
| `name_type` | `ten_that`, `khong_ton_tai` hoặc `ten_nham`. Khi huấn luyện, `khong_ton_tai` và `ten_nham` gộp thành tên bịa |
| `on_pypi` | Tên có trên PyPI tại ngày kiểm tra hay không |
| `check_date` | Ngày tra PyPI |
| `correct_pkg` | Với tên nhầm: gói đúng mà LLM định nói tới |
| `source` | `tu_sinh`, `0pstech`, `depscope`, `trendmicro` hoặc `pypi_ngau_nhien` |
| `models` | Các LLM đã gợi ý tên này |
| `n_mentions` | Tổng số lần được gợi ý |
| `nearest_real` | Tên gói thật gần nhất (theo khoảng cách Levenshtein, tức số ký tự phải thêm, xóa hoặc thay) |
| `edit_distance` | Khoảng cách tới `nearest_real` |
| `group_id` | Nhóm các tên gần giống nhau, dùng khi chia tập |
| `split` | `huan_luyen`, `chon_tham_so`, `kiem_thu`, `kiem_thu_nguon_ngoai` hoặc `do_bao_nham` |

Ví dụ ba dòng (`vectorcache` và `pil` là tên bịa thật trong bài của Raj và Sahu):

| `name_norm` | `name_type` | `on_pypi` | `correct_pkg` | `nearest_real` | `edit_distance` |
| --- | --- | --- | --- | --- | --- |
| `requests` | `ten_that` | có | | `requests` | 0 |
| `vectorcache` | `khong_ton_tai` | không | | (tính khi xử lý) | (tính khi xử lý) |
| `pil` | `ten_nham` | có | `pillow` | `pillow` | 3 |

## Mất cân bằng dữ liệu

Mất cân bằng nghĩa là số tên bịa ít hơn nhiều so với số tên thật. Vấn đề này xuất hiện ở hai chỗ, mỗi chỗ xử lý khác nhau.

### Khi huấn luyện

Trong tập chính, cứ khoảng 100 lượt gợi ý thì có 5–20 lượt là tên bịa, tùy LLM. Nếu không xử lý, D0 có xu hướng đoán mọi tên là tên thật mà vẫn đạt độ chính xác cao.

Cách xử lý: dùng **trọng số lớp**, tức là khi huấn luyện, phạt D0 nặng hơn mỗi khi bỏ sót một tên bịa. Cách này đơn giản và không làm thay đổi dữ liệu.

Những cách không dùng:

| Cách | Lý do không dùng |
| --- | --- |
| SMOTE (tạo mẫu mới bằng cách nội suy giữa các mẫu có sẵn) | Mẫu tạo ra là một vector đặc trưng, không ứng với tên gói nào có thật, trái với yêu cầu “mọi mẫu phải là tên gói hợp lệ” trong đề cương. |
| Nhân bản tên bịa trước khi chia tập | Cùng một tên có thể rơi vào cả tập huấn luyện lẫn tập kiểm thử, làm kết quả cao giả tạo. |
| Tạo thêm tên bịa bằng cách sửa ký tự ngẫu nhiên | Đây chính là kiểu tấn công ở Giai đoạn 2. Làm ở Giai đoạn 1 thì D0 đã được huấn luyện chống tấn công từ trước, và so sánh D0 với D′ mất ý nghĩa. |

### Khi đánh giá

Ngoài thực tế, tên bịa còn hiếm hơn nhiều so với trong tập chính. Vì vậy:

- Tập kiểm thử giữ nguyên tỷ lệ tự nhiên, không cân bằng lại.
- Chỉ số chính là **tỷ lệ phát hiện tên bịa khi chỉ cho phép báo nhầm 1 trên 100 tên thật** (viết tắt TPR@1%FPR), không dùng độ chính xác tổng.
- Báo cáo thêm **Precision**: trong các lần D0 báo động, bao nhiêu phần trăm là đúng. Precision phụ thuộc tỷ lệ tên bịa ngoài thực tế π:

```math
\text{Precision} = \frac{\text{TPR} \cdot \pi}{\text{TPR} \cdot \pi + \text{FPR} \cdot (1 - \pi)}
```

trong đó TPR là tỷ lệ phát hiện tên bịa, FPR là tỷ lệ báo nhầm tên thật.

Ví dụ: D0 phát hiện 90% tên bịa và báo nhầm 1% tên thật. Nếu 5% tên gặp ngoài thực tế là tên bịa, thì khoảng 83% lần báo động là đúng. Nếu chỉ 0,1% là tên bịa, con số này còn khoảng 8%. Montaruli và cộng sự (2025) gặp đúng hiện tượng này khi triển khai thật: chỉ 18,73% lần báo động là đúng. Arp và cộng sự (2022) liệt kê việc bỏ qua tỷ lệ thực tế là một lỗi phổ biến trong nghiên cứu học máy cho an toàn thông tin.

### Chia tập và cỡ mẫu

Tập chính chia 70% huấn luyện, 15% chọn tham số, 15% kiểm thử, theo hai quy tắc:

1. **Chia theo nhóm tên gần giống**, không chia theo từng dòng. Ví dụ `vector-cache` và `vectorcache` phải nằm cùng một phần. Raj và Sahu (2026) chia theo từng dòng và để 72,9% dòng kiểm thử trùng tên với phần huấn luyện; các tác giả phải làm lại.
2. **Thêm một cách chia theo LLM:** huấn luyện trên tên do 3 LLM sinh ra, kiểm thử trên LLM còn lại. Theo Spracklen và cộng sự, 81% tên bịa chỉ do một LLM sinh ra, nên đây là phép thử khó về khả năng tổng quát.

Cỡ mẫu kiểm thử tối thiểu (khoảng tin cậy 95%):

| Cần đo | Sai số chấp nhận | Số mẫu cần | Lấy từ |
| --- | --- | --- | --- |
| Tỷ lệ phát hiện tên bịa, quanh 90% | ±2,6 điểm % | 500 tên bịa không trùng nhau | Phần kiểm thử của tập chính: 15% của 3.500–5.500, tức khoảng 500–800 tên |
| Tỷ lệ báo nhầm, quanh 1% | ±0,2 điểm % | 10.000 tên thật | Tập đo báo nhầm |

## Chuẩn hóa dữ liệu

Chuẩn hóa là đưa mọi tên gói về một dạng duy nhất. Theo [quy tắc của PyPI](https://packaging.python.org/en/latest/specifications/name-normalization/), các tên `Vector_Cache`, `vector.cache`, `VECTOR-CACHE` là **cùng một gói**.

Các bước, áp dụng giống hệt nhau cho cả tên bịa và tên thật:

| Bước | Việc làm | Ví dụ trước → sau |
| --- | --- | --- |
| Bỏ phần thừa | Bỏ phiên bản, tùy chọn cài thêm, đường dẫn, chú thích | `requests[security]>=2.0` → `requests` |
| Loại tên không hợp lệ | Chỉ giữ tên gồm chữ, số, `.`, `_`, `-`, bắt đầu và kết thúc bằng chữ hoặc số | `-abc` → loại |
| Đưa về dạng chuẩn | Đổi về chữ thường, thay mọi chuỗi `.`, `_`, `-` liên tiếp bằng một dấu `-` | `Vector_Cache` → `vector-cache` |
| Khử trùng lặp | Gộp các dòng có cùng tên đã chuẩn hóa | Hai dòng `vector-cache` → một dòng |

Mã Python cho bước loại tên không hợp lệ và đưa về dạng chuẩn:

```python
import re

VALID = re.compile(r"^([A-Z0-9]|[A-Z0-9][A-Z0-9._-]*[A-Z0-9])\Z", re.IGNORECASE)

def normalize(name):
    if not VALID.match(name):
        return None
    return re.sub(r"[-_.]+", "-", name).lower()
```

**Vì sao phải chuẩn hóa giống nhau cho cả hai loại tên:** LLM hay viết tên theo kiểu module với dấu `_`, còn tên trên PyPI thường dùng `-`. Nếu chỉ chuẩn hóa một bên, D0 có thể chỉ học quy tắc “có dấu `_` là tên bịa”, và kết quả không có giá trị.

**Đầu vào của D0:** sau chuẩn hóa, tên gói chỉ còn 37 loại ký tự (a–z, 0–9, `-`). Độ dài tối đa chọn theo độ dài thực tế đo được. Những gì học từ dữ liệu, như từ vựng n-gram, chỉ được xây trên phần huấn luyện, để thông tin của phần kiểm thử không lọt vào quá trình huấn luyện (Arp và cộng sự, 2022).

## Chọn mô hình

Theo Spracklen và cộng sự, chỉ 13,4% tên bịa cách tên thật gần nhất 1–2 ký tự; 48,6% cách từ 6 ký tự trở lên. Nghĩa là đa số tên bịa **không phải lỗi gõ** mà là tổ hợp từ có vẻ hợp lý, nên dấu hiệu nhận biết có thể nằm ở cách ghép từ nhiều hơn ở từng ký tự. Ngoài ra, bộ phân loại của Raj và Sahu dựa 82% vào thông tin ngoài tên (số người duy trì gói, có liên kết GitHub hay không), nên chưa rõ riêng tên gói chứa bao nhiêu tín hiệu.

Vì vậy đề xuất so sánh 3 mô hình:

| Mô hình | Lý do đưa vào | Dùng được cho tấn công Faster-GCG ở Giai đoạn 2? |
| --- | --- | --- |
| Logistic Regression hoặc XGBoost trên các cụm 1–5 ký tự liên tiếp (n-gram) | Mốc so sánh đơn giản, dễ giải thích; Arp và cộng sự coi việc thiếu mốc đơn giản là lỗi phổ biến | Không (không có gradient); chỉ tấn công được kiểu black-box |
| 1D-CNN mức ký tự | Mô hình D0 theo đề cương | Có |
| Mô hình theo cụm từ con (fastText hoặc transformer cỡ nhỏ) | Kiểm tra giả thuyết dấu hiệu nằm ở cách ghép từ | Có |

Nếu mô hình đơn giản đạt kết quả gần bằng mạng nơ-ron, báo cáo sẽ nêu rõ; khi đó lý do giữ 1D-CNN là để có gradient phục vụ Giai đoạn 2.

## Ảnh hưởng tới Giai đoạn 2 và đề cương

**Ràng buộc khi tấn công.** PyPI từ chối đăng ký tên mới nếu tên đó trùng với một gói đã có sau khi bỏ `.`, `_`, `-`, đổi `l` và `i` thành `1`, đổi `o` thành `0` (hàm `ultranormalize_name` trong [mã nguồn PyPI](https://github.com/pypi/warehouse/blob/main/warehouse/migrations/versions/d18d443f89f0_ultranormalize_name_function.py)). PyPI còn có danh sách tên cấm. Theo Churilov, hai cơ chế này khiến 68 trong 109 tên bịa chung của 5 LLM không đăng ký được. Kịch bản Faster-GCG cần thêm luật này vào bước kiểm tra tên hợp lệ: ví dụ đổi `o` thành `0` thường vô ích với kẻ tấn công vì sẽ bị chặn.

**Các điểm cần sửa trong đề cương v2:**

| Đề cương v2 ghi | Đề xuất sửa |
| --- | --- |
| Thu thập trên PyPI và npm | Chỉ PyPI; npm chuyển sang phần mở rộng |
| Chưa nêu tên thật lấy từ đâu | Tên thật do chính LLM gợi ý trong cùng câu trả lời |
| Tên bịa là tên không có trên registry | Thêm loại tên nhầm: có trên PyPI nhưng không phải gói đúng |
| Chỉ số: Precision, Recall, F1, AUC-ROC, FPR | Chỉ số chính: TPR@1%FPR; Precision tính theo tỷ lệ thực tế |
| Ràng buộc tấn công: tên hợp lệ, chưa tồn tại, đủ hợp lý | Thêm luật chặn tên gần giống và danh sách tên cấm của PyPI |
| D0 là 1D-CNN, so với RF/XGBoost | Thêm mô hình n-gram và mô hình theo cụm từ con |

## Kế hoạch tiếp theo

| Việc làm | Kết quả |
| --- | --- |
| Tải bộ 0pstech, DepScope, Trend Micro; tải danh sách gói PyPI | Dữ liệu thô, danh sách PyPI có ghi ngày |
| Khảo sát đặc điểm tên bịa trong các bộ công khai | Báo cáo khảo sát dữ liệu |
| Chạy thử 300 câu hỏi trên CodeLlama-13B và DeepSeek-Coder-7B (chi phí dưới 1 USD); huấn luyện mô hình n-gram | Số tên bịa và tên thật không trùng nhau trên 1.000 câu hỏi; mức phân biệt đạt được khi chỉ dùng tên |
| Nếu chạy thử cho kết quả đủ tốt: chạy đủ 5.000 câu hỏi trên 4 LLM | Tập chính hoàn chỉnh |
| Tạo tập kiểm thử nguồn ngoài và tập đo báo nhầm; chia tập; huấn luyện và so sánh 3 mô hình | D0 và kết quả Giai đoạn 1 |

## Các vấn đề kính đề nghị thầy cho ý kiến

1. Dùng tên thật do chính LLM gợi ý trong cùng câu trả lời làm lớp tên thật có phù hợp không?
2. Tên nhầm (có trên PyPI nhưng không phải gói đúng, như `pil`) nên tính là tên bịa như đề xuất, hay tách riêng chỉ để phân tích?
3. Nếu chạy thử cho thấy riêng tên gói chứa ít tín hiệu, có nên cho D0 dùng thêm thông tin ngoài tên (ngữ cảnh câu hỏi, thông tin của gói trên PyPI) không? Việc này làm thay đổi phạm vi “bộ phát hiện chỉ dùng tên” trong đề cương.

## Phụ lục: đính chính số liệu trong báo cáo khảo sát trước

| Nội dung | Báo cáo trước ghi | Bài gốc ghi |
| --- | --- | --- |
| Tỷ lệ lỗi gõ (Spracklen và cộng sự) | 13% là lỗi gõ lệch 1 ký tự | 13,4% cách tên thật 1–2 ký tự; 37,9% cách 3–5; 48,6% cách từ 6 trở lên |
| Cách lấy tên gói (Spracklen và cộng sự) | Lấy từ lệnh `pip install` | 3 lượt hỏi như mô tả ở trên; `pip install` chỉ có ở 7% câu trả lời |
| Độ chính xác nhãn (Twist và cộng sự) | Kiểm tra thủ công 200 mẫu, đúng 95,8% | Lấy mẫu 200 câu trả lời; trong 24 câu trả lời bị gắn cờ, 23 đúng. Khoảng tin cậy 95%: 79,8–99,3% |
| Danh sách gói thật (Churilov) | Không nêu | Dùng danh sách chụp ngày 10/01/2024 cho dữ liệu tháng 4/2026 |

## Tài liệu tham khảo

- D. Arp, E. Quiring, F. Pendlebury, A. Warnecke, F. Pierazzi, C. Wressnegger, L. Cavallaro, K. Rieck. “Dos and Don'ts of Machine Learning in Computer Security.” *USENIX Security Symposium*, 2022. [arXiv:2010.09470](https://arxiv.org/abs/2010.09470)
- A. Churilov. “The Range Shrinks, the Threat Remains: Re-evaluating LLM Package Hallucinations on the 2026 Frontier-Model Cohort.” Bản tiền ấn phẩm, chưa qua bình duyệt, 2026. [arXiv:2605.17062](https://arxiv.org/abs/2605.17062)
- B. Montaruli, L. Compagna, S. E. Ponta, D. Balzarotti. “One Detector Fits All: Robust and Adaptive Detection of Malicious Packages from PyPI to Enterprises.” Bản tiền ấn phẩm, 2025. [arXiv:2512.04338](https://arxiv.org/abs/2512.04338)
- J. Peck, C. Nie, R. Sivaguru, C. Grumer, F. Olumofin, B. Yu, A. Nascimento, M. De Cock. “CharBot: A Simple and Effective Method for Evading DGA Classifiers.” *IEEE Access*, vol. 7, 2019. [arXiv:1905.01078](https://arxiv.org/abs/1905.01078)
- A. Raj, S. Sahu. “Names Can Hurt: Spotting Slopsquatting Risks Caused by Package Name Hallucinations in Local Coding LLMs.” Bản tiền ấn phẩm, 2026. [arXiv:2608.23897](https://arxiv.org/abs/2608.23897)
- J. Spracklen, R. Wijewickrama, A. H. M. N. Sakib, A. Maiti, B. Viswanath, M. Jadliwala. “We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs.” *USENIX Security Symposium*, 2025. [arXiv:2406.10279](https://arxiv.org/abs/2406.10279)
- L. Twist, M. Harman, H. Yannakoudakis, J. M. Zhang. “Library Hallucinations in LLM-Generated Code: A Risk Analysis Grounded in Developer Queries.” Bản tiền ấn phẩm, 2026. [arXiv:2509.22202](https://arxiv.org/abs/2509.22202)
