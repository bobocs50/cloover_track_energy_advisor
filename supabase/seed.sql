-- F04 deterministic offline seed.
-- Demo PLZ values are labelled authoring choices, not official measurements:
-- 10115 Berlin is the primary demo; 80331 Munich supports the Bavaria/Denkmal path.

insert into public.price_catalog
    (component, tier, unit, unit_price, source, valid_from)
values
    ('pv_per_kwp', 'SMALL', 'EUR/kWp', 1450.0, 'Market quote average; 0% VAT (§12)', date '2026-06-20'),
    ('pv_per_kwp', 'LARGE', 'EUR/kWp', 1300.0, 'Market quote average; economies of scale (§12)', date '2026-06-20'),
    ('battery_per_kwh', 'STANDARD', 'EUR/kWh', 700.0, 'Usable-kWh market average (§12)', date '2026-06-20'),
    ('heatpump_fixed', 'STANDARD', 'EUR', 22000.0, 'Air-source heat pump incl. install; market range 18–30k (§12)', date '2026-06-20'),
    ('wallbox_fixed', 'STANDARD', 'EUR', 1200.0, 'Wallbox incl. installation market average (§12)', date '2026-06-20'),
    ('oil_per_litre', 'STANDARD', 'EUR/l', 1.10, 'Destatis heating-oil index (§12)', date '2026-06-20'),
    ('gas_per_kwh', 'STANDARD', 'EUR/kWh', 0.115, 'Destatis household gas index (§12)', date '2026-06-20'),
    ('petrol_per_litre', 'STANDARD', 'EUR/l', 1.85, 'Destatis / ADAC fuel reference (§12)', date '2026-06-20'),
    ('diesel_per_litre', 'STANDARD', 'EUR/l', 1.75, 'Destatis / ADAC fuel reference (§12)', date '2026-06-20'),
    ('retail_per_kwh', 'STANDARD', 'EUR/kWh', 0.37, 'Destatis / BNetzA household electricity reference (§12)', date '2026-06-20'),
    ('feedin_per_kwh', 'STANDARD', 'EUR/kWh', 0.0778, 'Bundesnetzagentur EEG ≤10 kWp (§12)', date '2026-06-20'),
    ('public_charge_per_kwh', 'STANDARD', 'EUR/kWh', 0.45, 'Public CPO average; L4 Case B baseline (§12)', date '2026-06-20')
on conflict (component, tier, valid_from) do update set
    unit = excluded.unit,
    unit_price = excluded.unit_price,
    source = excluded.source;

insert into public.reference_plz
    (plz, lat, lon, specific_yield, retail_price, grid_fee, climate_zone, mastr_count)
values
    ('10115', 52.5323, 13.3846, 980.0, 0.37, 0.0, 'DE-4', 47),
    ('80331', 48.1372, 11.5756, 980.0, 0.37, 0.0, 'DE-5', 63)
on conflict (plz) do update set
    lat = excluded.lat,
    lon = excluded.lon,
    specific_yield = excluded.specific_yield,
    retail_price = excluded.retail_price,
    grid_fee = excluded.grid_fee,
    climate_zone = excluded.climate_zone,
    mastr_count = excluded.mastr_count;

insert into public.denkmal_seed (plz, flag)
values
    ('10115', false),
    ('80331', true)
on conflict (plz) do update set flag = excluded.flag;

insert into public.mastr_seed (plz, count)
values
    ('10115', 47),
    ('80331', 63)
on conflict (plz) do update set count = excluded.count;
