-- Another Me database bootstrap script for PostgreSQL 16 + pgvector.
--
-- Usage:
--   /opt/homebrew/opt/postgresql@16/bin/psql -d postgres -f backend/sql/init_database.sql
--
-- Notes:
--   - This script is intended for a fresh local database.
--   - It uses psql meta-commands such as \gexec and \connect.
--   - Alembic is marked at revision 202605030004 because schema-changing
--     migrations currently stop there; later stages use existing JSONB fields.

\set ON_ERROR_STOP on

SELECT 'CREATE DATABASE vibe_writer'
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = 'vibe_writer'
)\gexec

\connect vibe_writer

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  email varchar(255) UNIQUE,
  display_name varchar(120),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS style_categories (
  id uuid PRIMARY KEY,
  user_id uuid REFERENCES users(id) ON DELETE SET NULL,
  name varchar(120) NOT NULL,
  description text,
  writing_type_hint varchar(40) NOT NULL DEFAULT '混合风格',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_style_categories_created_at
  ON style_categories (created_at);

CREATE TABLE IF NOT EXISTS source_articles (
  id uuid PRIMARY KEY,
  style_category_id uuid NOT NULL REFERENCES style_categories(id) ON DELETE CASCADE,
  title varchar(255) NOT NULL,
  source_type varchar(20) NOT NULL DEFAULT 'txt',
  original_filename varchar(255) NOT NULL,
  raw_text text NOT NULL,
  cleaned_text text NOT NULL,
  word_count integer NOT NULL DEFAULT 0,
  status varchar(40) NOT NULL DEFAULT 'completed',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_source_articles_style_category_id
  ON source_articles (style_category_id);

CREATE TABLE IF NOT EXISTS article_chunks (
  id uuid PRIMARY KEY,
  source_article_id uuid NOT NULL REFERENCES source_articles(id) ON DELETE CASCADE,
  style_category_id uuid NOT NULL REFERENCES style_categories(id) ON DELETE CASCADE,
  chunk_index integer NOT NULL,
  content text NOT NULL,
  token_count integer DEFAULT 0,
  embedding vector(1536),
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_article_chunks_source_article_id
  ON article_chunks (source_article_id);

CREATE INDEX IF NOT EXISTS ix_article_chunks_style_category_id
  ON article_chunks (style_category_id);

CREATE INDEX IF NOT EXISTS ix_article_chunks_embedding_cosine
  ON article_chunks USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS style_profiles (
  id uuid PRIMARY KEY,
  style_category_id uuid NOT NULL UNIQUE REFERENCES style_categories(id) ON DELETE CASCADE,
  profile_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  summary text,
  sentence_style text,
  structure_style text,
  rhetoric_style text,
  imagery_style text,
  vocabulary_style text,
  tone_style text,
  argument_style text,
  opening_style text,
  ending_style text,
  do_rules text,
  dont_rules text,
  prompt_instruction text,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS generation_tasks (
  id uuid PRIMARY KEY,
  style_category_id uuid NOT NULL REFERENCES style_categories(id) ON DELETE CASCADE,
  prompt text NOT NULL,
  status varchar(40) NOT NULL DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_generation_tasks_style_category_id
  ON generation_tasks (style_category_id);

CREATE TABLE IF NOT EXISTS generated_outputs (
  id uuid PRIMARY KEY,
  generation_task_id uuid NOT NULL REFERENCES generation_tasks(id) ON DELETE CASCADE,
  content text NOT NULL,
  metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_generated_outputs_generation_task_id
  ON generated_outputs (generation_task_id);

CREATE TABLE IF NOT EXISTS alembic_version (
  version_num varchar(32) NOT NULL PRIMARY KEY
);

INSERT INTO alembic_version (version_num)
VALUES ('202605030004')
ON CONFLICT (version_num) DO NOTHING;
