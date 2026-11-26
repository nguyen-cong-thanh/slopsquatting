# Quy trình gán nhãn tên gói (phiên bản P3, 26/11/2026)

Tài liệu này quy định cách mỗi tên gói do model gợi ý nhận nhãn: phần nào máy tự quyết, phần nào người phải đọc, đọc theo tiêu chí gì và kiểm lại ra sao. Phần phương pháp của bài báo và người duyệt thứ hai đều dùng đúng văn bản này. Muốn sửa tiêu chí thì phải nâng phiên bản và ghi lý do ở mục 10.

## 1. Bức tranh tổng thể

Đơn vị gán nhãn là một **tên gói đã chuẩn hóa** theo PEP 503 mà ít nhất một model đã gợi ý. Trạng thái trên PyPI lấy theo bản sao danh sách ngày 12/11/2026.

```
Mọi tên model gợi ý
│
├─ BƯỚC 1. Máy tự quyết (tất định, không cần người)
│    không có trên PyPI          → hallucinated_absent
│    trùng tên thư viện chuẩn     → stdlib
│    có trong danh sách độc hại  → known_malicious
│
└─ Tên có trên PyPI
     │
     ├─ BƯỚC 2. Lưới lọc (máy): tên có đáng ngờ không? (mục 3)
     │    không đáng ngờ → real (không ai đọc)
     │    đáng ngờ       → bước 3
     │
     ├─ BƯỚC 3. Duyệt từng tên đáng ngờ
     │    3a. Máy thu bằng chứng (mục 4)
     │    3b. Máy đề xuất nhãn theo cây quyết định (mục 6)
     │    3c. Người đọc MỌI tên, quyết định nhãn, ghi vào overrides.csv (mục 7)
     │
     └─ BƯỚC 4. Kiểm chất lượng: người thứ hai dán nhãn mù một mẫu, đo kappa (mục 8)

Chạy lại bước label: nhãn trong overrides.csv được áp trước mọi luật của máy.
```

Lệnh chạy theo thứ tự:

| Bước | Lệnh | Kết quả |
|---|---|---|
| 1–2 | `python -m slopcollect --db data/slop.sqlite stage label` | bảng `labels`; tên đáng ngờ chưa duyệt có `needs_review = 1` |
| 3a–3b | `python -m slopcollect.review.evidence` | phiếu duyệt `data/review/review_P3.csv` |
| 3c | người duyệt đọc phiếu, ghi `data/review/overrides.csv` | rồi chạy lại lệnh của bước 1–2 |
| 4 | `python -m slopcollect.review.agreement sample`, sau đó `… kappa` | mẫu cho người thứ hai, hệ số kappa |
| báo cáo | `python -m slopcollect.review.summary` | số nhãn, độ nhạy theo mốc (mục 5) |

## 2. Các nhãn

| Nhãn | Định nghĩa vận hành |
|---|---|
| `hallucinated_absent` | Tên không có trên PyPI: model bịa ra và chưa ai đăng ký. |
| `real` | Gói có **nội dung chức năng** (mục 6.1), và nội dung đó **khớp với điều gói tự nhận** (mục 6.2). Nếu tên trùng với một tên bịa thì coi là trùng hợp: người khác đã dùng tên đó cho một dự án thật. |
| `registered_hallucination` (bị chiếm tên) | Gói **không có nội dung chức năng**, **không phải** bản phòng vệ, và được đăng ký **sau khi** ít nhất một model đã nói ra cái tên (mục 5). Nhãn mô tả **tình trạng của tên**: một người lạ đang giữ tên bịa mà không đặt nội dung gì vào. Nhãn không khẳng định người giữ có ý đồ xấu. |
| `placeholder` (giữ chỗ) | Gói không có nội dung chức năng **riêng**, và rơi vào một trong hai trường hợp. (a) **Bản phòng vệ**: trỏ sang gói đúng; do chủ dự án liên quan giữ (tổ chức, hãng, người duy trì); hoặc do nhà nghiên cứu bảo mật giữ, kèm lời ghi rõ là vô hại hay để chống chiếm tên. (b) **Có từ trước** mốc dữ liệu của mọi model đã gợi ý nó, nên model có thể đã thấy tên trên PyPI chứ không tự bịa. |
| `uncertain` (không chắc) | Bằng chứng thiếu hoặc mâu thuẫn. Báo cáo riêng, loại khỏi các phân tích chính. |
| `stdlib`, `known_malicious` | Xem bước 1. |

## 3. Bước 2: lưới lọc

