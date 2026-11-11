#!/usr/bin/env bash
# Cài / gỡ bộ giữ nhiệt CPU trên máy chạy Ollama. Chạy bằng sudo.
#   sudo bash scripts/kali/install_thermal_cap.sh            cài và bật (tự chạy lại sau khi khởi động máy)
#   sudo bash scripts/kali/install_thermal_cap.sh uninstall  gỡ, trả xung về mặc định
#   journalctl -u thermal-cap -f                             xem nhiệt độ và xung theo thời gian
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
[[ $EUID -eq 0 ]] || { echo "Cần chạy bằng sudo." >&2; exit 1; }

if [[ "${1:-install}" == "uninstall" ]]; then
  systemctl disable --now thermal-cap.service 2>/dev/null || true
  rm -f /etc/systemd/system/thermal-cap.service /usr/local/bin/thermal-cap.sh
  systemctl daemon-reload
  echo "Đã gỡ. Xung tối đa đã trở về mặc định."
  exit 0
fi

install -m 755 "$DIR/thermal-cap.sh" /usr/local/bin/thermal-cap.sh
install -m 644 "$DIR/thermal-cap.service" /etc/systemd/system/thermal-cap.service
systemctl daemon-reload
systemctl enable --now thermal-cap.service
sleep 1
systemctl --no-pager --lines=3 status thermal-cap.service
echo
echo "Đã cài. Xem nhiệt độ: journalctl -u thermal-cap -f"
