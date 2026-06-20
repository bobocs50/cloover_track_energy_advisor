-- F04: offline-safe Supabase/Postgres storage for reference data and advisor output.
-- This migration is intentionally re-runnable.

create extension if not exists pgcrypto;

create table if not exists public.reference_plz (
    plz text primary key,
    lat double precision not null,
    lon double precision not null,
    specific_yield numeric not null check (specific_yield > 0),
    retail_price numeric not null check (retail_price >= 0),
    grid_fee numeric not null check (grid_fee >= 0),
    climate_zone text not null,
    mastr_count integer check (mastr_count >= 0)
);

create table if not exists public.price_catalog (
    component text not null,
    -- PostgreSQL primary-key columns cannot be null. STANDARD represents the
    -- non-tiered rows described as "—" in the product specification.
    tier text not null default 'STANDARD',
    unit text not null,
    unit_price numeric not null check (unit_price >= 0),
    source text not null check (length(trim(source)) > 0),
    valid_from date not null,
    primary key (component, tier, valid_from)
);

create index if not exists price_catalog_lookup_idx
    on public.price_catalog (component, tier, valid_from desc);

create table if not exists public.cache_pvgis (
    lat double precision not null,
    lon double precision not null,
    tilt double precision not null,
    azimuth double precision not null,
    kwp numeric not null check (kwp > 0),
    payload_json jsonb not null,
    fetched_at timestamptz not null default now(),
    primary key (lat, lon, tilt, azimuth, kwp)
);

create table if not exists public.cache_dynprice (
    market_area text not null,
    day date not null,
    payload_json jsonb not null,
    fetched_at timestamptz not null default now(),
    primary key (market_area, day)
);

create table if not exists public.advise_run (
    id uuid primary key default gen_random_uuid(),
    household_json jsonb not null,
    options_json jsonb not null,
    recommendation_json jsonb not null,
    created_at timestamptz not null default now()
);

create table if not exists public.proposal (
    id uuid primary key default gen_random_uuid(),
    advise_run_id uuid not null references public.advise_run(id) on delete cascade,
    copy_md text not null,
    created_at timestamptz not null default now()
);

create index if not exists proposal_advise_run_idx
    on public.proposal (advise_run_id);

create table if not exists public.denkmal_seed (
    plz text primary key,
    flag boolean not null
);

create table if not exists public.mastr_seed (
    plz text primary key,
    count integer not null check (count >= 0)
);
