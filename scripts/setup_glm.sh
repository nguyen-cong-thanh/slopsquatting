#!/usr/bin/env bash
# Chuẩn bị máy GLM (bản clone repo hoặc gói glm-bundle) và thử kết nối. Chạy lại được nhiều lần.
#   bash scripts/setup_glm.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PY="${PYTHON:-python3}"
if [[ -d "$ROOT/src/slopcollect" ]]; then export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"; fi
SC=("$PY" -m slopcollect --root "$ROOT")
MODEL=glm53-internal
LOCAL="configs/models/$MODEL.local.toml"

echo "1. Python"
if ! "$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 11) else 1)'; then
  echo "   Cần Python >= 3.11 (hiện có: $("$PY" --version 2>&1)). Đặt PYTHON=/duong/dan/python3.11 rồi chạy lại." >&2
  exit 1
fi
echo "   $("$PY" --version) - được"

echo "2. Cấu hình model ($LOCAL)"
if [[ ! -f "$LOCAL" ]]; then
  cp "configs/models/$MODEL.toml" "$LOCAL"
  echo "   Đã tạo $LOCAL từ mẫu. Mở file, sửa base_url và model cho đúng server GLM, rồi chạy lại script này."
  exit 1
fi
echo "   có sẵn - được (file này không đưa lên git)"

echo "3. Bộ câu hỏi (data/prompts.jsonl)"
mkdir -p data
if [[ ! -s data/prompts.jsonl ]]; then
  if [[ -s data/exports/prompts_spracklen.jsonl ]]; then
    cp data/exports/prompts_spracklen.jsonl data/prompts.jsonl
  elif "${SC[@]}" --db data/prepare.sqlite run flows/prepare-glm.toml >/dev/null 2>&1; then
    cp data/exports/prompts_spracklen.jsonl data/prompts.jsonl
  else
    echo "   Không tải được bộ câu hỏi (máy không có Internet)." >&2
    echo "   Chép file data/exports/prompts_spracklen.jsonl từ máy chính sang đây thành data/prompts.jsonl rồi chạy lại." >&2
    exit 1
  fi
fi
echo "   $(wc -l < data/prompts.jsonl) câu - được"

echo "4. Thử gọi GLM"
"${SC[@]}" ping "$MODEL"
echo
echo "Xong. Nếu \"reasoning\" ở trên khác null: đổi think_style trong $LOCAL rồi chạy lại."
echo "Chạy thử 200 câu:   bash scripts/run_bg.sh flows/glm-pilot.toml"
echo "Chạy toàn bộ:       bash scripts/run_bg.sh flows/glm-generate.toml"
