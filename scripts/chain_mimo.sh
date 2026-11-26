#!/usr/bin/env bash
# Chạy nối tiếp sau khi luồng đầy đủ của MiMo-V2.6-Pro (mimo-full) xong:
#   gắn nhãn -> chọn tên bịa và hỏi lại (variants-mimo) -> độ bền trên bản cũ (persistence-mimo) -> gắn nhãn lại.
# Chạy nền: nohup bash scripts/chain_mimo.sh >> data/logs/chain-mimo.out 2>&1 &
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"; cd "$ROOT"
PY=.venv/bin/python; export PYTHONPATH="$ROOT/src"
say() { echo "$(date +%H:%M:%S) CHAIN $*" | tee -a data/logs/chain-mimo.log; }
alive() { [[ -f data/logs/$1.pid ]] && kill -0 "$(cat data/logs/$1.pid)" 2>/dev/null; }
say "chờ luồng đầy đủ"
while alive mimo-full; do sleep 30; done
for f in mimo-full; do
  grep -q "đã xong, không còn câu lỗi" data/logs/$f.log || { say "LỖI: $f dừng mà chưa xong, không chạy tiếp"; exit 1; }
done
for flow in label-enrich-glm variants-mimo persistence-mimo label-enrich-glm; do
  say "bắt đầu $flow"
  if ! $PY -m slopcollect --root "$ROOT" --log-file data/logs/chain-mimo.log run flows/$flow.toml --keep-going; then
    say "LỖI: $flow thất bại, dừng chuỗi"; exit 1
  fi
  say "xong $flow"
done
say "HOÀN TẤT"
