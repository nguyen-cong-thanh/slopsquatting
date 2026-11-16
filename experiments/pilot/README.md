# Pilot: dữ liệu công khai + metadata PyPI

Kết quả và phân tích: [docs/du-lieu/bao-cao-thu-nghiem-pilot.md](../../docs/du-lieu/bao-cao-thu-nghiem-pilot.md). Số liệu gốc: [results/results.json](results/results.json).

Danh sách tên gói không được commit (công bố có trách nhiệm); chạy lại các bước dưới đây để tái tạo.

```bash
pip install scikit-learn pandas xgboost torch rapidfuzz
```

```bash
mkdir -p work/ext && cd work/ext
for r in 0pstech/slopsquatting-dataset trendmicro/slopsquatting cuttalo/depscope-hallucinations-dataset Spracks/PackageHallucination; do git clone --depth 1 https://github.com/$r; done
git clone --depth 1 --filter=blob:none --no-checkout https://github.com/ossf/malicious-packages ossf
cd ..
```

```bash
(cd ext/ossf && git ls-tree -d --name-only HEAD osv/malicious/pypi/ | sed 's#.*/##') > ossf_pypi.txt
curl -s -H 'Accept: application/vnd.pypi.simple.v1+json' https://pypi.org/simple/ -o simple.json
```

```bash
python ../build_dataset.py ext .        # ~20k lượt gọi PyPI JSON API, ~15 phút
python ../run_experiments.py dataset.csv . ext/slopsquatting/slopsquatting.jsonl
```

Kết quả phụ thuộc thời điểm chạy (trạng thái PyPI thay đổi hằng ngày); pilot chạy ngày 09/11/2026.
