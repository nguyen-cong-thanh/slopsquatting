# Đề cương luận văn thạc sĩ (bản 1)

> Chuyển sang markdown từ `de-cuong-slopsquatting.docx` (Google Drive, sửa lần cuối 08/09/2026).

**Chuyên ngành:** An toàn thông tin

## Tên đề tài

**Phương án chính:** “Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn”

**Phương án tên tiếng Anh:** “Adversarially Robust Detection of Slopsquatting Attacks in LLM-Generated Code”

## I. Mục tiêu nghiên cứu

Xây dựng và đánh giá một cơ chế phát hiện tấn công Slopsquatting trong mã nguồn được sinh bởi mô hình ngôn ngữ lớn, có khả năng duy trì hiệu quả phát hiện trước một đối tượng tấn công chủ động điều chỉnh tên gói để né tránh (adversarial evasion), thay vì chỉ đo lường tỷ lệ ảo giác hoặc phát hiện tĩnh như các nghiên cứu hiện có.

## II. Đối tượng và phạm vi nghiên cứu

**Đối tượng nghiên cứu:** tên gói phần mềm do mô hình ngôn ngữ lớn gợi ý trong quá trình sinh mã, tập trung vào hệ sinh thái PyPI (Python), có thể mở rộng sang npm (JavaScript).

**Phạm vi nghiên cứu:** thực hiện trong môi trường mô phỏng có kiểm soát; không đăng ký bất kỳ tên gói nào lên registry công khai trong suốt quá trình thử nghiệm, nhằm bảo đảm đạo đức nghiên cứu.

## III. Phương pháp nghiên cứu

### 3.1. Giai đoạn 1: Xây dựng dữ liệu và bộ phát hiện cơ sở

- Thu thập tên gói do mô hình ngôn ngữ lớn gợi ý, bằng cách prompt nhiều mô hình (mã nguồn đóng và mã nguồn mở) với các tác vụ lập trình điển hình liên quan đến việc gọi thư viện bên thứ ba.
- Đối chiếu kết quả với danh sách gói thật trên PyPI và npm thông qua API công khai để xác định các tên gói bị ảo giác, tức không tồn tại trên registry.
- Trích xuất đặc trưng của tên gói: chuỗi n-gram ký tự, khoảng cách Levenshtein tới các gói phổ biến, và biểu diễn embedding.
- Huấn luyện bộ phát hiện cơ sở D0, sử dụng mô hình 1D-CNN trên chuỗi ký tự, có đối chiếu với các mô hình nền tảng khác như Random Forest hoặc XGBoost.
- Đánh giá bộ phát hiện cơ sở bằng các chỉ số Precision, Recall, F1-score, AUC-ROC và tỷ lệ dương tính giả.

### 3.2. Giai đoạn 2: Đánh giá và tăng cường độ bền vững adversarial

- Thiết kế kỹ thuật tấn công nhiễu ký tự trên không gian rời rạc, theo hướng tiếp cận kiểu HotFlip: sử dụng gradient trên lớp embedding để xác định hướng thay đổi có lợi nhất cho việc né tránh, sau đó ánh xạ về ký tự gần nhất.
- Ràng buộc tấn công: tên gói sau khi bị nhiễu vẫn phải hợp lệ theo quy tắc đặt tên của registry, đồng thời vẫn đủ hợp lý để mô hình ngôn ngữ lớn có khả năng gợi ý trong thực tế.
- Đo lường tỷ lệ tấn công thành công và ngân sách nhiễu tối thiểu, tức số ký tự cần thay đổi để né được bộ phát hiện cơ sở D0.
- Áp dụng phương pháp adversarial training: huấn luyện lại bộ phát hiện bằng chính tập mẫu tấn công thu được, tạo ra bộ phát hiện cải tiến D′ có độ bền vững cao hơn.
- Đánh giá lại D′ bằng chính kỹ thuật tấn công ở bước trên, đồng thời đo mức đánh đổi về tỷ lệ dương tính giả trên tập gói thật.
- Mở rộng nếu đủ thời gian: đánh giá khả năng lan truyền của mẫu tấn công, tức transferability, giữa các kiến trúc bộ phát hiện khác nhau.

### 3.3. Công cụ và môi trường thực hiện

- **Ngôn ngữ và framework:** Python, cùng PyTorch hoặc TensorFlow để xây dựng và huấn luyện các bộ phát hiện.
- **Nguồn dữ liệu đối chiếu:** API công khai của PyPI và npm để xác thực sự tồn tại của tên gói.
- **Môi trường triển khai thử nghiệm:** mô phỏng dưới dạng middleware hoặc plugin tại tầng API Gateway, ví dụ Kong Gateway, nhằm đánh giá độ trễ và khả năng triển khai thực tế trong quy trình phát triển phần mềm.

## IV. Kết quả dự kiến

- Bộ dữ liệu tên gói ảo giác được tổng hợp từ nhiều mô hình ngôn ngữ lớn, có đối chiếu với registry thật.
- Bộ phát hiện cơ sở D0 và bộ phát hiện bền vững D′, cùng bộ chỉ số đánh giá so sánh giữa hai bộ phát hiện.
- Số liệu định lượng về mức độ dễ bị tấn công của các bộ phát hiện phổ biến hiện nay trước tấn công Slopsquatting có chủ đích.
- Đề xuất kiến trúc triển khai thực tế tại tầng API Gateway hoặc quy trình tích hợp liên tục, phù hợp với bối cảnh phát triển phần mềm doanh nghiệp.
