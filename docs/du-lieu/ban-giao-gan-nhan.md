# Bàn giao việc gán nhãn (26/11/2026)

Tài liệu này dành cho cộng sự nhận tiếp việc gán nhãn bộ dữ liệu tên gói do model ngôn ngữ lớn gợi ý. Nội dung gồm: hiện trạng nhãn, những điểm nhãn còn nói quá bằng chứng, và các việc cần làm theo thứ tự. Quy trình chi tiết nằm ở [quy-trinh-gan-nhan-thu-cong.md](quy-trinh-gan-nhan-thu-cong.md), gọi tắt là "quy trình".

**Thứ tự bắt buộc:** làm xong giai đoạn A (duyệt mù) rồi mới đọc phần còn lại của tài liệu này, từ mục 3 trở đi, và các file nhãn. Lý do: các mục sau có nhãn của người duyệt thứ nhất. Đọc trước thì phép đo mức đồng ý giữa hai người mất giá trị.

## 1. Giai đoạn A: duyệt mù (làm trước tiên)

**Việc cần làm.** Gán nhãn độc lập **toàn bộ 2.167 tên** trong phạm vi duyệt, trong file `R2_P3.csv` (mở được bằng Excel). Với mỗi dòng, điền 3 cột cuối:
- `r2_label`: một trong `real`, `registered_hallucination`, `placeholder`, `uncertain`;
- `r2_criterion`: một trong `D`, `R`, `M`, `S`, `E`, `U`;
- `r2_note`: lý do ngắn.

Không sửa các cột khác, không xóa hay đổi thứ tự dòng. Thời gian ước tính:
- khoảng 700 dự án cũ không có file: chừng 30 giây mỗi tên;
- các tên còn lại: 3–5 phút mỗi tên;
- tổng khoảng 80–110 giờ, chia làm nhiều buổi được.

**Chỉ đọc mục 1–8 của quy trình.** Không đọc mục 9–10 của quy trình, không đọc mục 3 trở đi của tài liệu này, không mở các file nhãn. Không hỏi người khác về nhãn của một tên cụ thể; được hỏi về cách hiểu tiêu chí.

**An toàn (bắt buộc).**
- Không `pip install`, không chạy code của bất kỳ gói nào. Một số gói có thể độc hại.
- Xem code trên trình duyệt: `https://inspector.pypi.io/project/<tên-gói>/` (đọc từng file mà không tải về), hoặc kho mã ở cột `github`.
- Không đăng ký tên gói nào trên PyPI. Không chia sẻ danh sách tên ra ngoài nhóm.

**Các cột quan trọng.**

| Cột | Ý nghĩa |
|---|---|
| `summary`, `desc_head` | Gói tự nhận làm gì: tóm tắt, và 300 ký tự đầu của README |
| `outline` | Dàn ý code: tên file, hàm, lớp. Dùng để so với mô tả |
| `func_lines`, `other_src_lines`, `bin_kb` | Số dòng code Python, số dòng code ngôn ngữ khác, dung lượng phần đã biên dịch. Không tính thư mục đóng gói lẫn vào (`venv/`, `site-packages/`…) |
| `content` | `ok`: đã đọc được file; `api_404`: dự án không còn file nào; `no_files`: dự án chưa từng có file |
| `first_upload` | Ngày tải lên đầu tiên, tính cả bản đã xóa |
| `exists_by` | Với dự án không có ngày tải lên: ngày mà dự án chắc chắn đã tồn tại |
| `after_cutoff` | Kết luận thời gian do máy tính: `yes` là đăng ký sau khi model đã gợi ý tên; `no` là có từ trước; để trống là không kết luận được |
| `pre_registration_models`, `released_before_upload` | Các model đã gợi ý tên trước khi có người đăng ký (theo mốc dữ liệu / theo ngày phát hành model) |
| `defensive_hint`, `defensive_weak` | Cụm kiểu "use X instead" mà máy tìm thấy. Đọc nguyên văn trên trang PyPI rồi mới kết luận |

**Cách quyết định** (chi tiết ở mục 6 quy trình). Xét từ trên xuống, dừng ở bước đầu tiên khớp.
1. **Bản phòng vệ** → `placeholder` / `D`. Gồm: gói không có code riêng mà trỏ sang gói đúng; gói do chủ dự án liên quan giữ; gói do nhà nghiên cứu bảo mật giữ và ghi rõ là vô hại. Lời giữ tên của một cá nhân cho dự án sẽ làm ("coming soon", "name reserved") **không** tính là phòng vệ.
2. **Có code thật** (từ 20 dòng code chức năng, hoặc các trường hợp ở mục 6.1):
   - khớp tóm tắt **hoặc** README → `real` / `R`;
   - làm việc khác hẳn → `uncertain` / `M`;
   - bản sao nguyên vẹn của gói khác dưới tên lạ, hoặc code đã làm rối → `uncertain` / `U`.

   Code mẫu không tính: `hello()`, `add_one`, khung dự án Django mặc định.
