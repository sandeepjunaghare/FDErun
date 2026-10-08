-- Memory tables, shaped for pane A's api/memory/ (which owns reads and writes).

-- A conversation, scoped to one user.
create table if not exists sessions (
    session_id text primary key,
    user_id text not null,
    created_at timestamptz not null default now()
);

-- Session turns in order; citations are the chunk ids the turn relied on. User scope comes via sessions.
create table if not exists turns (
    id bigserial primary key,
    session_id text not null references sessions (session_id) on delete cascade,
    role text not null,
    content text not null,
    citations text[] not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists turns_session on turns (session_id, id);

-- Persistent per-user memory: conditions briefed recently, newest first.
create table if not exists recent_conditions (
    user_id text not null,
    condition_id text not null references conditions (id),
    viewed_at timestamptz not null default now(),
    primary key (user_id, condition_id)
);

create index if not exists recent_conditions_user on recent_conditions (user_id, viewed_at desc);

-- RLS on, no policies: blocks Supabase's public REST API; the postgres owner role is unaffected.
alter table sessions enable row level security;
alter table turns enable row level security;
alter table recent_conditions enable row level security;
