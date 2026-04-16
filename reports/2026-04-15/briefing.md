# Seasonal Outlook Briefing | 2026-04-15

- Data status: `current`
- Issue target window: `2026-05` to `2026-07`
- Forecast basis: calibrated multi-model prior + climate-factor posterior adjustment

## 1. Today's Headline

- Korea M+1 temperature: upper (48%); Korea M+1 precipitation: upper (38%)
- Signal wording remains probabilistic. Deterministic wording is intentionally avoided.

## 2. Korean Peninsula Tercile Table

| Variable | Lead | Target | Lower | Normal | Upper | Dominant | Agreement |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| temperature | M+1 | 2026-05 | 19% | 33% | 48% | upper | 100% |
| temperature | M+2 | 2026-06 | 20% | 34% | 46% | upper | 100% |
| temperature | M+3 | 2026-07 | 22% | 35% | 43% | upper | 100% |
| precipitation | M+1 | 2026-05 | 27% | 36% | 38% | upper | 75% |
| precipitation | M+2 | 2026-06 | 25% | 34% | 41% | upper | 100% |
| precipitation | M+3 | 2026-07 | 23% | 33% | 44% | upper | 100% |

## 3. East Asia Probability Panels And Model Agreement

Rendered figures:

![Tercile overview](D:/WORK/Projects/Codex/seasonal_outlook/reports/2026-04-15/tercile_overview.png)

![Model agreement](D:/WORK/Projects/Codex/seasonal_outlook/reports/2026-04-15/model_agreement.png)

## 4. Recent Climate-Factor Diagnostics

- **ENSO** `neutral_to_el_nino_watch` confidence=0.78 source=[NOAA CPC ENSO](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml?_bhlid=aa53132c1acc5d24129e855461cc692e294e0d8e)
  Summary: ENSO-neutral persists in April 2026, with El Nino emergence favored into boreal summer.
- **PDO** `negative` confidence=0.66 source=[NOAA PSL PDO](https://psl.noaa.gov/pdo/)
  Summary: Negative PDO background slightly tempers warm-signal amplification over the North Pacific sector.
- **IOD/IOB** `near_neutral_with_warm_iob_tendency` confidence=0.55 source=[JMA El Nino Outlook](https://ds.data.jma.go.jp/tcc/tcc/products/elnino/outlook.html)
  Summary: IOD remains near neutral while Indian Ocean basin warmth modestly supports summer moisture transport.
- **AO/NAO** `weak_positive` confidence=0.42 source=[NOAA CPC Teleconnections](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/teleconnections.shtml)
  Summary: High-latitude circulation is not strongly locked, so AO/NAO contributes as a low-weight transitional factor.
- **Pacific-Japan Pattern** `weak_positive_projection` confidence=0.48 source=[Derived PJ Index](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-pressure-levels-monthly-means)
  Summary: A weak positive PJ projection slightly lifts near-term East Asia rainfall and warmth risk, strongest for M+1.
- **BSISO** `suppressed_then_reactivating` confidence=0.50 source=[IPRC BSISO](https://iprc.soest.hawaii.edu/users/jylee/bsiso/main.htm)
  Summary: BSISO signal is more relevant to M+1, with rapidly decreasing utility beyond the first target month.
- **Asian Monsoon Indices** `early_transition` confidence=0.46 source=[JMA Asian Monsoon Monitoring](https://ds.data.jma.go.jp/tcc/tcc/products/clisys/ASIA_TCC/monsoon_index.html)
  Summary: Monsoon transition diagnostics support near-term precipitation uplift but with modest confidence.
- **Arctic Sea Ice** `low` confidence=0.37 source=[NSIDC Sea Ice](https://nsidc.org/sea-ice-today/)
  Summary: Sea-ice anomalies are treated as a low-confidence background modifier rather than a stand-alone forecast anchor.
- **Eurasian Snow Cover** `below_normal` confidence=0.34 source=[Rutgers Global Snow Lab](https://climate.rutgers.edu/snowcover/index.php/svg/chart_vis.php?ui_set=0&ui_week=5&ui_year=2026)
  Summary: Snow-cover anomaly enters the system only as a secondary background signal.
- **Soil Moisture** `dry_bias_north_of_korea` confidence=0.40 source=[NOAA CPC Soil Moisture](https://www.cpc.ncep.noaa.gov/soilmst/sm_glb.html)
  Summary: Soil-moisture anomalies are used as a land-surface persistence term with modest positive temperature contribution.

## 5. Factor Contribution Table

| Region | Variable | Lead | Posterior Adjustment | Top Contributions |
| --- | --- | --- | ---: | --- |
| korea | temperature | M+1 | +0.034 | ENSO:+0.023, PDO:-0.007, AO/NAO:+0.005, Pacific-Japan Pattern:+0.005 |
| korea | temperature | M+2 | +0.026 | ENSO:+0.027, PDO:-0.007, Soil Moisture:+0.003, Arctic Sea Ice:+0.002 |
| korea | temperature | M+3 | +0.023 | ENSO:+0.023 |
| korea | precipitation | M+1 | +0.018 | BSISO:+0.007, Pacific-Japan Pattern:+0.006, Asian Monsoon Indices:+0.005 |
| korea | precipitation | M+2 | +0.017 | ENSO:+0.012, IOD/IOB:+0.005 |
| korea | precipitation | M+3 | +0.024 | ENSO:+0.016, IOD/IOB:+0.008 |
| east_asia | temperature | M+1 | +0.038 | ENSO:+0.027, PDO:-0.010, AO/NAO:+0.006, Pacific-Japan Pattern:+0.006 |
| east_asia | temperature | M+2 | +0.028 | ENSO:+0.031, PDO:-0.010, Soil Moisture:+0.004, Arctic Sea Ice:+0.003 |
| east_asia | temperature | M+3 | +0.017 | ENSO:+0.027, PDO:-0.010 |
| east_asia | precipitation | M+1 | +0.023 | BSISO:+0.010, Pacific-Japan Pattern:+0.007, Asian Monsoon Indices:+0.005 |
| east_asia | precipitation | M+2 | +0.014 | ENSO:+0.008, IOD/IOB:+0.007 |
| east_asia | precipitation | M+3 | +0.025 | ENSO:+0.016, IOD/IOB:+0.010 |

## 6. Uncertainty And Counter-Scenario

- temperature: primary signal is `upper` for East Asia M+1, but `lower` remains plausible if fast factors weaken or reverse.
- precipitation: primary signal is `upper` for East Asia M+1, but `lower` remains plausible if fast factors weaken or reverse.

## 7. Validation And System Change Log

- Fixed evaluation contract: Korea-centered RPSS, BSS, reliability, ACC, probability jump penalty.
- Promotion rule: composite score improvement >= 2% and neither Korea temperature nor precipitation BSS may degrade by more than 5%.
- Warnings: none