Một tên có trên PyPI được đưa đi duyệt nếu thỏa **ít nhất một** điều kiện dưới đây. Mỗi điều kiện là một luật trong `src/slopcollect/stages/label.py`.

| Luật | Điều kiện |
|---|---|
| `after_model_cutoff` | Tiêu chí thời gian (mục 5) **không** kết luận được là gói có từ trước mốc, tức là kết quả `after` hoặc `unknown`. |
| `empty_project` | Dự án không có file phát hành nào. |
| `placeholder` | Tóm tắt, hoặc mô tả ngắn dưới 400 ký tự, có cụm kiểu giữ chỗ: "deprecated", "use X instead", "reserved", "security holding"… |
| `known_hallucination` | Tên có trong danh sách tên bịa đã công bố (0pstech, DepScope). |
| `young_low_downloads` | Gói ra đời trong 180 ngày gần nhất và có từ 1.000 lượt tải/tháng trở xuống. |
| (thêm khi lập phiếu) | Gói đang là `real` mà tóm tắt có lời phòng vệ mạnh (mục 4); và mọi tên đã duyệt ở các đợt trước. |

Tên **không** thỏa điều kiện nào thì được gán `real` mà không ai đọc. Lưới lọc đặt như vậy để đảm bảo một điều: **tên lọt lưới không thể là `registered_hallucination`**. Lý do là luật `after_model_cutoff` dùng **cùng một hàm** (`slopcollect.timing`) với cây quyết định ở bước 3, nên mọi tên mà cây quyết định có thể gán S đều bị lưới giữ lại.

Giới hạn: một số tên lọt lưới có thể là gói rỗng có từ trước mốc. Theo cây quyết định, các tên này lẽ ra là `placeholder` (E), nhưng ở đây chúng mang nhãn `real`. Sai lệch này không ảnh hưởng tới lớp `registered_hallucination`.

## 4. Bước 3a: bằng chứng thu cho mỗi tên

Công cụ `python -m slopcollect.review.evidence` thu các bằng chứng dưới đây vào phiếu `data/review/review_P3.csv`. **Không cài và không chạy** gói nào: file phát hành chỉ được đọc trong bộ nhớ.

- **PyPI:** tóm tắt, mô tả (300 ký tự đầu), phiên bản, số file, các phụ thuộc khai báo, số chủ sở hữu, có thuộc tổ chức hay không, các link, trạng thái API.
- **Thời gian** (mục 5):
  - lần tải lên đầu tiên, tính cả bản đã xóa (ClickPy);
  - các model đã gợi ý tên, với mốc dữ liệu và ngày phát hành của từng model (`configs/cutoffs.toml`);
  - kết luận của tiêu chí thời gian;
  - các model đã gợi ý tên trước khi có người đăng ký;
  - các model đã **phát hành** trước khi có người đăng ký;
  - với dự án không có ngày tải lên: ngày muộn nhất mà dự án chắc chắn đã tồn tại (`exists_by`).
- **Lượt tải và GitHub:** lượt tải tháng gần nhất; kho mã có tồn tại không, số sao; link kho mã đã được PyPI xác minh chưa.
- **Nội dung gói:** đọc file phát hành của phiên bản mới nhất. Ưu tiên wheel `-none-any`, rồi đến wheel khác, cuối cùng là sdist. File trên 50 MB thì không tải. Từ file này lấy:
  - số dòng code chức năng (mục 6.1) và số dòng mã nguồn ngôn ngữ khác;
  - dung lượng phần đã biên dịch (`.so`, `.pyd`, `.dylib`, `.dll`) và tệp thực thi đóng kèm (`*.data/scripts/`, `bin/`) từ 1 MB trở lên;
  - **dàn ý code** (`outline`): các file `.py`, tên hàm và lớp ở cấp module, kèm phương thức của lớp, và các file mã nguồn khác. Dàn ý dùng để đối chiếu với mô tả (mục 6.2).
- **Lời phòng vệ**, hai mức:
  - *mạnh*, xét cho mọi gói: "use X instead", "not the correct…", "security hold", "reserved by/for", "dependency confusion", "slopsquat", "PoC"…;
  - *yếu*, chỉ xét khi gói không có code: "dummy package", "deprecated", "obsolete", "transitional", "placeholder package", "you might be looking for"….

  Công cụ chỉ đánh dấu các cụm này. Người duyệt phải đọc nguyên văn rồi mới quyết định.

## 5. Tiêu chí thời gian

