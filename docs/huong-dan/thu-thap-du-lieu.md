# Hướng dẫn thu thập dữ liệu (slopcollect)

Pipeline gửi câu hỏi lập trình cho LLM, lấy tên gói trong câu trả lời, tra PyPI, gắn nhãn, thu metadata và hỏi lại để thu biến thể. Code nằm ở `src/slopcollect/`.

## Cách tổ chức

Pipeline được thiết kế để **đổi model hoặc đổi luồng xử lý mà không phải sửa code**:

| Thành phần | Nằm ở | Muốn đổi thì |
| --- | --- | --- |
| Model | `configs/models/<tên>.toml`: backend, địa chỉ, tên model, tham số | Thêm một file TOML. Backend có sẵn: `ollama`, `openai_compat` (vLLM, SGLang, GLM, OpenRouter...), `fake` |
| Câu hỏi gửi LLM | `configs/tasks/<tên>.toml`: mẫu câu hỏi, tham số, cách trích tên | Thêm một file TOML |
| Luồng | `flows/<tên>.toml`: danh sách các bước và tham số | Sửa hoặc thêm file TOML |
| Bước xử lý, nguồn câu hỏi, danh sách tham chiếu, luật gắn nhãn | Plugin Python, đăng ký bằng `@register(...)` | Viết một hàm mới; không phải sửa các bước khác |

Các bước chỉ trao đổi với nhau qua một file SQLite. Mỗi lần hỏi LLM có một khóa băm, tạo từ câu hỏi, model, tác vụ, tham số và số thứ tự lần hỏi. Nhờ vậy:

- Dừng giữa chừng rồi chạy lại thì chỉ hỏi những câu chưa có. Câu bị lỗi được hỏi lại.
- Đổi tham số hay model sẽ sinh khóa mới, nên kết quả cũ vẫn được giữ.
- File SQLite từ máy khác gộp vào được (lệnh `merge`) mà không sinh bản trùng.
- Thứ tự câu hỏi là ngẫu nhiên nhưng cố định, nên chạy `limit = 200` rồi chạy toàn bộ sẽ dùng lại 200 câu đã có.

## Ba tác vụ hỏi LLM (theo Spracklen và cộng sự, 2025)

Cả ba tác vụ chép đúng mẫu câu hỏi và tham số trong mã nguồn của Spracklen (commit `bd3031cc`), để số liệu so sánh được với bài gốc.

| Tác vụ | Hỏi gì | Cách lấy tên gói |
| --- | --- | --- |
| `spracklen_code_v1` | Sinh code cho câu hỏi (temperature 0,7, tối đa 2048 token) | Lệnh `pip install`; khối `requirements.txt`; lệnh `import` |
| `spracklen_pkgs_for_code_v1` | "Cần gói nào để chạy đoạn code này?" (temperature 0,01, tối đa 64 token) | Danh sách cách nhau bởi dấu phẩy |
| `spracklen_pkgs_for_prompt_v1` | "Gói nào hữu ích cho bài toán này?" | Danh sách cách nhau bởi dấu phẩy |

Spracklen không lấy tên từ lệnh `import`, vì cách này lẫn cả module cục bộ do LLM tự đặt (như `utils`, `config`). Pipeline vẫn lưu tên lấy từ `import`, nhưng ghi riêng `method = "import"`. Thống kê mặc định chỉ dùng `pip_install` và `llm_list`.

Có hai điểm pipeline làm khác Spracklen:

- Lấy đủ mọi tên sau `pip install`, trong khi Spracklen chỉ lấy tên đầu tiên.
- Bỏ mục cuối của danh sách khi câu trả lời bị cắt do hết 64 token, vì mục đó có thể là tên viết dở.

## Luật tên của PyPI

`src/slopcollect/extract/normalize.py` chép đúng luật của PyPI (mã nguồn warehouse, commit `dd5954ec`):

- **Chuẩn hóa tên** (`normalize_pep426_name`): gộp mỗi cụm `.`, `_`, `-` thành `-`, rồi chuyển về chữ thường. Ví dụ `Vector_Cache` thành `vector-cache`. Phép này áp cho **mọi** nhóm tên.
- **Kiểm tra tên mới có đăng ký được không**, theo đúng thứ tự PyPI dùng khi có người tạo project:
  1. Tên không hợp lệ.
  2. Trùng tên module thư viện chuẩn của bất kỳ phiên bản Python nào.
  3. Đã có project cùng tên.
  4. Nằm trong danh sách tên cấm. Danh sách này không công khai nên **không kiểm tra được**.
  5. Quá giống một project đã có: bỏ `.`, `_`, `-`, đổi `l` và `i` thành `1`, đổi `o` thành `0` rồi so.

