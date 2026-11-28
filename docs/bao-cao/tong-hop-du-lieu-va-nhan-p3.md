# Tổng hợp dữ liệu và nhãn P3

**Bản dữ liệu:** `p3-consolidated-v1` · **Trạng thái:** tạm thời, chưa duyệt độc lập R2. Báo cáo này cập nhật phần dữ liệu và nhãn của [báo cáo tiến độ 15/11](bao-cao-tien-do-15-11.md), không thay thế kết quả thí nghiệm lịch sử. Định nghĩa nhãn gốc theo [quy trình P3](../du-lieu/quy-trinh-gan-nhan-thu-cong.md); quyết định giữ riêng bằng chứng thiếu theo [bàn giao gán nhãn](../du-lieu/ban-giao-gan-nhan.md).

## Phạm vi và nguồn

| Đơn vị | Số lượng | Ghi chú |
|---|---:|---|
| Đề bài | 18.033 | Tập Spracklen sau bỏ trùng |
| Câu trả lời lưu trong SQLite | 515.724 | 22 cấu hình model; 7 phủ đủ đề ở cả ba tác vụ |
| Dòng trích `x4` | 1.778.581 | Một tên chuẩn hóa trên một câu trả lời và một phương pháp; không phải số tên duy nhất |
| Tên có nhãn P3 | 79.685 | Một dòng mỗi tên; gồm mọi model và phương pháp trích trong DB chính |
| Project trong snapshot PyPI | 937.845 | `pypi-20261112T031153-43535604`; sự tồn tại chỉ có nghĩa tại snapshot |

`data/slop.sqlite` là nguồn gốc, không sửa đổi. Dữ liệu GLM đã nằm trong DB này; không cộng lại từ `incoming/`. Không trộn `smoke.sqlite` hay bản sao `backup/` vào corpus. Trong `runs`, lần gắn nhãn P3 được dùng là `20261126T153806-e61191`. Lần `stats` và `export` thành công cuối được ghi nhận trước lần label này, vì vậy không mặc định Parquet hoặc detector cũ chứa nhãn hiện hành dù cùng ghi `rules-v3`.

Khi so sánh model, tách lượt gốc (`root_sample_idx = 0`) khỏi pilot và lượt hỏi lại. Cohort nghiên cứu chính gồm Mistral Small 3.2, Qwen3.6, Nemotron 3.5, DeepSeek V4.1 Flash và MiMo V2.6 Pro; Llama 3.1 8B và GLM 5.3 là hai đối chứng có đủ lượt gốc. Nếu đối chiếu số liệu Spracklen theo cách của project, chỉ lấy `pip_install` và `llm_list`, ghi rõ đơn vị là lượt trích hay tên riêng; không dùng số 79.685 làm mẫu số cho phép so sánh đó.

## Kết quả gán nhãn

| Nhãn | `label_p3` nguyên trạng | `label_analysis` bảo thủ |
|---|---:|---:|
| `hallucinated_absent` | 55.898 | 55.898 |
| `pre_cutoff_unverified` | 21.198 | 21.198 |
| `real` | 1.158 | 1.154 |
| `placeholder` | 832 | 672 |
| `stdlib` | 342 | 342 |
| `registered_hallucination` | 126 | 89 |
| `known_malicious` | 80 | 80 |
| `uncertain` | 51 | 252 |
| **Tổng** | **79.685** | **79.685** |

- `label_p3` giữ nguyên quyết định SQLite, gồm **77.518** nhãn tự động và **2.167** override của R1 (AI). `pre_cutoff_unverified` không phải gói thật đã xác minh và không tự động vào lớp âm. `hallucinated_absent` chỉ xác nhận tên vắng theo snapshot và quy tắc P3, không xác nhận tên đăng ký được hay chưa từng tồn tại.
- `label_analysis` chỉ đổi **201** dòng sang `uncertain` để không dùng bằng chứng phát hành không quan sát được làm nhãn chắc chắn: **160** `placeholder` tiêu chí E và **37** `registered_hallucination` tiêu chí S có `api_404`; **4** `real` tiêu chí R có `too_large`. Không phủ quyết R1 hay nhận là đã duyệt lại; mọi nhãn gốc, mã tiêu chí, trạng thái bằng chứng và lý do đổi được giữ riêng. `no_files` chỉ nói phiếu hiện có không thấy file, không chứng minh lịch sử chưa từng có file.
- **R2: 0/2.167** dòng đã điền nhãn, tiêu chí hoặc ghi chú trong phiếu kèm dữ liệu. Phiếu R2, khóa, phiếu bằng chứng và override R1 khớp tập tên. `needs_review.csv` rỗng chỉ có nghĩa hàng đợi của pipeline đã được xử lý bằng override, không có nghĩa đã thẩm định. Chưa có Cohen’s κ hay nhãn sau hòa giải.
- `registered_hallucination` không chứng minh ác ý. So sánh mốc dữ liệu hay ngày phát hành model với ngày tải gói lên cũng không chứng minh một câu trả lời cụ thể đã xuất hiện trước lúc đăng ký.