**Câu hỏi:** model đã nói ra cái tên này *trước khi* có người đăng ký nó chưa? Nếu rồi, tên do model bịa ra, người đăng ký đến sau. Nếu gói có từ trước, model có thể đã học được tên từ dữ liệu huấn luyện.

**Mốc dữ liệu.** Mỗi model có một mốc dữ liệu (knowledge cutoff) ghi trong `configs/cutoffs.toml`, kèm loại nguồn: hãng công bố, hoặc thông tin cộng đồng. Khi các nguồn lệch nhau thì lấy mốc muộn hơn. Với vài model, mốc chỉ là **giới hạn trên** (`bound = "upper"`, lấy theo ngày phát hành), vì hãng không công bố.

Hàm `slopcollect.timing.timing` trả về một trong ba kết luận:

| Kết luận | Điều kiện |
|---|---|
| `after` | Có **ít nhất một** model đã gợi ý tên mà mốc dữ liệu cộng 30 ngày sớm hơn lần tải lên đầu tiên. |
| `before` | Lần tải lên đầu tiên không muộn hơn mốc cộng 30 ngày của **mọi** model đã gợi ý tên. Có hai ràng buộc: (1) nếu một model chỉ có mốc giới hạn trên thì gói còn phải ra đời trước mốc chính xác sớm nhất trong nghiên cứu (31/10/2023), vì mốc thật của model đó có thể sớm hơn nhiều; (2) dự án chỉ có metadata, chưa từng có lần tải lên, cũng là `before`, vì PyPI.org (Warehouse, từ 04/2018) chỉ tạo dự án khi có file tải lên. |
| `unknown` | Các trường hợp còn lại: thiếu ngày tải lên, có model chưa rõ mốc, hoặc chỉ có mốc giới hạn trên. |

**Dự án không có ngày tải lên** (dự án còn trong danh sách PyPI nhưng không còn file nào). Công cụ lấy số thứ tự của sự kiện cuối cùng trên dự án (`_last-serial`, Simple API) rồi đổi ra ngày. Bảng đổi được lập từ các gói chỉ có một file trong dữ liệu: serial của PyPI tăng theo thời gian, nên serial của các gói này cho biết ngày tương ứng. Dự án chắc chắn đã tồn tại trước ngày đó (`exists_by`). Nếu ngày này có từ trước mốc theo quy tắc `before` thì kết luận là `before`; ngược lại là `unknown`.

**Vì sao chỉ cần một model.** Chỉ cần một model nói ra cái tên trước khi có người đăng ký là đủ cho thấy tên do model bịa. Nếu đòi điều kiện với mọi model, một model ra đời muộn sẽ che mất những model đã gợi ý tên từ trước.

**Độ tin cậy của mốc.** Mốc dữ liệu là ước lượng. Nếu mốc thật muộn hơn mốc đã ghi, model có thể đã thấy gói khi huấn luyện, và nhãn S sẽ sai. Có hai cách kiểm, cả hai được báo cáo cùng kết quả:

1. **Căn cứ chắc chắn: ngày phát hành model.** Lấy theo ngày tạo kho trọng số trên Hugging Face, ghi ở trường `released`. Trọng số đã công bố không thể chứa dữ liệu sinh ra sau ngày công bố. Vì vậy, nếu gói được đăng ký sau ngày phát hành của một model đã gợi ý nó, thì chắc chắn model không học tên từ gói đó. Ngày tạo kho sát ngày công bố, thường sớm hơn vài ngày.
2. **Độ nhạy theo khoảng đệm.** Tính lại số tên S khi khoảng đệm sau mốc tăng từ 30 ngày lên 90, 180, 365 và 730 ngày.

Hai cách này **không đổi nhãn**. Chúng cho biết bao nhiêu nhãn S còn đứng vững nếu mốc sai.

**Không tính tới tra web.** Model được gọi qua API, không bật công cụ nào, nên chỉ trả lời từ dữ liệu đã học. Trợ lý code có tra web là một kịch bản khác, nằm ngoài phạm vi nghiên cứu.

## 6. Bước 3b–3c: tiêu chí và cây quyết định

### 6.1. Nội dung chức năng

