# Slopsquatting: phát hiện tên gói ảo giác bền vững trước tấn công đối kháng

Tài liệu nghiên cứu cho luận văn thạc sĩ chuyên ngành An toàn thông tin:

> **Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn**
>
> *Adversarially Robust Detection of Slopsquatting Attacks in LLM-Generated Code: A Multi-Threat-Model and Cross-Ecosystem Study*

Đề tài gồm hai giai đoạn:

1. **Giai đoạn 1:** thu thập tên gói do LLM bịa ra, đối chiếu với PyPI/npm, rồi huấn luyện bộ phát hiện cơ sở D0.
2. **Giai đoạn 2:** tấn công D0 bằng Faster-GCG (white-box) và LLM-guided (black-box), rồi huấn luyện đối kháng ra bộ phát hiện bền vững D′.

## Tài liệu

Các tài liệu gốc nằm trên Google Drive (file .docx, .xlsx, Google Docs, .png) và được chuyển sang markdown trong thư mục `docs/`. Mỗi file ghi rõ file gốc và ngày sửa cuối ở đầu trang.

### Đề cương

| File | Nội dung | Ngày |
| --- | --- | --- |
| [01-de-cuong-v1.md](docs/de-cuong/01-de-cuong-v1.md) | Đề cương bản 1: tấn công kiểu HotFlip, một threat model | 08/09/2026 |
| [02-de-cuong-v2.md](docs/de-cuong/02-de-cuong-v2.md) | Đề cương bản 2: 4 LLM, hai threat model (Faster-GCG và LLM-guided), AdvSlop-Bench | 10/09/2026 |

### Phương pháp

| File | Nội dung | Ngày |
| --- | --- | --- |
| [kien-truc-phuong-phap.md](docs/phuong-phap/kien-truc-phuong-phap.md) | Sơ đồ kiến trúc hai giai đoạn (vẽ lại bằng Mermaid từ `architecture.png`) | 10/09/2026 |
| [kich-ban-tan-cong-faster-gcg.md](docs/phuong-phap/kich-ban-tan-cong-faster-gcg.md) | Kịch bản tấn công white-box Faster-GCG 8 bước, định nghĩa ASR | 10/09/2026 |

### Khảo sát

| File | Nội dung | Ngày |
| --- | --- | --- |
| [bang-thong-ke-bai-bao.md](docs/khao-sat/bang-thong-ke-bai-bao.md) | Thống kê 14 bài báo: package hallucination và adversarial robustness | 08/09/2026 |
| [bang-so-sanh-chi-so.md](docs/khao-sat/bang-so-sanh-chi-so.md) | So sánh chỉ số với công trình liên quan, bảng ASR, độ trễ, chi phí token | 15/09/2026 |

**Báo cáo tổng hợp sau khảo sát** (metrics, model và dữ liệu), 5 phiên bản theo thứ tự thời gian:

| File | Thay đổi so với bản trước | Ngày |
| --- | --- | --- |
| [01-ban-dau.md](docs/khao-sat/bao-cao-tong-hop/01-ban-dau.md) | Bản đầu: metrics, model, lượng dữ liệu, nguồn dữ liệu | 05/10/2026 |
| [02-them-luong-va-gioi-han.md](docs/khao-sat/bao-cao-tong-hop/02-them-luong-va-gioi-han.md) | Thêm 5 luồng nghiên cứu A–E và bảng giới hạn theo luồng | 17/10/2026 |
| [03-v1-cot-metrics-bai-tieu-bieu.md](docs/khao-sat/bao-cao-tong-hop/03-v1-cot-metrics-bai-tieu-bieu.md) | Thêm cột metrics mà bài tiêu biểu đã dùng | 17/10/2026 |
| [04-v2-them-kiem-tra-tinh-moi.md](docs/khao-sat/bao-cao-tong-hop/04-v2-them-kiem-tra-tinh-moi.md) | Thêm bảng kiểm tra tính mới so với từng luồng | 18/10/2026 |
| [05-v3-cap-nhat-tinh-moi-luong-c.md](docs/khao-sat/bao-cao-tong-hop/05-v3-cap-nhat-tinh-moi-luong-c.md) | **Bản mới nhất.** Đánh giá lại tính mới, cập nhật luồng C (DGA) | 18/10/2026 |

### Dữ liệu

| File | Nội dung | Ngày |
| --- | --- | --- |
| [thiet-ke-du-lieu.md](docs/du-lieu/thiet-ke-du-lieu.md) | Báo cáo gửi thầy hướng dẫn: trả lời các câu hỏi về dữ liệu, bộ phát hiện hai tầng có dùng metadata, đóng góp khoa học, thay đổi so với đề cương | 07/11/2026 |

## Đạo đức nghiên cứu

Toàn bộ thực nghiệm chạy trong môi trường mô phỏng có kiểm soát. Không đăng ký bất kỳ tên gói nào lên registry công khai.
