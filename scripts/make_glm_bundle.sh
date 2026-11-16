#!/usr/bin/env bash
# Đóng gói code + cấu hình + câu hỏi để mang sang máy GLM (không có Internet).
# Máy đích chỉ cần Python >= 3.11, không cần cài thư viện nào.
#
# Cách dùng (chạy ở thư mục gốc repo, sau khi đã chạy flows/prepare-glm.toml):
#   bash scripts/make_glm_bundle.sh                      # gói câu hỏi Spracklen
#   PROMPTS=data/exports/prompts_variants_glm.jsonl PROMPTS_NAME=prompts_variants.jsonl \
#     bash scripts/make_glm_bundle.sh dist/glm-variants   # gói câu hỏi hỏi lại (biến thể)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-dist/glm-bundle}"
PROMPTS="${PROMPTS:-data/exports/prompts_spracklen.jsonl}"
PROMPTS_NAME="${PROMPTS_NAME:-prompts.jsonl}"

cd "$ROOT"
if [[ ! -s "$PROMPTS" ]]; then
  echo "Không thấy $PROMPTS. Chạy trước: uv run python -m slopcollect run flows/prepare-glm.toml" >&2
  exit 1
fi

rm -rf "$OUT" "$OUT.tar.gz"
mkdir -p "$OUT/configs/models" "$OUT/configs/tasks" "$OUT/flows" "$OUT/data"
cp -r src/slopcollect "$OUT/"
find "$OUT/slopcollect" -name '__pycache__' -prune -exec rm -rf {} +
cp configs/models/glm53-internal.toml configs/models/fake.toml "$OUT/configs/models/"
cp configs/tasks/*.toml "$OUT/configs/tasks/"
cp flows/glm-pilot.toml flows/glm-generate.toml flows/glm-variants.toml "$OUT/flows/"
cp "$PROMPTS" "$OUT/data/$PROMPTS_NAME"
mkdir -p "$OUT/scripts"
cp scripts/run_bg.sh scripts/setup_glm.sh "$OUT/scripts/"
cp flows/prepare-glm.toml "$OUT/flows/"
cp docs/huong-dan/chay-tren-may-glm.md "$OUT/HUONG-DAN.md"
git rev-parse HEAD > "$OUT/VERSION" 2>/dev/null || echo "unknown" > "$OUT/VERSION"

tar -czf "$OUT.tar.gz" -C "$(dirname "$OUT")" "$(basename "$OUT")"
echo "Đã tạo $OUT.tar.gz"
sha256sum "$OUT.tar.gz"