3. **Không có code thật**, xét cột `after_cutoff`: `yes` → `registered_hallucination` / `S`; `no` → `placeholder` / `E`; trống → `uncertain` / `U`.
4. **Không chắc** → `uncertain` và ghi lý do. Không đoán.

**Khi xong:** gửi lại file đã điền, kèm ghi chú những chỗ quy trình chưa rõ.

---

*Dừng đọc ở đây cho tới khi nộp xong giai đoạn A.*

---

## 2. Hiện trạng bộ dữ liệu

Trạng thái PyPI lấy theo bản chụp ngày 12/11/2026. Tổng số tên: 79.685.

| Nhãn hiện tại | Số tên | Cách có nhãn | Đã duyệt nội dung |
|---|---|---|---|
| `hallucinated_absent` (tên bịa, chưa ai đăng ký) | 55.898 | máy tra PyPI | không cần |
| `real` | 1.158 | code khớp mô tả, đã duyệt | AI rà (R1) |
| `pre_cutoff_unverified` | 21.198 | máy gán vì có từ trước mốc dữ liệu; quyết định không kiểm nội dung (mục 3.1) | không |
| `placeholder` | 832 | 125 bản phòng vệ + 707 gói rỗng có từ trước mốc | có |
| `stdlib` | 342 | tra danh sách thư viện chuẩn | không cần |
| `registered_hallucination` | 126 | không có nội dung, đăng ký sau khi model đã gợi ý tên | có |
| `known_malicious` | 80 | danh sách gói độc hại công khai | không cần |
| `uncertain` | 51 | bằng chứng không đủ | có |

Toàn bộ 2.167 tên trong phạm vi duyệt mới chỉ do **một** người duyệt rà: người duyệt thứ nhất (R1). R1 là **trợ lý AI**, làm theo quy trình. Chưa có người nào đọc. Mức độ rà không đều:
- phần lớn: chỉ đọc tóm tắt, đầu README và dàn ý code (tên file, hàm, lớp), không đọc toàn bộ mã nguồn;
- khoảng 50 ca nghi vấn: có mở nội dung file.

Vì vậy giai đoạn A là lần **đầu tiên** có người thật kiểm các nhãn này.

## 3. Ba điểm nhãn đang nói quá bằng chứng

Đây là các điểm chủ nhiệm đề tài chỉ ra ngày 26/11/2026. Cả ba cần sửa trước khi viết bài.

### 3.1. "Có từ trước mốc" không đủ để gọi là gói thật

21.198 tên đang mang nhãn `real` chỉ vì gói có từ trước mốc dữ liệu của mọi model đã gợi ý nó. Điều này chỉ chứng minh model không tự bịa ra tên. Nó **không** chứng minh gói có code thật: trong nhóm này vẫn có thể có gói rỗng, gói giữ chỗ, gói đã bỏ, hay gói xấu chưa bị phát hiện.

**Quyết định (26/11/2026): không kiểm nhóm này.** Chủ nhiệm đề tài quyết định bỏ qua việc kiểm nội dung 21.198 gói, vì khối lượng quá lớn (ước tính khoảng 7.000 gói phải đọc toàn bộ mã nguồn). Hệ quả:
1. Đổi tên nhãn của nhóm này thành `pre_cutoff_unverified` ("có từ trước mốc, chưa kiểm nội dung"). Chỉ các tên đã được duyệt mới giữ nhãn `real`.
2. Không gọi nhóm này là "gói thật" trong bài. Phân tích nào cần lớp "gói thật" thì chỉ dùng các tên đã duyệt. Nếu buộc phải dùng nhóm này, ví dụ làm mẫu âm cho bộ phát hiện, thì ghi rõ đó là giới hạn.
3. Điều chắc chắn về nhóm này chỉ có một: **không tên nào trong nhóm có thể là tên bịa đã bị đăng ký**, vì gói có từ trước khi model biết đến (mục 3 của quy trình).

### 3.2. "Đăng ký sau khi model phát hành" không đủ để gọi là bị chiếm tên

Trong 126 tên `registered_hallucination`, 92 tên được đăng ký sau ngày phát hành của ít nhất một model đã gợi ý tên. Điều này chắc chắn về **thời gian**: tên do model bịa ra trước, người đăng ký đến sau. Nhưng nó **không** chứng minh người đăng ký có ý đồ: họ có thể tình cờ đặt trùng tên, hoặc định làm một dự án thật. Thêm vào đó, 37/126 tên đã bị gỡ hết file, nên không biết gói từng chứa gì.

**Việc cần làm:**
1. Đổi cách gọi trong bài và tài liệu: "tên bịa đã có người đăng ký, không có nội dung". Bỏ chữ "bị chiếm" khi chưa có bằng chứng về ý đồ.
2. Tách thành hai nhóm: 89 tên còn file và rỗng; 37 tên mất hết file (nội dung không quan sát được).
3. Ghi thêm cột "dấu hiệu chủ đích" cho từng tên. Chỉ ghi khi có bằng chứng; không có thì để trống. Các dấu hiệu:
   - một tài khoản giữ nhiều tên bịa: xem các gói khác của chủ sở hữu trên trang PyPI;
   - nhiều tên được đăng ký dồn trong vài ngày (ví dụ một loạt gói ngày 04–08/06/2026, nay đều đã mất file);
   - gói bị PyPI gỡ: kiểm cơ sở dữ liệu OSV (mục MAL);
   - tên có trong các danh sách tên bịa đã công bố (0pstech, DepScope, Trend Micro);
   - gói dùng mẫu giữ chỗ giống hệt nhau giữa nhiều tên.

