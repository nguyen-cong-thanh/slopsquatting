# Báo cáo tổng hợp sau khảo sát: metrics, model và dữ liệu

> Chuyển sang markdown từ `Báo cáo tổng hợp sau khảo sát_ metrics, model và dữ liệu.docx` (Google Drive, thư mục “Khảo sát thêm metrics”, sửa lần cuối 05/10/2026). Đây là bản sớm nhất trong 5 phiên bản.

## Metrics của đề tài

| Metric | Trả lời câu hỏi nào | Dẫn chứng từ đề tài tương tự |
| --- | --- | --- |
| TPR@1%FPR (thước đo chính) | Chỉ cho báo nhầm 1 trong 100 gói thật, bắt được bao nhiêu % tên giả? | [ODFA](https://arxiv.org/html/2512.04338): đạt 95,27% và nêu 1% FPR là thông lệ. [Yu et al.](https://faculty.washington.edu/mdecock/papers/byu2018a.pdf) (tên miền DGA): 83% với Random Forest, 97 đến 98% với mạng sâu |
| Số cảnh báo sai mỗi ngày | Hệ thống có làm phiền người dùng quá nhiều không? | ODFA: FPR 0,1% cho khoảng 2,18 cảnh báo sai mỗi ngày, vừa với ngân sách 20 phút mỗi tuần của người duyệt |
| Precision theo tỷ lệ thực | Khi hệ thống báo động, bao nhiêu % là đúng? | [Arp et al.](https://arxiv.org/pdf/2010.09470) cảnh báo lỗi bỏ qua tỷ lệ thực. ODFA: Precision chỉ 18,73% ở FPR 1% vì gói độc hại rất hiếm |
| PHR (tỷ lệ gói ảo giác) | AI bịa tên gói thường xuyên đến mức nào? | [Spracklen](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf): 5,2% model thương mại, 21,7% model mã nguồn mở. [Churilov](https://arxiv.org/pdf/2605.17062): 4,62 đến 6,10% |
| Độ chính xác của nhãn | Dữ liệu gắn nhãn "ảo giác" có đúng không? | [Library Hallucinations](https://arxiv.org/pdf/2509.22202): kiểm thủ công 200 mẫu, đúng 95,8%. [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset): 97,6% ứng viên ban đầu hóa ra là gói thật |
| ASR | Kẻ gian sửa tên thì lừa được bộ phát hiện bao nhiêu %? | [TextAttack](https://textattack.readthedocs.io/en/latest/1start/what_is_an_adversarial_attack.html): ví dụ 128/157 = 81,5%. [MaskDGA](https://arxiv.org/abs/1902.08909): điểm F1 giảm từ 0,977 xuống 0,495 |
| Robust TPR | Sau khi bị sửa tên, còn bắt được bao nhiêu % tên giả? | ODFA: 95,27% giảm còn 24,30% khi bị tấn công; sau huấn luyện đối kháng còn 86,81% |
| ΔTPR | Học thêm mẫu bị sửa có làm kém đi ở tên bình thường không? | ODFA: 95,27% lên 95,64% trên MalwareBench, tức không mất |
| Kiểm định thống kê | Chênh lệch giữa hai mô hình là thật hay do ngẫu nhiên? | Churilov (cùng lĩnh vực): khoảng tin cậy Wilson, hiệu chỉnh Holm. [EvoSafeHarness](https://arxiv.org/pdf/2609.05903): McNemar cho so sánh cặp |

## Model pre-train và lượng dữ liệu để tự train

### Đã có sẵn

| Loại | Ví dụ | Dùng được làm D0 không | Dẫn chứng |
| --- | --- | --- | --- |
| Bộ phân loại đã công bố cho tên gói ảo giác | 7 bộ Random Forest của [Names Can Hurt](https://arxiv.org/pdf/2608.23897) (mỗi LLM một bộ) | Không phù hợp: 82% tín hiệu đến từ 2 đặc trưng metadata (<https://github.com/sargamsahu1011/package-hallucination-detector>), trong khi D0 cần chỉ dùng tên | Bài báo tự nêu; hai đặc trưng này đủ để viết thành một luật đơn giản cho kết quả ngang Random Forest |
| Mô hình ngôn ngữ pre-train tổng quát | fastText và CodeBERT trong [AgentGuard](https://arxiv.org/html/2604.16309) (fastText được tinh chỉnh trên 10.015.794 tên gói); RoBERTa trong [Cerebro](https://dl.acm.org/doi/10.1145/3705304) | Có thể thử làm phương án so sánh; chưa có bài nào chứng minh tốt hơn mạng ký tự nhỏ cho riêng tên gói | AgentGuard, Cerebro |
| Mạng ký tự nhỏ, train từ đầu | LSTM của [Woodbridge](https://arxiv.org/pdf/1611.00791); CNN, LSTM trong [Yu et al.](https://faculty.washington.edu/mdecock/papers/byu2018a.pdf) cho tên miền | Phù hợp nhất, đây chính là dạng D0 của đề tài | Yu et al.: 97 đến 98% TPR tại FPR 0,1%; Woodbridge: 90% tại FPR 1/10.000 |
| Công cụ theo luật hoặc danh sách | [slopguard-cli](https://pypi.org/project/slopguard-cli/), [pkgguard-cli](https://pypi.org/project/pkgguard-cli/), [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset) | Không phải model học máy; dùng làm mốc so sánh | README của từng công cụ |

### Bao nhiêu dữ liệu là đủ

| Đề tài tương tự | Dữ liệu dùng để train | Nhận xét |
| --- | --- | --- |
| Names Can Hurt (Random Forest, tên gói ảo giác) | Lớn nhất khoảng 410 dòng; mỗi LLM có 68 đến 108 dòng ảo giác | Mỗi test chỉ có 2 đến 12 mẫu dương; bài tự nêu cần khoảng 30 mẫu dương mỗi test mới kết luận được. Vài trăm mẫu đủ để chạy nhưng chưa đủ để chứng minh |
| [Dự án GitHub dùng RoBERTa](https://github.com/RuffinaMercy/slopsquatting-detector) (hành vi gói độc hại) | Khoảng 1.000 mẫu (500 độc hại, 498 bình thường) | F1 0,880 ± 0,044; đây là dự án cá nhân, chưa bình duyệt |
| [ODFA](https://arxiv.org/html/2512.04338) (XGBoost, gói PyPI) | 3.190 gói độc hại + 3.368 gói bình thường | TPR@1%FPR đạt 95,27% |
| [CharBot](https://arxiv.org/pdf/1905.01078) (tên miền) | 100.000 tên miền tổng hợp để train, 10.000 để test | Báo kết quả ở FPR 0,1% và 1% |
| [DeepDGA](https://arxiv.org/pdf/1610.01969) (tên miền) | Thêm 10.000 mẫu đối kháng để làm cứng bộ phân loại | Dùng làm mốc cho cỡ dữ liệu của huấn luyện đối kháng |

## Nguồn dữ liệu

| Cần gì | Lấy ở đâu | Quy mô (theo nguồn) | Truy cập |
| --- | --- | --- | --- |
| Câu hỏi lập trình để cho AI sinh code | [Spracklen: prompt](https://github.com/Spracks/PackageHallucination) · [Zenodo](https://zenodo.org/records/14676377) | 20.163 câu Stack Overflow + 19.806 câu do AI sinh (theo Churilov) | Tải ngay (MIT) |
| Tên gói thật (lớp âm) | Cùng repo Spracklen (master list) | PyPI 500.565 tên; npm khoảng 3 triệu tên (theo Churilov) | Tải ngay (MIT) |
| Tên ảo giác quy mô lớn | [Spracklen: corpus](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf), email joseph.spracklen@utsa.edu · [Churilov](https://arxiv.org/pdf/2605.17062), [Zenodo](https://doi.org/10.5281/zenodo.19859120) | Spracklen: 205.474 tên duy nhất | Chỉ cấp cho nhà nghiên cứu đã xác minh |
| Tên ảo giác tự sinh | Dùng prompt ở trên và pipeline của Spracklen (`generate_code.py`, `package_detection.py`) | Xem phần "Model pre-train và lượng dữ liệu để tự train" về số mẫu cần | Tự làm |
| Kiểm tra thực tế (tên ảo giác) | [Trend Micro](https://github.com/trendmicro/slopsquatting) · [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset) | DepScope: 161 tên (05/2026); Trend Micro: 100 tác vụ, chưa đếm số dòng | Tải ngay (MIT; CC-BY-NC-SA, cấm thương mại) |
| Kiểm tra ngoài phân phối (gói giả mạo tên) | [NeupaneDB](https://github.com/ldklab/typomind-release) · [ConfuDB](https://github.com/confuguard/confuguard) · [ecosyste-ms](https://github.com/ecosyste-ms/typosquatting-dataset) | Tối đa 2.156 mẫu giả mạo (633 + 1.380 + 143), chưa kiểm tra trùng lặp | Tải ngay |
| Loại gói độc hại khỏi lớp tên thật | [OpenSSF](https://github.com/ossf/malicious-packages) · [DataDog](https://github.com/DataDog/malicious-software-packages-dataset) | DataDog: 17.367 gói (theo README ecosyste-ms) | Tải ngay, chưa kiểm tra giấy phép |
| Đo báo nhầm trên dữ liệu thực | RSS PyPI: [gói mới](https://pypi.org/rss/packages.xml) · [bản phát hành](https://pypi.org/rss/updates.xml) | ODFA thu 91.949 bản phát hành trong 37 ngày | Công khai |
