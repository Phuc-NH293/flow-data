CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS mart;

CREATE TABLE IF NOT EXISTS raw.github_commits (
    raw_id BIGSERIAL PRIMARY KEY,
    _raw JSONB NOT NULL,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_github_commits_sha
    ON raw.github_commits ((_raw ->> 'sha'));

CREATE TABLE IF NOT EXISTS raw.rejected_github_commits (
    rejected_id BIGSERIAL PRIMARY KEY,
    source_repository TEXT NOT NULL,
    page_number INTEGER NOT NULL,
    raw_text TEXT NOT NULL,
    error_message TEXT NOT NULL,
    _ingested_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);