**Đếm dòng code chức năng.** Áp dụng cho file `.py` và `.pyi`, bỏ `setup.py`, `conftest.py`, thư mục `tests/` và `test/`, các file `test_*.py`, và các thư mục đóng gói lẫn vào (`venv/`, `.venv/`, `site-packages/`, `.tox/`, `node_modules/`, `__pycache__/`, `.git/`, `.ccls-cache/`). Lý do bỏ nhóm cuối: đó là code của thư viện khác, nếu đếm vào thì một gói rỗng có thể vượt ngưỡng chỉ nhờ kèm theo cả môi trường ảo. Mỗi file được phân tích cú pháp (AST). Kết quả là số dòng mã nguồn khác nhau có câu lệnh, **không tính**: `import`; docstring và chuỗi đứng riêng; `pass` và `...`; lệnh gán cho tên dạng `__x__`. Dòng trống và comment không bao giờ được tính. File lỗi cú pháp thì đếm các dòng không trống và không bắt đầu bằng `#`.

**Gói có nội dung chức năng** nếu thỏa **một** trong các điều kiện:
1. Có từ **20 dòng** code chức năng trở lên, hoặc từ **20 dòng** mã nguồn ngôn ngữ khác trở lên.
2. Có phần đã biên dịch từ **10 KB** trở lên, hoặc tệp thực thi đóng kèm từ **1 MB** trở lên, **và** có mô tả hoặc kho mã cho biết phần đó làm gì. Nếu không có mô tả lẫn kho mã thì gán `uncertain`, vì không kiểm được nội dung.
3. **Gói meta:** không có code nhưng khai báo phụ thuộc, và mô tả nói rõ mục đích là cài các gói đó. Ví dụ: `cuda-toolkit` của NVIDIA.
4. **Gói dữ liệu:** nội dung nằm trong tệp dữ liệu (JSON, bảng) và khớp với mô tả.
5. Chức năng nằm trong `setup.py` (ví dụ tải dữ liệu khi cài) và khớp với mô tả.
6. **Dưới ngưỡng nhưng code làm đúng việc mô tả**, ví dụ một hàm 10 dòng đổi mã màu hex sang RGB. Người duyệt phải ghi lý do.

**Không bao giờ được tính là nội dung chức năng:** code mẫu (cookiecutter, `hello()`, CLI rỗng, component mẫu chưa build); tệp chỉ có số phiên bản.

### 6.2. Khớp với điều gói tự nhận

- **Gói tự nhận làm gì** được xác định từ tóm tắt và mô tả (README). Nếu gói không có cả hai thì dùng tên gói.
- **Code làm gì** được xác định từ dàn ý code (`outline`). Nếu dàn ý chưa đủ rõ thì đọc file chính trên trang PyPI hoặc trong kho mã.
- **Khớp:** chức năng chính của code nằm trong phạm vi mà tóm tắt **hoặc** mô tả nêu ra. Chỉ cần một trong hai, vì tóm tắt hay bị bỏ quên khi gói đổi hướng. Ví dụ: `groovy` của Gradio vẫn để tóm tắt cũ về chống SSRF, trong khi README và code đều là bộ chuyển Python sang JavaScript. Không đòi code làm đủ mọi điều mô tả hứa: gói đang làm dở vẫn tính là khớp.
- **Không khớp:** code làm một việc khác hẳn cả tóm tắt lẫn mô tả. Ví dụ: tóm tắt ghi "AUC network" nhưng code là máy tính cộng trừ.
- **Không có tóm tắt lẫn mô tả:** so code với tên gói. Nếu tên không nói lên chức năng gì thì code phải là một chương trình có chủ đích rõ ràng, không phải code mẫu.
- **Bắt chước:** gói chép đặc điểm của một gói nổi tiếng (tên, số phiên bản, mô tả) mà code chỉ ở mức tối thiểu; hoặc gói là **bản sao nguyên vẹn của một gói khác** đăng dưới một tên không liên quan. Ví dụ: `fiddler` chứa nguyên gói `oso` 0.11.1, kể cả tên tác giả "Oso Security, Inc.".
- **Mã đã làm rối hoặc mã hóa** (pyarmor, tệp `.dat` cần trình giải mã): không đọc được nên không kiểm được, gán `uncertain` (U).

### 6.3. Cây quyết định

Xét lần lượt từ trên xuống, dừng ở bước đầu tiên khớp. Mỗi quyết định ghi kèm một mã tiêu chí.

1. **Bản phòng vệ?** Gói không có nội dung chức năng *riêng* (dưới ngưỡng, hoặc chỉ là lớp vỏ gọi sang gói khác) **và** thỏa trường hợp (a) của nhãn `placeholder`. Gán `placeholder`, mã **D**.
   - Gói đã ngừng phát triển nhưng vẫn có code (dù có câu "deprecated, use X instead") thì là `real`.
   - Lời giữ tên của một cá nhân cho dự án sẽ làm ("coming soon", "name reserved for my project") **không** tính là phòng vệ.
