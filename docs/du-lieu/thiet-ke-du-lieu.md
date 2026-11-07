# Báo cáo: Dữ liệu và đóng góp khoa học của đề tài

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

**Giảng viên hướng dẫn:** TS. Mai Đức Thọ · **Ngày:** 07/11/2026

Báo cáo gồm hai phần: trả lời các câu hỏi về dữ liệu ở buổi trao đổi trước, và đóng góp khoa học của đề tài. Cuối báo cáo là các bước tiếp theo.

## 1. Trả lời các câu hỏi về dữ liệu

### Bộ dữ liệu gồm những gì

Mỗi mẫu là một tên gói Python, gắn nhãn **tên bịa** hoặc **tên thật**, kèm thông tin: LLM nào gợi ý, từ câu hỏi nào, xuất hiện bao nhiêu lần.

Tên bịa có hai loại:

- **Tên không có trên PyPI**, ví dụ `vectorcache`.
- **Tên nhầm đã có người đăng ký**, ví dụ `pil` thay vì `pillow`, `skimage` thay vì `scikit-image`. Tra PyPI không phát hiện được loại này. Raj và Sahu (2026) ghi nhận khoảng một nửa số tên bịa trong thực nghiệm của họ thuộc loại này. Đây là lý do cần một mô hình học máy thay vì chỉ tra PyPI.

Tên thật lấy từ chính câu trả lời của LLM. Ví dụ LLM viết mã dùng `requests`, `numpy` và `vectorcache` thì `requests`, `numpy` là tên thật. Nếu lấy tên ngẫu nhiên trên PyPI, mô hình sẽ học phân biệt "tên kiểu LLM" với "tên kiểu người đặt", thay vì phân biệt tên bịa với tên thật.

### Mất cân bằng dữ liệu

Tên bịa chỉ chiếm khoảng 5–20% số tên LLM gợi ý, tùy LLM (Spracklen và cộng sự, 2025).

- **Khi huấn luyện:** phạt mô hình nặng hơn mỗi khi bỏ sót một tên bịa. Không tạo mẫu giả, vì mẫu giả không phải tên gói thật và có thể lẫn với dạng tấn công cần nghiên cứu.
- **Khi đánh giá:** giữ nguyên tỷ lệ tự nhiên. Đo xem mô hình bắt được bao nhiêu tên bịa khi chỉ được phép báo nhầm 1 trên 100 tên thật. Tỷ lệ báo nhầm đo trên 10.000 tên gói thật lấy ngẫu nhiên từ PyPI.

### Kiểu dữ liệu và mô hình

Đầu vào là một chuỗi ký tự ngắn (tên gói); đầu ra là một trong hai nhãn: tên bịa hoặc tên thật. Đây là bài toán **phân loại nhị phân trên văn bản ngắn**. Mô hình chỉ dùng tên gói, không dùng thông tin khác của gói trên PyPI.

Cùng một tên gói có thể biểu diễn theo ba dạng. Mỗi dạng hợp với một nhóm mô hình:

| Biểu diễn dữ liệu | Ví dụ với `vectorcache` | Mô hình tương ứng | Ưu điểm | Hạn chế |
| --- | --- | --- | --- | --- |
| **Dạng bảng:** mỗi tên thành một dòng các đặc trưng số, như số lần xuất hiện của các cụm 1–5 ký tự liên tiếp, độ giống với các gói phổ biến | `vec`: 1, `cache`: 1, … | Machine learning: Logistic Regression, Random Forest, XGBoost | Nhanh, dễ giải thích, cần ít dữ liệu | Không có gradient, nên chỉ tấn công được kiểu hộp đen |
| **Dạng chuỗi ký tự:** mỗi ký tự là một phần tử của chuỗi | `v e c t o r c a c h e` | Deep learning cho chuỗi: 1D-CNN, LSTM/GRU | Tự học mẫu ký tự, không cần thiết kế đặc trưng. Bài toán tương tự là phát hiện tên miền độc hại dùng chính các mô hình này | Khó nắm nghĩa của từ ghép |
| **Dạng chuỗi cụm từ:** tách tên thành các mảnh có nghĩa | `vector` + `cache` | Deep learning cho văn bản: fastText, hoặc tinh chỉnh mô hình đã huấn luyện sẵn trên mã nguồn như CodeBERT | Nắm được việc ghép từ có hợp lý hay không | Nặng hơn; cần kiểm chứng có tốt hơn hai dạng kia không |

