-- Condition-briefing corpus: conditions → documents (one per condition + section) → chunks with embeddings.
-- Loaded by `python -m rag.ingest <corpus-dir>`; searched by rag.search (condition + section filter, cosine).

-- Canonical condition names plus the aliases the planner resolves ("CHF" → heart-failure).
create table if not exists conditions (
    id text primary key,
    name text not null,
    aliases text[] not null default '{}'
);

-- One synthetic source document: exactly one condition and one section, with its label and as-of date.
create table if not exists documents (
    doc text primary key,
    condition_id text not null references conditions (id),
    section text not null
        check (section in ('standard_of_care', 'emerging_treatments', 'key_institutions')),
    title text not null,
    source_label text not null,
    source_type text not null,
    as_of date not null
);

-- Paragraph chunks. condition_id + section are copied from the document so search is a single-table filter.
-- vector(1024) must equal EMBEDDING_DIM (voyage-4).
create table if not exists chunks (
    chunk_id text primary key,
    doc text not null references documents (doc) on delete cascade,
    ord int not null,
    condition_id text not null,
    section text not null,
    text text not null,
    embedding vector(1024) not null,
    unique (doc, ord)
);

create index if not exists chunks_embedding_hnsw on chunks using hnsw (embedding vector_cosine_ops);
create index if not exists chunks_condition_section on chunks (condition_id, section);

-- RLS on, no policies: blocks Supabase's public REST API; the postgres owner role is unaffected.
alter table conditions enable row level security;
alter table documents enable row level security;
alter table chunks enable row level security;
