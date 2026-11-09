# Data catalogue

Two years of GB data, 1 October 2024 to 30 September 2026 (UK time). Each dataset is in this folder as Parquet and as CSV, with identical content.

- All timestamps are UTC (ISO 8601). `period_start` is the start of the period a value applies to; half-hours follow GB settlement periods.
- Forecast datasets have `issued_at` (when the provider issued the forecast) and `received_at` (when it landed in our database, including later backfills; empty where the source doesn't record it).

## imbalance_price

GB System Imbalance Price (SIP) for each half-hour settlement period.

35,039 rows; `period_start` from 2024-09-30 23:00:00+00:00 to 2026-09-30 22:30:00+00:00.

| Column              | Meaning                       |
| ------------------- | ----------------------------- |
| `period_start`      | Start of the half-hour        |
| `price_gbp_per_mwh` | System Imbalance Price, £/MWh |

## demand_forecast_elexon

NESO's National Demand Forecast (NDF), published via Elexon, every publication, up to about 45 hours ahead. It is the demand to be met by transmission-metered generation: it includes transmission losses and excludes interconnector exports, power stations' own use and pumped storage pumping. Embedded wind and solar (see wind_solar_forecast_embedded) aren't metered by NESO, so their output shows up as lower demand.

2,055,958 rows; `period_start` from 2024-09-27 23:30:00+00:00 to 2026-10-02 03:30:00+00:00.

| Column         | Meaning                                    |
| -------------- | ------------------------------------------ |
| `issued_at`    | When it was published                      |
| `received_at`  | When it landed in our database             |
| `period_start` | Start of the half-hour the forecast is for |
| `demand_mw`    | Forecast demand, MW                        |

## margin_daily

NESO Operational Planning Margin Requirement (OPMR) forecasts: one row per publication and day, 2 to 3 days ahead, daily values. NESO publishes once a day but doesn't record the time of day, so `issued_at` is the publication date and `received_at` is empty.

1,458 rows; `day` from 2024-09-30 to 2026-10-03.

| Column                                      | Meaning                                                                                                       |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `issued_at`                                 | Publication date (as midnight UK time); the time of day isn't recorded                                        |
| `received_at`                               | Not available for this source                                                                                 |
| `day`                                       | UK date the forecast is for                                                                                   |
| `peak_demand_forecast_mw`                   | Forecast maximum demand on that day, MW                                                                       |
| `minimum_demand_forecast_mw`                | Forecast minimum demand on that day, MW                                                                       |
| `generator_availability_mw`                 | Generation forecast to be available, MW                                                                       |
| `generation_availability_margin_mw`         | Generation available after meeting demand, MW                                                                 |
| `operating_margin_requirement_mw`           | Generation NESO needs above the demand forecast to meet its reserve requirement (the OPMR), MW                |
| `national_surplus_mw`                       | Generation minus demand minus the OPMR, MW: positive means slack, negative means tight                        |
| `max_interconnector_import_mw`              | Maximum flow the interconnectors can bring into GB, MW                                                        |
| `max_interconnector_export_mw`              | Maximum flow the interconnectors can take out of GB, MW                                                       |
| `operating_reserve_from_interconnectors_mw` | Part of the operating reserve provided by interconnectors, MW                                                 |
| `constrained_plant_mw`                      | Generation that can't be used because of network constraints, MW                                              |
| `high_frequency_response_requirement_mw`    | High-frequency response NESO needs at minimum demand, MW                                                      |
| `negative_reserve_mw`                       | Reserve for reducing generation: negative regulating reserve plus the high-frequency response requirement, MW |

## margin_half_hourly

Loss of load probability and de-rated margin per half-hour, via Elexon, every publication. Each publication covers up to about 41 hours ahead. Only available from 9 October 2025.

961,662 rows; `period_start` from 2025-10-09 16:00:00+00:00 to 2026-10-02 03:30:00+00:00.

| Column                     | Meaning                                                                                                                                       |
| -------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------- |
| `issued_at`                | When it was published                                                                                                                         |
| `received_at`              | When it landed in our database                                                                                                                |
| `period_start`             | Start of the half-hour                                                                                                                        |
| `loss_of_load_probability` | Probability of a shortfall of generation against demand in that half-hour, 0–1                                                                |
| `derated_margin_mw`        | Forecast available generation minus the capacity requirement (which includes interconnector exports and headroom for managing the system), MW |

## wind_forecast_elexon

Wind generation forecast (WINDFOR) published via Elexon, every publication, hourly values. It covers wind farms that NESO can see and that have operational metering, so not the embedded farms in wind_solar_forecast_embedded. Each publication covers roughly the previous day up to about 66 hours ahead.

422,741 rows; `period_start` from 2024-09-27 20:00:00+00:00 to 2026-10-02 20:00:00+00:00.

| Column         | Meaning                               |
| -------------- | ------------------------------------- |
| `issued_at`    | When it was published                 |
| `received_at`  | When it landed in our database        |
| `period_start` | Start of the hour the forecast is for |
| `wind_mw`      | Forecast wind generation, MW          |

## wind_solar_forecast_embedded

NESO forecast of wind and solar generation from embedded farms: those without transmission metering, connected to the distribution networks and not visible to NESO. Their output isn't measured, so NESO estimates it with a model. Every forecast produced, up to 72 hours ahead. NESO does not publish a receipt time, so `received_at` is empty.

2,509,386 rows; `period_start` from 2024-09-27 23:00:00+00:00 to 2026-10-03 22:30:00+00:00.

| Column                       | Meaning                                                                                                                         |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `issued_at`                  | When NESO produced the forecast. NESO's own timestamp was in UK time until June 2026 despite a UTC label; converted to UTC here |
| `received_at`                | Not available for this source                                                                                                   |
| `period_start`               | Start of the half-hour the forecast is for                                                                                      |
| `embedded_wind_mw`           | Forecast embedded wind generation, MW                                                                                           |
| `embedded_solar_mw`          | Forecast embedded solar generation, MW                                                                                          |
| `embedded_wind_capacity_mw`  | NESO's estimate of installed embedded wind capacity, MW                                                                         |
| `embedded_solar_capacity_mw` | NESO's estimate of installed embedded solar capacity, MW                                                                        |

## Sources and licences

- `demand_forecast_elexon`, `imbalance_price`, `margin_half_hourly`, `wind_forecast_elexon`: Contains BMRS data © Elexon Limited copyright and database right 2024–2026. Licence: https://www.elexon.co.uk/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/
- `margin_daily`, `wind_solar_forecast_embedded`: Supported by National Energy SO Open Data. Licence: https://www.neso.energy/data-portal/neso-open-licence