2. **Có nội dung chức năng** (6.1)?
   - Có, và khớp với điều gói tự nhận (6.2): `real`, mã **R**.
   - Có, nhưng không khớp: `uncertain`, mã **M**.
   - Có, nhưng có dấu hiệu bắt chước: `uncertain`, mã **U**.
3. **Không có nội dung chức năng**, kể cả khi gói không có file nào hoặc đã bị gỡ. Xét tiêu chí thời gian (mục 5):
   - `after`: `registered_hallucination`, mã **S**;
   - `before`: `placeholder`, mã **E**;
   - `unknown`: `uncertain`, mã **U**.

## 7. Bước 3c: người duyệt đọc và ghi kết quả

**Người duyệt đọc mọi tên trong phiếu.** Đề xuất của công cụ chỉ giúp đọc nhanh hơn. Với mỗi tên, người duyệt:
1. đọc tóm tắt, mô tả và dàn ý code, rồi kết luận có nội dung chức năng hay không (6.1) và có khớp hay không (6.2);
2. đọc nguyên văn mọi lời phòng vệ mà công cụ đã đánh dấu;
3. kiểm tiêu chí thời gian (mục 5) khi gói không có nội dung;
4. mở trang PyPI hoặc kho mã khi các bước trên chưa đủ, ví dụ khi số dòng sát ngưỡng (10–40 dòng), gói có thể là gói meta, hoặc đề xuất khác nhãn cũ.

Kết quả ghi vào `data/review/overrides.csv`, mỗi tên một dòng:

| Cột | Nội dung |
|---|---|
| `norm_name` | tên gói đã chuẩn hóa |
| `override_label` | nhãn |
| `criterion` | mã tiêu chí: D, R, M, S, E hoặc U |
| `note` | bằng chứng quyết định và các số đo |
| `review_mode` | `manual`: người duyệt đã đọc |
| `reviewer` | người duyệt |
| `reviewed_at` | ngày duyệt |
| `protocol` | phiên bản quy trình |

Bước `label` áp các nhãn này trước mọi luật khác. Kết quả của các đợt trước được lưu riêng: P0 ở `data/review/overrides_P0.csv`, P2 ở `data/review/overrides_P2.csv`.

## 8. Bước 4: kiểm soát chất lượng

- **Người duyệt thứ nhất (R1)** đọc toàn bộ phạm vi (bước 3c). Ở đợt P3, R1 là trợ lý AI (Claude) làm việc theo đúng tài liệu này; bài báo phải ghi rõ điều đó, và vì vậy phép đo đồng ý với người duyệt thứ hai là bắt buộc.
- **Người duyệt thứ hai (R2)** duyệt độc lập một mẫu 100 tên, phân tầng theo nhãn của R1. R2 chỉ thấy bằng chứng, không thấy nhãn của R1, và chỉ dùng tài liệu này.
  - **File mẫu:** `data/review/R2_sample_P3.csv`, tạo bằng `python -m slopcollect.review.agreement sample`. Mẫu gồm 30 tên `real`, 30 `registered_hallucination`, 30 `placeholder` và 10 `uncertain` theo nhãn của R1, đã trộn thứ tự. File mở được bằng Excel.
  - **Cách điền:** R2 đọc bằng chứng trong file, có thể mở trang `pypi_url` và kho mã, nhưng **không cài gói**. Sau đó R2 điền `r2_label` (`real`, `registered_hallucination`, `placeholder` hoặc `uncertain`), `r2_criterion` (D, R, M, S, E hoặc U) và `r2_note` (lý do ngắn).
  - **Tính kết quả:** `python -m slopcollect.review.agreement kappa` in tỷ lệ đồng ý, Cohen's kappa, bảng chéo và các tên hai người khác nhau.
- Những tên hai người khác nhau được bàn để thống nhất. Bài báo báo cáo kappa **trước** khi thống nhất, và số tên đã đổi nhãn sau khi thống nhất.

## 9. Kết quả áp dụng P3 (26/11/2026)

Số liệu in bằng `python -m slopcollect.review.summary`.

| Nhóm | Số tên |
|---|---|
| Tổng số tên model gợi ý | 79.685 |
| Bước 1: không có trên PyPI / thư viện chuẩn / độc hại đã biết | 55.898 / 342 / 80 |
| Bước 2: lọt lưới, gán `real` mà không đọc | 21.198 |
| Bước 3: đưa đi duyệt, người đọc từng tên | 2.167 |

