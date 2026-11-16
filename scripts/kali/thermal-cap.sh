#!/usr/bin/env bash
# Giữ nhiệt độ CPU quanh mức mục tiêu bằng cách chỉnh xung tối đa (scaling_max_freq).
# KHÔNG đụng tới quạt / chế độ hiệu năng (platform_profile): quạt giữ mặc định.
#
# Cứ INTERVAL giây đọc nhiệt độ CPU (x86_pkg_temp):
#   > TARGET_HIGH        -> giảm xung tối đa STEP_MHZ (nóng hơn 6°C: giảm gấp 3)
#   < TARGET_LOW         -> tăng xung tối đa STEP_MHZ
#   trong khoảng đó      -> giữ nguyên
# Dừng service -> trả xung tối đa về mức gốc của máy.
#
# Cấu hình qua biến môi trường (đặt trong file service): TARGET_HIGH, TARGET_LOW, MIN_MHZ, MAX_MHZ,
# START_MHZ, STEP_MHZ, INTERVAL. SYS là gốc của /sys (chỉ đổi khi test).
set -u
SYS=${SYS:-/sys}
HIGH=${TARGET_HIGH:-82}; LOW=${TARGET_LOW:-77}
MIN=${MIN_MHZ:-1200}; MAX=${MAX_MHZ:-3200}; START=${START_MHZ:-2400}
STEP=${STEP_MHZ:-100}; INTERVAL=${INTERVAL:-10}

zone=""
for z in "$SYS"/class/thermal/thermal_zone*; do [ "$(cat "$z/type")" = x86_pkg_temp ] && zone=$z; done
[ -n "$zone" ] || { echo "Không tìm thấy cảm biến x86_pkg_temp"; exit 1; }
files=("$SYS"/devices/system/cpu/cpu*/cpufreq/scaling_max_freq)
hw_max=$(( $(cat "$SYS/devices/system/cpu/cpu0/cpufreq/cpuinfo_max_freq") / 1000 ))
(( MAX > hw_max )) && MAX=$hw_max

set_freq() { for f in "${files[@]}"; do echo $(( $1 * 1000 )) > "$f"; done; }
cur=$START
(( cur > MAX )) && cur=$MAX; (( cur < MIN )) && cur=$MIN
set_freq "$cur"
echo "Bắt đầu: giữ CPU trong ${LOW}-${HIGH}°C, xung tối đa ${MIN}-${MAX} MHz, khởi điểm ${cur} MHz. Quạt: không đổi."
trap 'set_freq "$hw_max"; echo "Dừng: trả xung tối đa về ${hw_max} MHz"; exit 0' TERM INT

n=0
while true; do
  t=$(( $(cat "$zone/temp") / 1000 ))
  new=$cur
  if (( t > HIGH + 6 )); then new=$(( cur - 3 * STEP ))
  elif (( t > HIGH )); then new=$(( cur - STEP ))
  elif (( t < LOW )); then new=$(( cur + STEP )); fi
  (( new < MIN )) && new=$MIN
  (( new > MAX )) && new=$MAX
  if (( new != cur )); then cur=$new; set_freq "$cur"; fi
  (( n++ % 30 == 0 )) && echo "Nhiệt ${t}°C, xung tối đa ${cur} MHz"
  [ -n "${MAX_LOOPS:-}" ] && (( n >= MAX_LOOPS )) && break
  sleep "$INTERVAL" & wait $!
done
