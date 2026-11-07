# Báo cáo: Dữ liệu và đóng góp khoa học của đề tài

**Đề tài:** Tăng cường độ bền vững adversarial cho hệ thống phát hiện tấn công Slopsquatting (Package Hallucination) trong mã nguồn sinh bởi mô hình ngôn ngữ lớn

**Giảng viên hướng dẫn:** TS. Mai Đức Thọ · **Ngày:** 07/11/2026

Báo cáo gồm bốn phần: trả lời các câu hỏi về dữ liệu ở buổi trao đổi trước, đóng góp khoa học, những thay đổi so với đề cương, và các bước tiếp theo.

## 1. Trả lời các câu hỏi về dữ liệu

### Bộ phát hiện làm gì

Bộ phát hiện gồm hai tầng:

- **Tầng 1, tra PyPI:** tên gói không có trên PyPI thì cảnh báo ngay. Tầng này không cần học máy.
- **Tầng 2, mô hình học máy:** với tên có trên PyPI, mô hình dùng tên gói và thông tin của gói (metadata) để phân biệt gói thật với gói đáng ngờ.

Tầng 2 là phần cần học máy. Kẻ tấn công slopsquatting đăng ký trước các tên mà LLM hay bịa, nên khi người dùng cài thì tên đó đã có trên PyPI và tầng 1 không bắt được.

### Bộ dữ liệu gồm những gì

Mỗi mẫu gồm tên gói, metadata (nếu gói có trên PyPI), nhóm tên, và nguồn gốc: LLM nào gợi ý, từ câu hỏi nào, xuất hiện bao nhiêu lần.

| Nhóm tên | Ví dụ | Dùng làm gì |
| --- | --- | --- |
| Tên thật, đúng gói cần dùng | `requests`, `numpy` | Lớp bình thường |
| Tên bịa không có trên PyPI | `vectorcache` | Tầng 1 bắt được. Dùng để thu biến thể cho phần tấn công |
| Tên nhầm có bản giữ chỗ | `sklearn` (mô tả trên PyPI: "deprecated sklearn package, use scikit-learn instead"), `skimage` ("Dummy package that points to scikit-image") | Nhóm riêng. Đây là bản phòng vệ trỏ người dùng sang gói đúng, không tính là bẫy |
| Tên bịa đã có người khác đăng ký | Các tên như `fastyaml`, `embeddinghub` mà Raj và Sahu (2026) ghi nhận đã có người đăng ký | Lớp đáng ngờ |
| Gói độc hại đã bị phát hiện trên PyPI | Lấy từ bộ dữ liệu của OpenSSF và DataDog | Bổ sung lớp đáng ngờ |

Tên thật lấy từ chính câu trả lời của LLM. Ví dụ LLM viết mã dùng `requests`, `numpy` và `vectorcache`, thì `requests` và `numpy` là tên thật. Nếu lấy tên ngẫu nhiên trên PyPI, mô hình sẽ học phân biệt "tên kiểu LLM" với "tên kiểu người đặt" thay vì phân biệt gói thật với gói đáng ngờ.

### Mất cân bằng dữ liệu

Theo Spracklen và cộng sự (2025), tính trên số lượt gợi ý, trung bình 5,2% tên do LLM thương mại gợi ý là tên bịa, và 21,7% với LLM mã nguồn mở. Báo cáo này đếm theo tên không trùng nhau, nên tỷ lệ thực tế sẽ khác và được đo khi chạy thử. Ở tầng 2, gói đáng ngờ còn hiếm hơn nữa.

- **Khi huấn luyện:** đặt trọng số lớn hơn cho lớp đáng ngờ, tức là phạt mô hình nặng hơn mỗi khi bỏ sót một gói đáng ngờ. Không tạo mẫu giả bằng cách nội suy, vì mẫu tạo ra không ứng với gói nào có thật. Không tạo thêm mẫu bằng cách sửa ký tự ngẫu nhiên, vì đó chính là dạng tấn công cần nghiên cứu.
- **Khi đánh giá:** giữ nguyên tỷ lệ tự nhiên. Đo xem mô hình bắt được bao nhiêu gói đáng ngờ khi chỉ được phép báo nhầm 1 trên 100 gói thật. Tỷ lệ báo nhầm đo trên ba nhóm:
  - **Chính:** tên thật do LLM gợi ý, giữ riêng, không dùng khi huấn luyện.
  - **Phụ:** 10.000 gói lấy ngẫu nhiên trên PyPI.
  - **Phụ:** các gói thật mới đăng, thu qua RSS của PyPI. Nhóm này để kiểm tra mô hình có báo nhầm mọi gói mới hay không.

  10.000 gói chỉ đủ đo chính xác ở mức báo nhầm 1 trên 100, chưa đủ cho mức 1 trên 1.000.