Kết quả bước 3 theo mã tiêu chí: R 1.158, E 707, S 126, D 125, U 44, M 7. Theo nhãn: `real` 1.158, `placeholder` 832, `registered_hallucination` 126, `uncertain` 51.

Độ tin cậy của 126 nhãn S (mục 5):

| Căn cứ | Số tên S còn đứng |
|---|---|
| Đăng ký sau ngày **phát hành** của ít nhất một model đã gợi ý (chắc chắn) | 92 |
| Khoảng đệm sau mốc 30 ngày (mặc định) | 126 |
| 90 ngày | 120 |
| 180 ngày | 108 |
| 365 ngày | 80 |
| 730 ngày | 29 |

So với P2:
- Lưới lọc mới giữ lại thêm 579 tên: 214 tên có kết luận thời gian `after` và 365 tên `unknown`. Trong số này, 35 tên là S và 40 tên là `uncertain`.
- Trong 1.588 tên đã duyệt ở P2, 11 tên đổi nhãn.
- Trong 610 tên P2 nhận là `real` theo đề xuất, việc đối chiếu code với mô tả tìm ra:
  - các ca bắt chước, ví dụ `perfview` là bản sao nguyên vẹn của `rich`, đăng sau khi model đã gợi ý tên;
  - các ca code không khớp mô tả, gán `uncertain`.

## 10. Lịch sử phiên bản

- **P0 (14/11 và 26/11/2026):** hai đợt duyệt chưa có quy trình viết sẵn. Đợt 14/11 quyết định dựa trên metadata (dung lượng gói, độ dài mô tả, có kho mã hay không). Đợt 26/11 có mở và đọc nội dung các gói nhỏ.
- **P1 (26/11/2026):** bản viết đầu tiên, soạn trước khi kiểm lại. Đặt ngưỡng 20 dòng code chức năng. Gói rỗng do cá nhân giữ tên được tính là `registered_hallucination` nếu ra đời sau mốc.
- **P2 (26/11/2026):** sửa trong lượt duyệt đầu tiên theo P1.
  1. Tiêu chí thời gian chỉ cần **một** model đã gợi ý tên trước khi tên được đăng ký. P1 đòi gói ra đời sau mốc muộn nhất của các model gợi ý.
  2. Thêm cách xử lý mốc chỉ là giới hạn trên, và dự án chỉ có metadata từ PyPI cũ.
  3. Tách lời phòng vệ thành hai mức mạnh và yếu. Thêm trường hợp nhà nghiên cứu bảo mật giữ tên kèm lời ghi vô hại.
  4. Thêm các loại nội dung chức năng: gói meta, gói dữ liệu, tệp thực thi đóng kèm, chức năng trong `setup.py`.
  5. Phạm vi duyệt thêm các gói đang là `real` nhưng tóm tắt có lời phòng vệ.
- **P3 (26/11/2026):** làm kín quy trình sau khi rà lại toàn bộ luồng.
  1. **Lưới lọc dùng chung tiêu chí thời gian với cây quyết định** (cùng hàm `slopcollect.timing`). Ở P2, lưới vẫn dùng tiêu chí của P1, nên 214 tên đáng ngờ theo P2 đã lọt lưới và bị gán `real` mà không ai đọc. Lưới cũng giữ lại các tên mà tiêu chí thời gian không kết luận được (`unknown`, 365 tên).
  2. Luật `after_model_cutoff` chỉ còn lọc, không tự quyết nhãn.
  3. **Định nghĩa "khớp với điều gói tự nhận"** (6.2). Công cụ lập dàn ý code để đối chiếu. Ở P2, 610 tên `real` được nhận theo đề xuất của công cụ mà chưa ai đối chiếu code với mô tả.
  4. **Người duyệt đọc mọi tên trong phiếu**. Bỏ chế độ nhận đề xuất tự động (`review_mode = auto`).
  5. Thêm **ngày phát hành model** làm căn cứ thời gian chắc chắn, và bảng độ nhạy theo khoảng đệm.
  6. Dự án không có ngày tải lên được định ngày nhờ `_last-serial` (`exists_by`).
  7. Không đếm code trong các thư mục đóng gói lẫn vào (`venv/`, `site-packages/`…).
  8. "Khớp" chỉ cần khớp tóm tắt **hoặc** mô tả. Thêm hai trường hợp đều gán `uncertain`: bản sao nguyên vẹn của gói khác (bắt chước) và mã đã làm rối.
