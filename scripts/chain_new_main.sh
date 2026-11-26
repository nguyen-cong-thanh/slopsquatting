#!/usr/bin/env bash
# Chạy nối tiếp sau khi 3 luồng đầy đủ của model chính mới (mistral32/qwen36/nemotron35-full) xong:
#   gắn nhãn -> chọn tên bịa và hỏi lại (variants-new-main) -> độ bền trên bản cũ (persistence-v3) -> gắn nhãn lại.
# Chạy nền: nohup bash scripts/chain_new_main.sh >> data/logs/chain-new-main.out 2>&1 &
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; export PYTHONPATH="$ROOT/src"
say() { echo "$(date +%H:%M:%S) CHAIN $*" | tee -a data/logs/chain-new-main.log; }
alive() { [[ -f data/logs/$1.pid ]] && kill -0 "$(cat data/logs/$1.pid)" 2>/dev/null; }
say "chờ 3 luồng đầy đủ"
while alive mistral32-full || alive qwen36-full || alive nemotron35-full; do sleep 30; done
for f in mistral32-full qwen36-full nemotron35-full; do
  grep -q "đã xong, không còn câu lỗi" data/logs/$f.log || { say "LỖI: $f dừng mà chưa xong, không chạy tiếp"; exit 1; }
done
for flow in label-enrich-glm variants-new-main persistence-v3 label-enrich-glm; do
  say "bắt đầu $flow"
  if ! $PY -m slopcollect --root "$ROOT" --log-file data/logs/chain-new-main.log run flows/$flow.toml --keep-going; then
    say "LỖI: $flow thất bại, dừng chuỗi"; exit 1
  fi
  say "xong $flow"
done
say "HOÀN TẤT"
