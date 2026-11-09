-- Lượt tải 90 ngày gần nhất cho danh sách gói (BigQuery, bảng công khai của PyPI).
-- Tạo bảng tạm my_dataset.names(name STRING) từ dataset.csv trước khi chạy.
-- Lọc theo partition timestamp để giới hạn chi phí quét.
SELECT REPLACE(LOWER(file.project), '_', '-') AS name, COUNT(*) AS downloads_90d,
       COUNT(DISTINCT DATE(timestamp)) AS active_days
FROM `bigquery-public-data.pypi.file_downloads`
WHERE DATE(timestamp) BETWEEN DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY) AND CURRENT_DATE()
  AND REPLACE(LOWER(file.project), '_', '-') IN (SELECT name FROM `my_dataset.names`)
GROUP BY name;