### Kiểu dữ liệu và mô hình

Dữ liệu ở tầng 2 là **dữ liệu hỗn hợp**:

- **Chuỗi ký tự:** tên gói.
- **Bảng số:** metadata của gói, gồm tuổi gói, số bản phát hành, số lượt tải, số sao GitHub, và việc link mã nguồn có được PyPI xác minh hay không.

Mô hình chưa chốt. Sau khi thu xong dữ liệu, nhóm thử nghiệm các nhóm mô hình dưới đây trên cùng một bộ dữ liệu và cùng cách đánh giá, rồi mới chọn.

| Cách đưa dữ liệu vào mô hình | Nhóm mô hình ứng viên | Lý do đưa vào thử |
| --- | --- | --- |
| Gộp thành một bảng số: đặc trưng từ tên (các cụm ký tự, độ giống với gói phổ biến) cùng metadata | Machine learning: Logistic Regression, Random Forest, XGBoost | Nhanh, dễ giải thích, cần ít dữ liệu; dùng làm mốc so sánh |
| Tên dạng chuỗi ký tự, metadata dạng bảng, mỗi phần một nhánh rồi ghép lại | Deep learning: nhánh đọc tên là 1D-CNN hoặc LSTM, nhánh đọc metadata là mạng nhiều lớp | Tự học mẫu ký tự trong tên. Các mô hình đọc chuỗi ký tự đã hiệu quả trên bài toán tương tự là phát hiện tên miền độc hại (Yu và cộng sự, 2018) |
| Tên tách thành cụm từ có nghĩa, metadata dạng bảng | Deep learning cho văn bản: fastText, hoặc tinh chỉnh mô hình đã huấn luyện sẵn trên mã nguồn như CodeBERT | Phần lớn tên bịa là từ ghép nghe hợp lý: chỉ 13,4% lệch tên thật 1–2 ký tự (Spracklen và cộng sự, 2025). Mô hình hiểu nghĩa từ ghép có thể phát hiện tốt hơn |

Mỗi nhóm được thử cả hai cách: dùng tên và metadata, và chỉ dùng tên. So sánh hai cách cho biết metadata đóng góp bao nhiêu.

Tiêu chí chọn: tỷ lệ phát hiện khi chỉ báo nhầm 1 trên 100 gói thật, độ ổn định khi kiểm thử chéo giữa hai LLM, và thời gian xử lý. Kẻ tấn công thực tế trong phần 2 không cần gradient của mô hình, nên mô hình nào cũng đánh giá được. Riêng mốc so sánh "kẻ tấn công được tự do sửa ký tự" cần gradient, nên phải có ít nhất một mạng nơ-ron trong các mô hình thử nghiệm.

**Nguồn metadata:**

- API của PyPI: tuổi gói, số bản phát hành, link mã nguồn và trạng thái xác minh.
- Bộ dữ liệu công khai của PyPI trên BigQuery hoặc pypistats: số lượt tải.
- API của GitHub: số sao, chỉ lấy được với gói có link repo.

### Lấy dữ liệu thế nào

**Hiểu dữ liệu thật trước.** Khảo sát các bộ tên bịa đã công bố:

- 0pstech: 1.071 tên trên PyPI tại ngày 07/11/2026, giấy phép CC BY 4.0, cập nhật 6 giờ một lần.
- DepScope.
- Trend Micro.

Mục đích là biết tên bịa thật trông ra sao, rồi dùng làm chuẩn để kiểm tra dữ liệu tự tạo.

**Tạo dữ liệu.**