### 3.3. Nhóm "không chắc" phải được rà theo phương pháp rõ ràng

51 tên `uncertain` đã được R1 rà nhưng bằng chứng chưa đủ. Mỗi lý do có một cách rà riêng:

| Lý do | Số tên | Cách rà |
|---|---|---|
| Dự án không còn file | 28 | Tìm nội dung cũ: bản lưu trên Wayback Machine (`web.archive.org/web/*/pypi.org/project/<tên>*`), bộ dữ liệu PyPI công khai trên BigQuery (bảng `distribution_metadata`, có metadata cả file đã xóa: ngày tải lên, tóm tắt), deps.dev, OSV |
| Code không khớp mô tả | 7 | Đọc toàn bộ code; xem các gói khác cùng chủ sở hữu |
| Chỉ có model có mốc "giới hạn trên" gợi ý (MiMo, Qwen3.5) | 7 | Xét thêm ngày phát hành của model đó; tìm mốc dữ liệu chính thức nếu hãng đã công bố |
| Mã làm rối hoặc chỉ có phần đã biên dịch | 6 | Tìm kho mã nguồn và tác giả; đối chiếu với tên gói |
| Bắt chước gói khác | 3 | So sánh với gói gốc (phiên bản, file, tác giả); xem tài khoản đăng |

Sau khi rà, ca nào vẫn không kết luận được thì giữ `uncertain`, ghi rõ đã rà những nguồn nào, và báo cáo riêng. Cách rà ở bảng trên cần được viết thành một mục mới trong quy trình (bản P4) trước khi áp dụng, để hai người duyệt làm giống nhau.

## 4. Thứ tự công việc

1. **Giai đoạn A** (mục 1): cộng sự duyệt mù toàn bộ 2.167 tên. Sau đó chạy `python -m slopcollect.review.agreement kappa`:
   - kappa trên toàn bộ 2.167 tên là con số báo cáo trong bài, kèm bảng chéo theo từng nhãn;
   - các tên hai người lệch nhau được bàn để thống nhất.
2. **Viết quy trình P4**, gồm:
   - đổi tên nhãn theo mục 3.1 và 3.2;
   - cột "dấu hiệu chủ đích";
   - phương pháp rà sâu cho nhóm không chắc (mục 3.3);
   - nhánh phân loại tự động cho nhóm có từ trước mốc.
3. **Mục 3.1:** đổi tên nhãn nhóm 21.198 gói thành `pre_cutoff_unverified`; không kiểm nội dung (đã quyết định bỏ qua).
4. **Mục 3.2:** tách 37 tên mất file, ghi dấu hiệu chủ đích cho 126 tên.
5. **Mục 3.3:** rà sâu 51 tên không chắc. Hai người làm độc lập, rồi đối chiếu.
6. Chạy lại bước gán nhãn và `python -m slopcollect.review.summary`, rồi cập nhật mục kết quả của quy trình.

## 5. File và lệnh

Các file trong `data/review/` không nằm trong git. Chủ nhiệm đề tài gửi trực tiếp.

| File | Nội dung | Gửi khi nào |
|---|---|---|
| `R2_P3.csv` | phiếu duyệt mù 2.167 tên | giai đoạn A |
| `R2_P3_key.csv` | tên nào thuộc nhóm khó (S, D, không chắc, R1 khác công cụ, sát ngưỡng) | **không gửi** cho người duyệt; chỉ dùng khi tính kappa |
| `review_P3.csv` | phiếu bằng chứng đầy đủ của 2.167 tên | sau giai đoạn A |
| `overrides.csv` | nhãn của R1, kèm mã tiêu chí và ghi chú bằng chứng | sau giai đoạn A |
| `overrides_P2.csv`, `overrides_P0.csv` | nhãn các đợt trước | khi cần đối chiếu |

| Lệnh | Việc |
|---|---|
| `python -m slopcollect --db data/slop.sqlite stage label` | gán nhãn lại (nhãn trong `overrides.csv` được áp trước mọi luật) |
| `python -m slopcollect.review.evidence` | thu bằng chứng, tạo `review_P3.csv` |
| `python -m slopcollect.review.agreement sample` / `kappa` | tạo phiếu duyệt mù / tính mức đồng ý |
| `python -m slopcollect.review.summary` | in số nhãn và bảng độ nhạy theo mốc |

Nguyên tắc đạo đức áp dụng cho mọi bước:
- không đăng ký tên nào;
- không cài hay chạy gói;
- không công bố danh sách tên bịa chưa đăng ký.
