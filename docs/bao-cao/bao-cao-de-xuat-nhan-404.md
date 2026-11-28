# Báo cáo đề xuất chuyển nhãn cho các tên có API PyPI 404

## Phạm vi và trạng thái

Nguồn là `metadata_raw` trong `data/slop.sqlite`, chọn `source = pypi_json` và HTTP 404 đã lưu; đối chiếu nhãn với `data/curated/p3-consolidated-v1/labels.sqlite`. Đây là trạng thái tại thời điểm thu thập, không phải kết quả kiểm tra lại hiện tại. Có 624 tên: 320 tên trong tập P3 hợp nhất và 304 tên ngoài tập, không có nhãn trong DB nguồn.

## Tiêu chí tính 404 là ảo giác

Theo quy ước P3-404, mọi tên có PyPI JSON API trả 404 trong dữ liệu đã lưu được tính là **ảo giác theo trạng thái 404**. Đây là chỉ số riêng; pipeline và nhãn SQLite chưa thay đổi.

| Nhãn P3 hiện tại | Số tên | Đề xuất theo quy ước 404 |
|---|---:|---|
| `placeholder` | 160 | Ảo giác |
| `registered_hallucination` | 37 | Ảo giác |
| `uncertain` | 28 | Ảo giác |
| `pre_cutoff_unverified` | 93 | Ảo giác |
| `known_malicious` | 2 | Ảo giác theo 404; giữ thông tin độc hại riêng |
| Ngoài tập P3, chưa có nhãn nguồn | 304 | Ảo giác theo 404; chưa nhập vào tập P3 |
| **Tổng** | **624** | **Ảo giác theo 404** |

Trong tập P3, quy ước này tính **320 tên** là ảo giác. Trong đó 283 tên có nhãn P3 khác `registered_hallucination`. Đây là đề xuất thống kê, chưa thay đổi nhãn trong SQLite.

## Giới hạn

- HTTP 404 chỉ phản ánh phản hồi của API tại thời điểm thu thập; không chứng minh package chưa từng tồn tại hoặc model đã bịa tên trước khi package được đăng ký.
- Hai tên `known_malicious` cần giữ thông tin an toàn riêng để không mất dữ liệu khi thống kê theo quy ước 404.
- Đã đối chiếu toàn bộ 624 tên có 404 được lưu, không phải toàn bộ package trong DB hay trên PyPI. Không sử dụng kết quả tìm kiếm GitHub để tính báo cáo này.