- **LLM:** hai LLM, một LLM thương mại và một LLM chạy trên máy, chọn sau khi chạy thử.
- **Câu hỏi:** gửi cho LLM bộ 18.033 câu hỏi Python không trùng nhau của Spracklen và cộng sự (19.084 câu trước khi bỏ trùng). Bộ này có hai hạn chế:
  - Nhóm tự đếm thấy chỉ 19% câu lấy từ Stack Overflow có chữ `import` hoặc `pip install` trong nội dung, tức nhiều câu không cần thư viện ngoài.
  - Các câu đã công khai từ năm 2024, nên LLM mới có thể đã học.

  Vì vậy nhóm nghiên cứu thêm cách tạo câu hỏi mới.
- **Gắn nhãn:** lấy tên gói trong câu trả lời, tra PyPI, và thu metadata cho các tên có tồn tại. Đây là ảo giác thật do LLM sinh ra, không phải tên do nhóm tự đặt.
- **Biến thể:** với khoảng 500 tên bịa, hỏi lại câu hỏi gốc khoảng 10 lần và ghi lại mọi tên LLM sinh ra cùng số lần xuất hiện.

**Quy mô.**

- **Mục tiêu:** khoảng 4.000 tên bịa không trùng nhau, mỗi LLM ít nhất 500 tên riêng. Số tên được đếm theo tên không trùng: hai lần hỏi ra {a, b, c} và {a, b, e} là 4 tên, không phải 6.
- **Rủi ro:** LLM thương mại có thể không đạt 500 tên riêng. Churilov (2026) ghi nhận mỗi LLM thế hệ mới chỉ cho vài trăm tên không trùng trên khoảng 40.000 câu hỏi, tính cả Python và JavaScript. Lần chạy thử sẽ đo con số này.

**Chia tập.**

- Chia theo câu hỏi gốc và theo nhóm tên gần giống. Mọi biến thể của cùng một tên nằm chung một phần, để tránh rò rỉ dữ liệu giữa huấn luyện và kiểm thử.
- Có thêm phép kiểm thử chéo: huấn luyện trên tên của LLM này, kiểm thử trên tên của LLM kia. Kết quả phép này dự kiến thấp, vì 81% tên bịa chỉ do một LLM sinh ra (Spracklen và cộng sự, 2025).

### Chuẩn hóa

Đưa mọi tên về dạng mà PyPI coi là một: `Vector_Cache`, `vector.cache` và `vector-cache` đều thành `vector-cache`. Sau đó bỏ các tên trùng.

Làm giống hệt nhau cho mọi nhóm tên. LLM hay viết tên với dấu `_`, còn PyPI thường dùng dấu `-`. Nếu chỉ chuẩn hóa một bên, mô hình chỉ cần học mẹo "có dấu `_` là tên bịa".

## 2. Đóng góp khoa học

### Những gì đã có người làm

- Đo tỷ lệ LLM bịa tên gói: Spracklen và cộng sự (2025), Churilov (2026).
- Bộ phát hiện tên bịa: Raj và Sahu (2026). Bộ này dùng 10 đặc trưng, gồm 8 đặc trưng từ tên và 2 từ metadata (số người duy trì gói, có link GitHub hay không). Riêng số người duy trì chiếm 57,6% mức quan trọng.
- Tấn công và huấn luyện thêm bằng mẫu tấn công cho bộ phân loại chuỗi ký tự ngắn: đã làm nhiều trong bài toán phát hiện tên miền độc hại (CharBot của Peck và cộng sự, 2019; MaskDGA của Sidi và cộng sự, 2019).

Các bộ phát hiện có dùng metadata hiện chưa được thử trước kẻ tấn công làm giả metadata.

### Đóng góp chính: tấn công theo cách sát thực tế

Các nghiên cứu về tấn công né tránh thường giả định kẻ tấn công được tự do sửa tên. Với slopsquatting, giả định này không đúng, vì kẻ tấn công chỉ thắng nếu đăng ký đúng cái tên mà LLM sẽ gợi ý cho nạn nhân.

Trong đề tài, kẻ tấn công **né thành công** khi thỏa cả ba điều kiện:

1. **Tên là biến thể mà LLM thật sự gợi ý,** lấy từ các lần hỏi lại.
2. **Tên đăng ký được trên PyPI.** PyPI bỏ các dấu `.`, `_`, `-`, đổi `l` và `i` thành `1`, đổi `o` thành `0`, chuyển về chữ thường, rồi so với các tên đã có; nếu trùng thì từ chối đăng ký. Đề tài kiểm tra bằng đúng quy tắc này, lấy từ mã nguồn của PyPI.
3. **Bộ phát hiện không cảnh báo,** kể cả sau khi kẻ tấn công làm giả metadata trong phạm vi ngân sách.

