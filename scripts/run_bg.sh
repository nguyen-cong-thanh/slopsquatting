#!/usr/bin/env bash
# Chạy một luồng ở nền cho các lần chạy dài: không phụ thuộc cửa sổ terminal, tự chạy lại khi lỗi
# (--keep-going), ghi log và pid. Chạy lại script này sau khi máy khởi động lại để tiếp tục.
#
#   bash scripts/run_bg.sh flows/local-full.toml          bắt đầu / tiếp tục
#   bash scripts/run_bg.sh flows/local-full.toml stop     dừng (lưu các câu đã xong rồi thoát)
#   bash scripts/run_bg.sh flows/local-full.toml status   tiến độ
#   tail -f data/logs/local-full.log                       xem log
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FLOW="${1:?Cách dùng: bash scripts/run_bg.sh <flows/xxx.toml> [start|stop|status]}"
ACTION="${2:-start}"
NAME="$(basename "$FLOW" .toml)"
cd "$ROOT"
LOGDIR="data/logs"
PIDFILE="$LOGDIR/$NAME.pid"
mkdir -p "$LOGDIR"

# Repo có .venv (máy chính) thì dùng; không thì python3 (bản clone hoặc gói GLM, không cần thư viện ngoài).
if [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"; else PY="${PYTHON:-python3}"; fi
# Bản clone repo: package nằm trong src/.
if [[ -d "$ROOT/src/slopcollect" ]]; then export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"; fi
SC=("$PY" -m slopcollect --root "$ROOT")

running() { [[ -f "$PIDFILE" ]] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; }

case "$ACTION" in
  start)
    if running; then
      echo "Đang chạy rồi (pid $(cat "$PIDFILE")). Xem: tail -f $LOGDIR/$NAME.log"
      exit 0
    fi
    nohup "${SC[@]}" --log-file "$LOGDIR/$NAME.log" run "$FLOW" --keep-going >>"$LOGDIR/$NAME.out" 2>&1 &
    echo $! >"$PIDFILE"
    echo "Đã chạy nền luồng $NAME (pid $!)."
    echo "  log:      tail -f $LOGDIR/$NAME.log"
    echo "  tiến độ:  bash scripts/run_bg.sh $FLOW status"
    echo "  dừng:     bash scripts/run_bg.sh $FLOW stop"
    ;;
  stop)
    if running; then
      kill -TERM "$(cat "$PIDFILE")"
      echo "Đã gửi tín hiệu dừng tới pid $(cat "$PIDFILE"); tiến trình lưu các câu đã xong rồi thoát."
    else
      echo "Không có tiến trình nào đang chạy cho $NAME."
    fi
    ;;
  status)
    if running; then echo "Đang chạy (pid $(cat "$PIDFILE"))."; else echo "Không chạy."; fi
    "${SC[@]}" status "$FLOW"
    ;;
  *)
    echo "Hành động không hợp lệ: $ACTION (start | stop | status)" >&2
    exit 2
    ;;
esac
