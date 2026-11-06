# Báo cáo tổng hợp sau khảo sát: metrics, model và dữ liệu

> Chuyển sang markdown từ `bBáo cáo tổng hợp sau khảo sát v2 (thêm kiểm tra tính mới)` (Google Drive, thư mục “Khảo sát thêm metrics”, sửa lần cuối 18/10/2026). Bản gốc là Google Docs.

## Metrics của đề tài

Các luồng:

- A là detector tên gói tĩnh (Names Can Hurt, Typomind, ConfuGuard).
- B là detector gói độc hại và gói giả mạo tên (ODFA, AgentGuard, Cerebro).
- C là phân loại chuỗi ký tự ngắn kiểu tên miền DGA (Yu et al., CharBot, MaskDGA).
- D là đo tỷ lệ ảo giác (Spracklen, Churilov, Library Hallucinations). (Phụ)
- E là tấn công điều hướng LLM chọn gói (Dependency Steering). (Phụ)

| Metric | Trả lời câu hỏi nào | Dẫn chứng từ đề tài tương tự | Luồng |
| --- | --- | --- | --- |
| TPR@1%FPR (thước đo chính) | Chỉ cho báo nhầm 1 trong 100 gói thật, bắt được bao nhiêu % tên giả? | [ODFA](https://arxiv.org/html/2512.04338): đạt 95,27% và nêu 1% FPR là thông lệ. [Yu et al.](https://faculty.washington.edu/mdecock/papers/byu2018a.pdf) (tên miền DGA): 83% với Random Forest, 97 đến 98% với mạng sâu | B, C |
| Số cảnh báo sai mỗi ngày | Hệ thống có làm phiền người dùng quá nhiều không? | ODFA: FPR 0,1% cho khoảng 2,18 cảnh báo sai mỗi ngày, vừa với ngân sách 20 phút mỗi tuần của người duyệt | B |
| Precision theo tỷ lệ thực | Khi hệ thống báo động, bao nhiêu % là đúng? | [Arp et al.](https://arxiv.org/pdf/2010.09470) cảnh báo lỗi bỏ qua tỷ lệ thực. ODFA: Precision chỉ 18,73% ở FPR 1% vì gói độc hại rất hiếm | A, B |
| PHR (tỷ lệ gói ảo giác) | AI bịa tên gói thường xuyên đến mức nào? | [Spracklen](https://www.usenix.org/system/files/usenixsecurity25-spracklen.pdf): 5,2% model thương mại, 21,7% model mã nguồn mở. [Churilov](https://arxiv.org/pdf/2605.17062): 4,62 đến 6,10% | D |
| Độ chính xác của nhãn | Dữ liệu gắn nhãn "ảo giác" có đúng không? | [Library Hallucinations](https://arxiv.org/pdf/2509.22202): kiểm thủ công 200 mẫu, đúng 95,8%. [DepScope](https://github.com/cuttalo/depscope-hallucinations-dataset): 97,6% ứng viên ban đầu hóa ra là gói thật | A, D |
| ASR | Kẻ gian sửa tên thì lừa được bộ phát hiện bao nhiêu %? | [TextAttack](https://textattack.readthedocs.io/en/latest/1start/what_is_an_adversarial_attack.html): ví dụ 128/157 = 81,5%. [MaskDGA](https://arxiv.org/abs/1902.08909): điểm F1 giảm từ 0,977 xuống 0,495 | C, E |
| Robust TPR | Sau khi bị sửa tên, còn bắt được bao nhiêu % tên giả? | ODFA: 95,27% giảm còn 24,30% khi bị tấn công; sau huấn luyện đối kháng còn 86,81% | B |
| ΔTPR | Học thêm mẫu bị sửa có làm kém đi ở tên bình thường không? | ODFA: 95,27% lên 95,64% trên MalwareBench, tức không mất | B |
| Kiểm định thống kê | Chênh lệch giữa hai mô hình là thật hay do ngẫu nhiên? | Churilov (cùng lĩnh vực): khoảng tin cậy Wilson, hiệu chỉnh Holm. [EvoSafeHarness](https://arxiv.org/pdf/2609.05903): McNemar cho so sánh cặp | D |

### Giới hạn của các bài liên quan, theo luồng

| Luồng | Bài tiêu biểu | Metrics bài tiêu biểu đã dùng | Giới hạn chính | Metrics của đề tài |
| --- | --- | --- | --- | --- |
| A. Detector tên gói tĩnh | Names Can Hurt, Typomind, ConfuGuard | Precision, Recall, F1 ở một ngưỡng | Chỉ báo P/R/F1 ở một ngưỡng. Ghi chú trong bản gốc: tập kiểm thử lệch (ConfuDB khoảng 27%, NeupaneDB 75% mẫu giả mạo). Nhãn ảo giác lẫn cả gói đã đăng ký. | TPR@1%FPR, Precision theo tỷ lệ thực, Độ chính xác của nhãn |
| B. Gói độc hại và gói giả mạo tên | ODFA, AgentGuard, Cerebro | ODFA: TPR@1%FPR và @0,1%FPR, Precision, số cảnh báo sai mỗi ngày. AgentGuard: Recall, F1, ΔRecall | ODFA tấn công vào code, không vào tên; đạt 95,27% trên MalwareBench nhưng 68,36% trên PyPI thật. AgentGuard chỉ lật metadata nên ΔRecall bằng 0 của cấu hình chỉ-tên chưa chứng minh được độ bền. Không có kiểm định thống kê. | TPR@1%FPR, Số cảnh báo sai, Robust TPR, ΔTPR, Kiểm định thống kê |
| C. Chuỗi ký tự ngắn (tên miền DGA) | Yu et al., CharBot, MaskDGA | Yu et al.: TPR ở FPR 0,1%. CharBot: kết quả ở FPR 0,1% và 1%. MaskDGA: F1 | Đo trên tên miền, không phải tên gói. | ASR, TPR@1%FPR |
| D. Đo tỷ lệ ảo giác | Spracklen, Churilov, Library Hallucinations | PHR (tỷ lệ gói ảo giác). Churilov: thêm khoảng tin cậy Wilson và hiệu chỉnh Holm. Library Hallucinations: kiểm thủ công 200 mẫu | Chỉ đo hiện tượng, không có bộ phát hiện. Hai cách tính PHR nên số liệu không so trực tiếp được (0,22% đến 46,15%). Bộ 205.474 tên của Spracklen không công bố. | PHR, Độ chính xác của nhãn, Kiểm định thống kê |
| E. Tấn công điều hướng LLM chọn gói | Dependency Steering | THR, đo việc LLM chọn gói của kẻ tấn công (tối đa 100% trên Qwen2.5-Coder) | Đo việc LLM chọn tên gói của kẻ tấn công, không đo việc né bộ phát hiện. Chỉ Python, chỉ model mã nguồn mở, phòng thủ được thử chỉ là bộ quét skill. | ASR |

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

## Đề tài so với các luồng: kiểm tra tính mới

| Luồng | Luồng đã làm | Đề tài của tôi thêm |
| --- | --- | --- |
| A. Detector tên gói tĩnh | Phát hiện tên gói tĩnh, báo P/R/F1 ở một ngưỡng, chưa thử sửa tên để né. | Đo bộ phát hiện chỉ-tên (D0) khi bị sửa tên, và D′ huấn luyện đối kháng. |
| B. Gói độc hại và gói giả mạo tên | ODFA đã tấn công thích nghi và huấn luyện đối kháng, nhưng trên code gói độc hại. | Chuyển sang tên gói, đo Robust TPR và ΔTPR trên tên. |
| C. Chuỗi ký tự ngắn (tên miền DGA) | CharBot, MaskDGA tấn công tên miền không phải tên gói | Chuyển từ tên miền sang tên gói |
| D. Đo tỷ lệ ảo giác | Chỉ đo PHR, không có bộ phát hiện. | Dùng PHR làm nguồn dữ liệu và độ chính xác của nhãn. |
| E. Tấn công điều hướng LLM chọn gói | Dependency Steering: tấn công chủ động, không đo bộ phát hiện. | Báo ASR theo hai mô hình đe dọa (thụ động và chủ động) cùng khoảng cách thực hiện được. |