**Chỉ số chính:** tỷ lệ né thành công, bằng tổng tần suất (trong các lần hỏi lại) của những biến thể thỏa cả ba điều kiện. Kết quả được báo thành đường: tỷ lệ né thành công theo ngân sách của kẻ tấn công.

**Làm giả metadata chỉ mô phỏng:** không đăng ký gói thật, không mua sao giả, chỉ thay đổi giá trị trong dữ liệu.

- Mỗi đặc trưng có chi phí làm giả, lấy từ nguồn đã công bố hoặc từ thời gian phải chờ. Ví dụ: lượt tải tự tạo, sao GitHub mua, tuổi gói phải chờ.
- Đặc trưng không làm giả được, như link mã nguồn được PyPI xác minh, được ghi rõ.

**Mốc so sánh:** kẻ tấn công được tự do sửa ký tự, dùng gradient của mô hình (kiểu kỹ thuật Faster-GCG). Mốc này cho biết giả định "tự do sửa tên" của các nghiên cứu trước làm sai lệch mức nguy hiểm thực tế đến đâu.

**Ba câu hỏi nghiên cứu:**

1. Bộ phát hiện dễ bị né đến mức nào trong điều kiện thực tế, theo từng mức ngân sách?
2. So với kẻ tấn công được tự do sửa tên, mức nguy hiểm thực tế chênh bao nhiêu?
3. Huấn luyện thêm bằng các biến thể và metadata giả có làm bộ phát hiện bền hơn không, và phải đánh đổi bao nhiêu báo nhầm?

### Đóng góp về dữ liệu

- **Chính: bộ biến thể tên bịa theo từng câu hỏi, kèm tần suất.** Spracklen và cộng sự có đo mức lặp lại (43% tên bịa lặp lại cả 10 lần, 39% không lặp lại lần nào) nhưng không công bố dữ liệu. Hiện chưa có bộ công khai nào cho biết LLM bịa những biến thể nào và với tần suất bao nhiêu.
- **Phụ: bộ tên nhầm do LLM gây ra.** Mỗi tên kèm gói đúng, tần suất LLM gợi ý, và trạng thái trên PyPI: bản giữ chỗ, bị người khác đăng ký, hay chưa có ai đăng ký. Việc ánh xạ tên module sang tên gói thì đã có sẵn trong các công cụ. Điểm mới là danh sách gắn với việc LLM gợi ý và có tần suất.
- **Công bố có trách nhiệm:** công khai danh sách tên bịa thì kẻ xấu có thể đăng ký ngay. Vì vậy làm theo cách của Churilov (2026): gửi danh sách cho đội an ninh của PyPI trước, giữ danh sách đầy đủ cho tới khi hết thời hạn công bố.

### Giới hạn

- Nhận định "chưa ai làm" chỉ đúng trong phạm vi khoảng 24 bài nhóm đã khảo sát.
- Một phần mẫu đáng ngờ ở tầng 2 phải mô phỏng. Tỷ lệ mô phỏng phụ thuộc vào số tên bịa đã có người đăng ký sẵn.

## 3. Thay đổi so với đề cương v2

| Đề cương v2 | Báo cáo này | Lý do |
| --- | --- | --- |
| PyPI và npm, có đánh giá từ PyPI sang npm | Chỉ PyPI | Giảm khối lượng; npm để mở rộng |
| 4 LLM | 2 LLM: một thương mại, một chạy trên máy, chọn sau khi chạy thử | Phần lớn tên bịa đến từ LLM mã nguồn mở; giảm chi phí |
| Bộ phát hiện chỉ dùng tên | Hai tầng: tra PyPI, rồi mô hình dùng tên và metadata. Giữ một bản chỉ dùng tên để so sánh | Tên chưa có trên PyPI thì tra là biết; phần khó là gói đã bị đăng ký |
| Tấn công chính: Faster-GCG tự do sửa ký tự | Tấn công chính: chọn biến thể do LLM sinh và làm giả metadata (mô phỏng). Faster-GCG thành mốc so sánh | Kẻ tấn công chỉ thắng nếu đăng ký đúng tên LLM gợi ý |
| Tên bịa là tên không có trên registry | Thêm nhóm tên nhầm, tách riêng bản giữ chỗ | Một số tên nhầm là bản phòng vệ, không phải bẫy |
| Chỉ số: Precision, Recall, F1, AUC-ROC, FPR | Tỷ lệ phát hiện khi chỉ báo nhầm 1 trên 100; tỷ lệ né thành công theo ngân sách | Phù hợp tỷ lệ thực tế và với mô hình tấn công mới |