## Nhãn

| Nhãn | Ý nghĩa | Cần duyệt tay |
| --- | --- | --- |
| `real` | Gói thật, bình thường | Không |
| `hallucinated_absent` | Không có trên PyPI. Kèm thông tin đăng ký được không và vì sao | Không |
| `registered_hallucination` | Có trên PyPI nhưng nghi do người khác đăng ký theo tên bịa. Dấu hiệu: có trong danh sách 0pstech/DepScope, phát hành sau mốc `cutoff_date`, hoặc mới và ít lượt tải | Có |
| `placeholder` | Bản giữ chỗ trỏ sang gói đúng (mô tả có "deprecated", "use X instead"...), hoặc project không có file nào | Có |
| `known_malicious` | Có trong danh sách gói độc hại của DataDog hoặc OSV/OpenSSF | Không |
| `unlabeled` | Có trên PyPI nhưng chưa có metadata | Có |

**Duyệt tay:**

1. Bước `label` ghi các dòng cần duyệt ra `data/review/needs_review.csv`.
2. Điền cột `override_label` (và `note` nếu cần) cho những dòng đã xem.
3. Lưu thành `data/review/overrides.csv` (file riêng, để lần chạy sau không ghi đè).
4. Chạy lại bước `label`. Nhãn duyệt tay được áp trước mọi luật.

## Cài đặt (máy chính, có Internet)

```bash
uv sync --all-extras       # cài stdlib-list, pyarrow, pytest; chỉ lấy bản phát hành đã ra ít nhất 2 tuần
uv run pytest              # chạy test
uv run python -m slopcollect run flows/smoke.toml   # chạy thử cả luồng với model giả, tra PyPI thật
```

Token GitHub (tùy chọn) dùng để lấy số sao GitHub. Bước `metadata` đọc token từ biến môi trường `GITHUB_TOKEN`, nếu không có thì đọc file `~/.config/github/token`. Không có cả hai thì bước này bỏ qua nguồn GitHub.

## Cấu hình Ollama trên máy kali

Ollama mặc định chỉ nghe trên `localhost`. Cách an toàn là cho Ollama nghe trên địa chỉ Tailscale của máy kali, để chỉ các máy trong mạng Tailscale gọi được:

```bash
# trên máy kali
sudo systemctl edit ollama
#   thêm vào phần [Service] và [Unit]:
#   [Unit]
#   After=tailscaled.service
#   Wants=tailscaled.service
#   [Service]
#   Environment="OLLAMA_HOST=100.86.126.91:11434"
sudo systemctl daemon-reload && sudo systemctl restart ollama
ollama pull qwen3.5:4b
```

Kiểm tra từ máy chính:

```bash
uv run python -m slopcollect ping qwen35-4b-kali
```

## Chạy dài ngày

Chạy toàn bộ bộ câu hỏi mất nhiều ngày, nên dùng script chạy nền:

```bash
bash scripts/run_bg.sh flows/local-full.toml           # bắt đầu, hoặc tiếp tục sau khi dừng / khởi động lại máy
bash scripts/run_bg.sh flows/local-full.toml status    # tiến độ: tổng, đã xong, còn lại, lỗi, số giờ còn lại
tail -f data/logs/local-full.log                        # xem log
bash scripts/run_bg.sh flows/local-full.toml stop      # dừng: lưu các câu đã xong rồi thoát
```

Pipeline xử lý các tình huống sau:

| Tình huống | Pipeline làm gì |
| --- | --- |
| Đóng terminal, mất SSH | Không ảnh hưởng: script chạy bằng `nohup` |
| Máy kali mất mạng, Ollama khởi động lại, máy kali ngủ | Thấy nhiều câu liền nhau lỗi tạm thời thì tạm dừng, mỗi phút thử lại một câu, **không ghi lỗi**; nối lại được thì chạy tiếp. Mất kết nối quá 24 giờ thì dừng hẳn |
| Một câu lẻ cứ lỗi | Thử lại vài lần rồi ghi lỗi; cuối luồng tự chạy thêm lượt để thử lại câu lỗi (tối đa 5 lượt) |
| Tiến trình gặp lỗi bất ngờ | Chờ 2 phút rồi tự chạy lại luồng |
| Bị `kill`, Ctrl-C, máy chính khởi động lại | Câu đã xong được lưu (CSDL ghi ít nhất 15 giây một lần). Chạy lại `run_bg.sh ... start` để tiếp tục; câu đã có không bị hỏi lại |

Lưu ý:

- Máy chạy pipeline (máy gọi LLM) không được ngủ. Nếu là laptop, tắt chế độ ngủ khi gập máy, hoặc chạy pipeline trên một máy luôn bật.
- Máy kali cũng cần tắt chế độ ngủ trong lúc chạy.
- Lệnh `status` chỉ tính câu đã đủ điều kiện để hỏi. Hai tác vụ hỏi danh sách gói chạy sau tác vụ sinh code, nên số "tổng" của chúng tăng dần khi phần sinh code chạy xong.

## Quy trình đầy đủ

```bash
# 1. Chạy thử 200 câu trên Qwen, tra PyPI, gắn nhãn, thống kê -> data/exports/pilot_stats.md
uv run python -m slopcollect run flows/pilot.toml

# 2. Chuẩn bị gói cho máy GLM
uv run python -m slopcollect run flows/prepare-glm.toml
bash scripts/make_glm_bundle.sh          # -> dist/glm-bundle.tar.gz, kèm HUONG-DAN.md

# 3. Chạy toàn bộ trên Qwen ở nền (song song với máy GLM); xem mục "Chạy dài ngày"
bash scripts/run_bg.sh flows/local-full.toml

# 4. Gộp kết quả GLM, rồi trích tên, tra PyPI, metadata, gắn nhãn, xuất, thống kê
uv run python -m slopcollect merge data/glm.sqlite
uv run python -m slopcollect run flows/label-enrich.toml

# 5. Thu biến thể: chọn khoảng 500 tên bịa, hỏi lại 10 lần mỗi câu gốc
uv run python -m slopcollect run flows/variants-select.toml
PROMPTS=data/exports/prompts_variants_glm.jsonl PROMPTS_NAME=prompts_variants.jsonl \
  bash scripts/make_glm_bundle.sh dist/glm-variants
uv run python -m slopcollect run flows/variants-generate.toml
uv run python -m slopcollect merge data/glm.sqlite      # sau khi máy GLM chạy flows/glm-variants.toml
uv run python -m slopcollect run flows/label-enrich.toml
uv run python -m slopcollect stage stats selection_id=variants-v1
```

Chạy riêng một bước với tham số tùy ý. Giá trị được đọc theo cú pháp TOML (số, `true`, `["a", "b"]`); chữ thường được hiểu là chuỗi:

```bash
uv run python -m slopcollect stage generate model=qwen35-4b-kali task=spracklen_code_v1 limit=20
uv run python -m slopcollect run flows/pilot.toml --only gen-code      # chỉ chạy một bước của luồng
uv run python -m slopcollect info                                      # số dòng mỗi bảng
```

## Dữ liệu đầu ra

- `data/slop.sqlite`: toàn bộ dữ liệu.
- `data/exports/*.parquet`: từng bảng, cùng hai bảng tổng hợp:
  - `dataset_names`: mỗi tên một dòng, gồm trạng thái trên PyPI, nhãn, metadata, danh sách tham chiếu, tần suất theo model.
  - `dataset_mentions`: mỗi lần một tên xuất hiện trong một câu trả lời.
- `data/exports/stats.md`: các số liệu cần cho việc chốt quy mô:
  - tốc độ và thời gian ước tính cho toàn bộ;
  - tỷ lệ tên không có trên PyPI;
  - đường số tên bịa tăng theo số câu hỏi;
  - tỷ lệ tên bịa đã có người đăng ký;
  - số biến thể khi hỏi lại.

Metadata thu cho mỗi gói có trên PyPI:

- ngày phát hành đầu và cuối, số bản phát hành, số file;
- số người duy trì, có thuộc tổ chức không;
- lượt tải 30 ngày;
- kho GitHub và số sao;
- kho mã nguồn đã xác minh qua Trusted Publishing (`source_repo_verified`).

## Thêm model hoặc luồng mới

- **Model mới qua API kiểu OpenAI:** chép `configs/models/glm53-internal.toml` thành file mới, sửa `base_url` và `model`, rồi dùng tên file trong luồng.
- **Model mới qua Ollama:** chép `configs/models/qwen35-4b-kali.toml`, sửa `model`.
- **Bộ câu hỏi mới:** ghi ra JSONL (`{"text": ..., "tags": [...]}`), nạp bằng `load_prompts` với `source = "jsonl"`. Hoặc viết một plugin `source` trong `src/slopcollect/sources/`.
- **Luật gắn nhãn mới:** viết hàm `@register("label_rule", "<tên>")` trong `src/slopcollect/stages/label.py`, rồi thêm tên vào tham số `rules` của bước `label`.

## Đạo đức

- Không bước nào đăng ký hay đăng tải gì lên PyPI.
- Thư mục `data/` không đưa lên git.
- Danh sách tên bịa chỉ công bố sau khi đã gửi cho đội an ninh của PyPI (xem báo cáo dữ liệu).