### Thống kê bổ sung theo PyPI 404

Theo quy ước tính tên có PyPI JSON API trả 404 tại thời điểm thu thập là ảo giác, có **320 tên trong tập P3**; thêm **304 tên ngoài tập**. Đây là chỉ số riêng, không thay thế các nhãn trong bảng trên. HTTP 404 không chứng minh tên chưa từng tồn tại, và 2 trong 320 tên có nhãn `known_malicious` cần giữ thông tin này riêng. Xem [báo cáo đề xuất nhãn 404](bao-cao-de-xuat-nhan-404.md).

## Điểm cần lưu tâm khi duyệt nhãn

Mục này dành cho người điều phối, không đưa vào phiếu duyệt mù. Các nhóm ưu tiên có thể chồng nhau; không thay thế yêu cầu R2 duyệt đủ 2.167 tên.

| Tài liệu cần xem | Việc cần kiểm trước khi kết luận |
|---|---|
| [Quy trình P3, mục 5–6](../du-lieu/quy-trinh-gan-nhan-thu-cong.md#5-tiêu-chí-thời-gian) | Với nhãn S, tách thời điểm trả lời quan sát được, ngày tải file lên đầu tiên, mốc dữ liệu và ngày phát hành model. Không diễn giải hai mốc của model thành bằng chứng nó đã gợi ý tên trước khi gói được đăng ký. |
| [Bàn giao, mục 3.2–3.3](../du-lieu/ban-giao-gan-nhan.md#32-đăng-ký-sau-khi-model-phát-hành-không-đủ-để-gọi-là-bị-chiếm-tên) | Rà sâu 51 ca `uncertain` gốc và 201 ca chuyển sang `uncertain` trong bản phân tích. Ưu tiên tìm đúng tệp/phiên bản khi `api_404` hoặc `too_large`; nếu vẫn thiếu bằng chứng, giữ `uncertain`, không suy gói rỗng. |
| [Thiết kế dữ liệu](../du-lieu/thiet-ke-du-lieu.md) và [báo cáo 15/11](bao-cao-tien-do-15-11.md) | Không dùng 21.198 `pre_cutoff_unverified` làm mẫu âm đã xác minh. Gói có trong PyPI không mặc định là gói thật; khi đo báo nhầm trên gói mới, ghi rõ tập nào chỉ lấy mẫu từ registry và tập nào đã duyệt nội dung. |

## Cách dùng bản dữ liệu

- `data/curated/p3-consolidated-v1/labels.sqlite`: bảng `labels` ghép với `mentions.norm_name`; `label_summary` cho số tổng hợp. Dùng `label_p3` để đối chiếu P3, `label_analysis` cho phân tích thăm dò loại bằng chứng thiếu; cả hai đều chưa phải ground truth. `review_status = 'pending_r2'` xác định tập cần duyệt độc lập.
- `data/curated/p3-consolidated-v1/summary.json`: manifest với lần label nguồn, snapshot, số dòng, checksum phiếu và checksum nội dung bảng nhãn. Các file trong `data/` là nội bộ; chỉ chia sẻ số gộp. Người duyệt R2 chỉ nhận `R2_P3.csv` và mục 1–8 của quy trình, không nhận bản nhãn hợp nhất, override hoặc file khóa.

## Điều kiện chốt kết quả cho bài báo khoa học

1. Duyệt mù đủ 2.167 tên; kiểm tên duy nhất, khớp khóa và đủ ba trường R2 trước khi tính Cohen’s κ AI–người. Tính trước hòa giải, rồi phát hành bản nhãn mới với thay đổi sau thống nhất.
2. Xuất lại báo cáo theo cohort và phiên bản nhãn đó. Giữ artifact detector cũ như baseline lịch sử: phát hiện cao trên mẫu mô phỏng không chuyển sang gói mới hoặc ca đã đăng ký quan sát được. Lần đánh giá mới cần tập chỉnh ngưỡng riêng, metadata đúng thời điểm và báo riêng FPR gói mới, recall ca quan sát được.
3. Chỉ cân nhắc gọi thêm LLM nếu phân tích cục bộ chỉ ra một nhóm thiếu dữ liệu. Bản hợp nhất này không phát sinh token API.
