# Supabase local setup

Apply the migration, then the deterministic seed:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 \
  -f supabase/migrations/202606200001_f04_schema.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f supabase/seed.sql
```

Both files are idempotent. `price_catalog` uses `STANDARD` for non-tiered rows because PostgreSQL
primary-key columns cannot be null. Consumers select the newest row whose `valid_from` is not later
than the pricing date:

```sql
select *
from public.price_catalog
where component = $1
  and tier = $2
  and valid_from <= $3
order by valid_from desc
limit 1;
```

The seed performs no network requests. Live PVGIS and dynamic-tariff data are optional cache writers,
not prerequisites for the demo.