## 4. Bước tiếp theo

Chạy thử trên LLM chạy trên máy (gần như không tốn tiền), cộng một lượt nhỏ trên LLM thương mại, để đo:

- số tên bịa không trùng tăng thế nào theo số câu hỏi, để chốt quy mô;
- tỷ lệ tên bịa đã có người đăng ký sẵn, để biết phải mô phỏng bao nhiêu mẫu đáng ngờ;
- số biến thể khi hỏi lại cùng một câu 10 lần;
- mô hình chỉ dùng tên có phân biệt được tên bịa và tên thật không.

**Rủi ro cần biết sớm:**

- **Nếu LLM gần như luôn lặp lại đúng một tên,** kẻ tấn công hầu như không có biến thể để chọn. Kết quả đó vẫn có giá trị, vì nó cho thấy tấn công né tránh trên thực tế khó hơn giả định của các nghiên cứu trước; nhưng trọng tâm luận văn cần điều chỉnh.
- **Nếu rất ít tên bịa đã có người đăng ký sẵn,** phần lớn mẫu đáng ngờ phải mô phỏng. Khi đó cần dựa nhiều hơn vào các gói độc hại thật đã bị phát hiện.

## Tài liệu tham khảo

- Churilov, A. (2026). *The Range Shrinks, the Threat Remains: Re-evaluating LLM Package Hallucinations on the 2026 Frontier-Model Cohort*. Bản tiền ấn phẩm. [arXiv:2605.17062](https://arxiv.org/abs/2605.17062)
- Peck, J., Nie, C., Sivaguru, R., Grumer, C., Olumofin, F., Yu, B., Nascimento, A., De Cock, M. (2019). *CharBot: A Simple and Effective Method for Evading DGA Classifiers*. IEEE Access. [arXiv:1905.01078](https://arxiv.org/abs/1905.01078)
- Raj, A., Sahu, S. (2026). *Names Can Hurt: Spotting Slopsquatting Risks Caused by Package Name Hallucinations in Local Coding LLMs*. Bản tiền ấn phẩm. [arXiv:2608.23897](https://arxiv.org/abs/2608.23897)
- Sidi, L., Nadler, A., Shabtai, A. (2019). *MaskDGA: A Black-box Evasion Technique Against DGA Classifiers and Adversarial Defenses*. [arXiv:1902.08909](https://arxiv.org/abs/1902.08909)
- Spracklen, J., Wijewickrama, R., Sakib, A. H. M. N., Maiti, A., Viswanath, B., Jadliwala, M. (2025). *We Have a Package for You! A Comprehensive Analysis of Package Hallucinations by Code Generating LLMs*. USENIX Security. [arXiv:2406.10279](https://arxiv.org/abs/2406.10279)
- Yu, B., Pan, J., Hu, J., Nascimento, A., De Cock, M. (2018). *Character Level Based Detection of DGA Domain Names*. IJCNN. [DOI: 10.1109/IJCNN.2018.8489147](https://doi.org/10.1109/IJCNN.2018.8489147)
- Bộ dữ liệu: [0pstech](https://github.com/0pstech/slopsquatting-dataset), [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset), [Trend Micro](https://github.com/trendmicro/slopsquatting), [OpenSSF malicious packages](https://github.com/ossf/malicious-packages), [DataDog malicious packages](https://github.com/DataDog/malicious-software-packages-dataset), [bộ câu hỏi của Spracklen và cộng sự](https://github.com/Spracks/PackageHallucination)
- Quy tắc tên trên PyPI: [hàm `ultranormalize_name` trong mã nguồn PyPI](https://github.com/pypi/warehouse/blob/main/warehouse/migrations/versions/d18d443f89f0_ultranormalize_name_function.py)