Dạng chuỗi cụm từ được đưa vào vì phần lớn tên bịa không phải lỗi gõ: chỉ 13,4% lệch tên thật 1–2 ký tự, còn lại là các từ ghép nghe hợp lý (Spracklen và cộng sự, 2025).

Đề xuất:

- **Mô hình chính:** 1D-CNN trên chuỗi ký tự. Mô hình nhẹ, đã hiệu quả trên bài toán tên miền độc hại, và có gradient để phục vụ phần tấn công.
- **Mô hình đối chứng:** XGBoost trên dạng bảng, làm mốc so sánh đơn giản.
- **Mô hình kiểm tra giả thuyết:** fastText hoặc CodeBERT trên dạng cụm từ, để xem việc hiểu nghĩa từ ghép có giúp phát hiện tốt hơn không.

Mô hình cuối cùng được chọn sau khi chạy thử, so sánh trên cùng một bộ dữ liệu.

### Lấy dữ liệu thế nào

**Hiểu dữ liệu thật trước.** Khảo sát các bộ tên bịa đã công bố: 0pstech (1.066 tên trên PyPI), DepScope và Trend Micro. Mục đích là biết tên bịa thật trông ra sao, rồi dùng làm chuẩn để kiểm tra dữ liệu tự tạo.

**Tạo dữ liệu.** Gửi câu hỏi lập trình cho hai LLM, một LLM thương mại và một LLM chạy trên máy. Lấy tên gói trong câu trả lời, rồi tra PyPI để gắn nhãn. Đây là ảo giác thật do LLM sinh ra, không phải tên do nhóm tự đặt.

- **Câu hỏi:** dùng 18.033 câu hỏi Python công khai từ nghiên cứu của Spracklen và cộng sự. Bộ này có hạn chế: chỉ 19% câu lấy từ Stack Overflow có nhắc tới thư viện ngoài, và các câu đã công khai từ năm 2024 nên LLM mới có thể đã học. Vì vậy nhóm nghiên cứu thêm cách tạo câu hỏi mới.
- **Chọn LLM:** chọn sau khi chạy thử.

**Quy mô.** Mục tiêu khoảng 4.000 tên bịa không trùng nhau, mỗi LLM ít nhất 500 tên riêng. Con số này đủ để phần kiểm thử có khoảng 500 tên bịa, và đủ để huấn luyện trên tên của một LLM rồi kiểm thử trên tên của LLM kia.

Số tên được đếm theo tên không trùng nhau: hai lần hỏi ra {a, b, c} và {a, b, e} là 4 tên, không phải 6. Càng hỏi nhiều thì càng ít tên mới, nên quy mô sẽ chốt sau khi chạy thử.

### Chuẩn hóa

Đưa mọi tên về dạng mà PyPI coi là một: `Vector_Cache`, `vector.cache` và `vector-cache` đều thành `vector-cache`. Sau đó bỏ các tên trùng.

Làm giống hệt nhau cho cả tên bịa và tên thật. LLM hay viết tên với dấu `_`, còn PyPI thường dùng dấu `-`. Nếu chỉ chuẩn hóa một bên, mô hình chỉ cần học mẹo "có dấu `_` là tên bịa".

## 2. Đóng góp khoa học

### Những gì đã có người làm

- Đo tỷ lệ LLM bịa tên gói: Spracklen và cộng sự (2025), Churilov (2026).
- Bộ phát hiện tên bịa: Raj và Sahu (2026). Bộ này dựa phần lớn vào thông tin ngoài tên, như số người duy trì gói.
- Huấn luyện thêm bằng mẫu tấn công để bộ phân loại chuỗi ký tự ngắn bền hơn: đã phổ biến trong bài toán phát hiện tên miền độc hại.

### Đóng góp chính: tấn công theo cách sát thực tế

Các nghiên cứu về tấn công né tránh thường giả định kẻ tấn công được tự do sửa tên. Với slopsquatting, giả định này không đúng: kẻ tấn công chỉ thắng nếu đăng ký đúng cái tên mà LLM sẽ gợi ý cho nạn nhân.

Đề tài nghiên cứu kẻ tấn công làm như sau:

1. Hỏi LLM nhiều lần để thu các biến thể tên mà LLM tự sinh ra.
2. Chọn biến thể né được bộ phát hiện.
3. Kiểm tra biến thể đó vẫn đăng ký được trên PyPI. PyPI chặn các tên quá giống gói đã có.

Đề tài trả lời ba câu hỏi:

1. Bộ phát hiện chỉ dựa vào tên dễ bị né đến mức nào trong điều kiện thực tế này?
2. So với kẻ tấn công được tự do sửa tên, mức nguy hiểm thực tế chênh bao nhiêu?
3. Huấn luyện thêm bằng các biến thể này có làm bộ phát hiện bền hơn không, và phải đánh đổi bao nhiêu báo nhầm?

### Đóng góp về dữ liệu

**Chính: bộ biến thể tên bịa theo từng câu hỏi.** Với mỗi câu hỏi làm LLM bịa tên, hỏi lại khoảng 10 lần và ghi lại mọi tên LLM sinh ra cùng số lần xuất hiện. Dự kiến làm với khoảng 500 tên bịa.

Spracklen và cộng sự có đo mức lặp lại: 43% tên bịa lặp lại cả 10 lần, 39% không lặp lại lần nào. Nhưng nhóm này không công bố dữ liệu đó. Hiện chưa có bộ công khai nào cho biết LLM bịa những biến thể nào và với tần suất bao nhiêu. Đây cũng là dữ liệu bắt buộc phải có cho đóng góp chính.

**Phụ: bộ tên nhầm do LLM gây ra, kèm gói đúng.** Ví dụ `pil` kèm gói đúng là Pillow, có ghi tên nhầm hiện có người đăng ký trên PyPI hay không. Các bộ dữ liệu về gói giả mạo tên hiện có được thu từ các vụ tấn công trên PyPI, không gắn với việc LLM gợi ý.

**Công bố có trách nhiệm.** Công khai danh sách tên bịa thì kẻ xấu có thể đăng ký ngay. Vì vậy dự kiến làm theo cách của Churilov (2026): gửi danh sách cho đội an ninh của PyPI để chặn trước, sau đó mới công bố.

### Giới hạn

Nhận định "chưa ai làm" chỉ đúng trong phạm vi khoảng 24 bài nhóm đã khảo sát.

## 3. Bước tiếp theo

Chạy thử nhỏ trên LLM chạy trên máy (gần như không tốn tiền) để đo:

- số tên bịa không trùng tăng thế nào theo số câu hỏi, để chốt quy mô;
- hỏi lại cùng một câu 10 lần thì ra bao nhiêu biến thể;
- mô hình chỉ dựa vào tên có phân biệt được tên bịa và tên thật không.

**Rủi ro:** nếu LLM gần như luôn lặp lại đúng một tên, kẻ tấn công hầu như không có biến thể để chọn. Kết quả đó vẫn có giá trị, vì nó cho thấy tấn công né tránh trên thực tế khó hơn nhiều so với giả định của các nghiên cứu trước. Nhưng khi đó trọng tâm luận văn cần điều chỉnh, nên phải biết sớm.

## Tài liệu tham khảo

- Churilov, A. (2026). *The Range Shrinks, the Threat Remains: Re-evaluating LLM Package Hallucinations on the 2026 Frontier-Model Cohort*. Bản tiền ấn phẩm. [arXiv:2605.17062](https://arxiv.org/abs/2605.17062)
- Raj, A., Sahu, S. (2026). *Names Can Hurt: Spotting Slopsquatting Risks Caused by Package Name Hallucinations in Local Coding LLMs*. Bản tiền ấn phẩm. [arXiv:2608.23897](https://arxiv.org/abs/2608.23897)
- Spracklen, J., Wijewickrama, R., Sakib, A. H. M. N., Maiti, A., Viswanath, B., Jadliwala, M. (2025). *We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs*. USENIX Security. [arXiv:2406.10279](https://arxiv.org/abs/2406.10279)
- Bộ dữ liệu: [0pstech](https://github.com/0pstech/slopsquatting-dataset), [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset), [Trend Micro](https://github.com/trendmicro/slopsquatting), [bộ câu hỏi của Spracklen và cộng sự](https://github.com/Spracks/PackageHallucination)
