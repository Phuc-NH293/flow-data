# GitHub Commit Data Pipeline
docker compose exec airflow airflow dags trigger github_commit_pipeline
docker compose restart airflow
Pipeline end-to-end lấy commit từ GitHub REST API, lưu vào PostgreSQL, transform
bằng dbt, điều phối bằng Airflow và hiển thị bằng Metabase.

## Nguồn và grain

- Nguồn: `GET /repos/{owner}/{repo}/commits`.
- Repository mặc định: `apache/airflow`, đổi bằng `GITHUB_REPOSITORY`.
- Window: GitHub API parameters `since` và `until`.
- Pagination: `per_page=100`, tăng `page` đến trang cuối.
- Natural key: `commit_sha`.
- Staging grain: 1 dòng = 1 commit.
- Mart grain: 1 dòng = 1 author trong 1 repository, trong 1 ngày UTC.
- Mart key: `(commit_date, repository, author_key)`.

Luồng:

```text
GitHub Commits API
  -> raw.github_commits
  -> staging.stg_github_commits
  -> mart.agg_commit_activity_daily
  -> Metabase
```

## Chạy project

```bash
cp .env.example .env
```

Nếu đã chạy bản nguồn log mô phỏng trước đây, reset volume một lần để tạo schema
GitHub mới:

```bash
docker compose down --volumes
```

`GITHUB_TOKEN` là tùy chọn với repository public, nhưng nên thiết lập PAT để
tránh giới hạn anonymous API thấp:

```env
GITHUB_REPOSITORY=apache/airflow
GITHUB_TOKEN=github_pat_xxx
```

Sau đó:

```bash
docker compose up --build
```

- Dashboard: <http://localhost:3001>
- Airflow: <http://localhost:8080>

Không commit `.env` hoặc token lên Git.

## Sáu tiêu chí

### 1. Idempotent

Raw append-only nên chạy lại có thể tăng. Staging dùng `row_number()` theo
`commit_sha`; mart được dựng lại từ staging nên số commit không đổi:

```bash
docker compose exec -T postgres psql \
  -U pipeline_user -d resident_analytics \
  -f /dev/stdin < sql/prove_idempotency.sql
```

### 2. Backfill

DAG chạy mỗi phút và không catch up tự động. Chạy 7 ngày:

```bash
docker compose exec airflow airflow dags backfill github_commit_pipeline \
  --start-date 2026-07-01 --end-date 2026-07-07
```

Chạy hai lần rồi dùng `prove_idempotency.sql`; staging và mart phải không đổi.

### 3. Raw là raw

Extractor insert nguyên response object vào `_raw`; `_ingested_at` do database
sinh. Record thiếu SHA hoặc timestamp đi vào `raw.rejected_github_commits`.

### 4. Tách tầng

- Raw: payload API nguyên bản.
- Staging: parse JSON, dedupe, UTC, null và type.
- Mart: group theo ngày/author và tính commit, merge, verified rate.
- Dashboard: chỉ query `mart.agg_commit_activity_daily`.

Metabase dùng role `dashboard_reader` chỉ có `SELECT` trên mart:

```bash
docker compose exec postgres psql \
  -U dashboard_reader -d resident_analytics \
  -f /dev/stdin < sql/prove_dashboard_access.sql
```

Query mart thành công; query raw và staging phải bị `permission denied`.

### 5. dbt tests

Có test not-null, unique SHA, unique mart grain, positive commit count và custom
business invariant. Chạy:

```bash
docker compose exec airflow dbt test \
  --project-dir /opt/flow-data/dbt --profiles-dir /opt/flow-data/dbt
```

Cố tình phá mart:

```bash
docker compose exec -T postgres psql \
  -U pipeline_user -d resident_analytics \
  -f /dev/stdin < sql/break_custom_test_demo.sql

docker compose exec airflow dbt test \
  --project-dir /opt/flow-data/dbt --profiles-dir /opt/flow-data/dbt \
  --select assert_commit_count_balances
```

Test phải fail. Chạy `dbt run` để khôi phục.

### 6. Reproducible

Toàn bộ PostgreSQL, Airflow, dbt và Metabase được khai báo trong Compose.
Datasource/dashboard được provision từ code; credentials lấy từ `.env`.

## Dashboard (Metabase)

Sau lần khởi động đầu tiên, mở Metabase tại `http://localhost:3001`, tạo tài
khoản quản trị, rồi kết nối PostgreSQL bằng các thông tin:

- Host: `postgres`
- Port: `5432`
- Database: giá trị `POSTGRES_DB`
- User: giá trị `DASHBOARD_DB_USER`
- Password: giá trị `DASHBOARD_DB_PASSWORD`

Chọn schema `mart`, sau đó tạo các câu hỏi/dashboard: tổng commit theo ngày,
tỷ lệ verified, top author và bảng hoạt động author.
