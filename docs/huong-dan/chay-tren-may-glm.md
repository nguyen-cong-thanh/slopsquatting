# Chạy thu thập dữ liệu trên máy GLM

Gói này dùng để gửi bộ câu hỏi lập trình cho GLM 5.3 trên máy nội bộ. Máy không cần Internet và không cần cài thư viện nào, chỉ cần **Python 3.11 trở lên**. Kết quả là một file `data/glm.sqlite`, sau đó mang về máy chính để gộp.

## 1. Chuẩn bị

Có hai cách lấy code về máy GLM:

- **Clone repo:** `git clone git@github.com:nguyen-cong-thanh/slopsquatting.git && cd slopsquatting`
- **Gói nén từ máy chính:** `tar -xzf glm-bundle.tar.gz && cd glm-bundle`

Không cần chạy `uv sync` hay `pip install`: phần chạy trên máy GLM chỉ dùng thư viện chuẩn của Python.

Nếu dùng bản clone, bộ câu hỏi không có trong git. Chép file `data/exports/prompts_spracklen.jsonl` từ máy chính sang máy GLM thành `data/prompts.jsonl` (khoảng 20 MB). Máy GLM có Internet thì không cần: script ở dưới tự tải.

Chạy script chuẩn bị. Script kiểm tra từng bước và dừng ở bước đầu tiên còn thiếu; sửa xong thì chạy lại:

```bash
bash scripts/setup_glm.sh
```

Lần đầu, script tạo file `configs/models/glm53-internal.local.toml`. Đây là cấu hình riêng của máy này, không đưa lên git, nên `git pull` không bị xung đột. Mở file đó và sửa ba chỗ:

- `base_url`: địa chỉ API, kết thúc bằng `/v1`, ví dụ `http://10.0.0.5:8000/v1`.
- `model`: đúng tên model mà server trả về. Xem bằng lệnh `curl <base_url>/models`.
- Nếu server cần khóa: bỏ dấu `#` ở dòng `api_key_env` rồi đặt khóa vào biến môi trường, ví dụ `export GLM_API_KEY=...`.

Trong file này còn hai tùy chọn, chỉ cần sửa khi server báo lỗi:

- `think_style`: cách tắt chế độ suy nghĩ. Dùng `"chat_template_kwargs"` cho vLLM/SGLang, `"zhipu"` cho API kiểu Zhipu/Z.ai.
- `send_top_k`: đặt `false` nếu server không nhận tham số `top_k`.

## 2. Thử kết nối

Chạy lại `bash scripts/setup_glm.sh`. Bước cuối của script gửi một câu ngắn cho GLM rồi in câu trả lời và số token. Nếu `reasoning` khác `null` thì chế độ suy nghĩ vẫn đang bật: đổi `think_style` rồi thử lại.

## 3. Chạy thử 200 câu

```bash
bash scripts/run_bg.sh flows/glm-pilot.toml
bash scripts/run_bg.sh flows/glm-pilot.toml status
```

Lệnh `status` cho biết số câu đã xong và thời gian còn lại ước tính. Nếu chạy ổn và server còn dư sức, có thể tăng `concurrency` trong file cấu hình model để gửi nhiều câu cùng lúc.

## 4. Chạy toàn bộ

Chạy ở nền: đóng terminal hay mất SSH không ảnh hưởng.

```bash
bash scripts/run_bg.sh flows/glm-generate.toml           # bắt đầu, hoặc tiếp tục sau khi dừng
bash scripts/run_bg.sh flows/glm-generate.toml status    # tiến độ: tổng, đã xong, còn lại, lỗi, số giờ còn lại
tail -f data/logs/glm-generate.log                        # xem log
bash scripts/run_bg.sh flows/glm-generate.toml stop      # dừng: lưu các câu đã xong rồi thoát
```

- 200 câu đã chạy ở bước 3 được giữ lại, không hỏi lại.
- Server GLM tạm ngừng hoặc mất mạng: chương trình tạm dừng, mỗi phút thử lại, không ghi lỗi. Server trả lời lại thì chạy tiếp.
- Câu lẻ bị lỗi được tự hỏi lại ở cuối, tối đa 5 lượt.
- Máy khởi động lại: chạy lại lệnh `start`, chương trình tiếp tục từ chỗ dừng.

## 5. Mang kết quả về

Đợi tới khi `status` báo "Không chạy." (đã chạy xong hoặc đã dừng hẳn), rồi chép **chỉ một file** `data/glm.sqlite` về máy chính. Ở máy chính, chạy:

```bash
uv run python -m slopcollect merge data/glm.sqlite
```

Không đưa `data/glm.sqlite` lên git: thư mục `data/` đã bị git bỏ qua, và danh sách tên bịa chỉ được công bố sau khi đã báo cho PyPI.

## Cập nhật code

Với bản clone: chạy `git pull`. Các câu đã sinh vẫn được giữ, trừ khi bản cập nhật đổi mẫu câu hỏi hoặc tham số sinh.

## Lần sau: hỏi lại để thu biến thể

Chép file `data/exports/prompts_variants_glm.jsonl` từ máy chính sang máy GLM thành `data/prompts_variants.jsonl`. Nếu dùng gói nén thì giải nén gói mới; file cấu hình `.local.toml` đã sửa có thể chép lại. Rồi chạy:

```bash
bash scripts/run_bg.sh flows/glm-variants.toml
```

Sau đó mang `data/glm.sqlite` về và gộp như bước 5.

## Lưu ý

- Không sửa file `data/prompts.jsonl`. Mỗi câu có mã kiểm tra; nếu bị sửa, chương trình sẽ báo lỗi.
- Tên gói trong kết quả có thể là tên do model bịa ra. Không cài thử và không đăng ký các tên này.
