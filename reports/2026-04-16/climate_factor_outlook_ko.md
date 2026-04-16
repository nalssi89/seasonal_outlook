# 기후인자 기반 한반도 3개월 전망 | 2026-04-16

- 발행 기준일: `2026-04-16`
- 전망 기간: `2026-05` ~ `2026-07`
- 산출물 성격: 기존 브리핑과 분리한 기후인자 전용 보고서

## 1. 개요

기존 다중모델 3분위 확률을 앵커로 두고, NOAA PSL·CPC·JMA·WMO의 최신 기후인자 현황과 동아시아 teleconnection 문헌을 결합해 한반도 영향을 보수적으로 정리한 별도 슬라이드 보고서입니다.

## 2. 방법

- 3분위 확률의 수치 앵커는 기존 calibrated multi-model prior를 사용하고, 기후인자는 capped posterior adjustment로만 반영했습니다.
- 기후인자는 implementation plan의 freshness 규칙을 따라 fresh / usable_with_lag / stale을 구분했고, lagged factor는 배경장 해석에만 사용했습니다.
- 문헌은 동아시아·한반도에 직접 연결되는 ENSO, 인도양, AO, QBO, PDO 위주로 엄선했고, 근거가 약한 경우에는 uncertain 또는 weak로 낮춰 표현했습니다.

## 3. 한반도 3분위 전망

- 기온 요약: 기온은 M+1~M+3 모두 상위 3분위 우세가 유지됩니다. ENSO 중립 이행기에도 동아시아 대규모 온난 배경과 한반도 주변 해역의 warm boundary condition이 남아 있어, 평균기온 자체가 평년보다 높을 가능성이 상대적으로 큽니다.
- 강수 요약: 강수는 세 달 모두 상위 3분위가 가장 높지만, M+1은 normal과의 차이가 작고 M+2~M+3도 강한 wet call로 보기에는 근거가 제한적입니다. 따라서 '평년과 비슷하거나 다소 많을 가능성'으로 읽는 것이 가장 객관적입니다.

| 변수 | 리드 | 대상월 | 하위 | 평년 | 상위 | 우세 범주 | 모델 합의도 |
| --- | --- | --- | ---: | ---: | ---: | --- | ---: |
| 기온 | M+1 | 2026-05 | 21.2% | 33.9% | 44.9% | upper | 100% |
| 기온 | M+2 | 2026-06 | 22.2% | 34.9% | 42.9% | upper | 100% |
| 기온 | M+3 | 2026-07 | 23.6% | 35.3% | 41.1% | upper | 100% |
| 강수 | M+1 | 2026-05 | 28.1% | 36.1% | 35.8% | normal | 75% |
| 강수 | M+2 | 2026-06 | 26.1% | 34.5% | 39.4% | upper | 100% |
| 강수 | M+3 | 2026-07 | 24.7% | 33.5% | 41.8% | upper | 100% |

## 4. 핵심 기후인자 현황

| 기후인자 | 등급 | 역할 | 최신값 | 최신월 | 최신성 | M+1 T | M+1 P | M+2 T | M+2 P | M+3 T | M+3 P |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| ENSO / Niño 3.4 | A | 핵심 | -0.06 °C | 2026-03 | fresh | 상위 가중 | 중립~약한 상위 | 상위 가중 | 약한 상위 | 상위 가중 | 약한 상위 |
| Western Pacific pattern | A | 핵심 | -2.13 standardized | 2026-03 | fresh | 약한 상위 | 불확실 | 중립~약한 상위 | 약한 상위 | 중립 | 불확실 |
| Indian Ocean Basin / IOBW | B | 보조 | -0.02 °C | 2026-03 | fresh | 중립 | 중립 | 중립~약한 상위 | 약한 상위 | 약한 상위 | 약한 상위 |
| Arctic Oscillation | B | 보조 | +2.04 standardized | 2026-03 | fresh | 약한 상위 | 불확실 | 중립 | 불확실 | 중립 | 없음 |
| QBO 30 hPa | B | 조건부 | -23.13 m/s | 2026-02 | usable_with_lag | 없음 | 불확실 | 없음 | 약한 상위 | 없음 | 약한 상위 |
| Pacific Decadal Oscillation | C | 배경장 | -1.22 °C | 2025-12 | usable_with_lag | 약한 하향 | 없음 | 약한 하향 | 없음 | 약한 하향 | 없음 |

## 5. 인자별 해석

### ENSO / Niño 3.4

- 현재 상태: 2026년 3월 Niño3.4는 -0.06°C로 중립권이며, JMA SOI는 2026년 1~3월 +0.9, +1.0, +1.0으로 아직 약한 La Niña 잔재를 시사합니다.
- 동아시아/한반도 해석: ENSO의 직접 신호는 약해졌지만, 봄 장벽 구간에서도 여름철 열대 태평양이 warm 쪽으로 기울 경우 서북태평양 저층 순환과 동아시아 여름 몬순 강수대가 다시 조직될 수 있습니다. 따라서 이번 발행월에서는 기온 쪽 신호를 더 크게, 강수는 보조적으로만 반영했습니다.
- 신뢰도: 높음
- 최신성 판정: `fresh`
- 참고 문헌/기관 자료:
  - [NOAA CPC ENSO Diagnostic Discussion (2026-04-10)](https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso_advisory/ensodisc.shtml)
  - [JMA El Niño Monitoring Indices](https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/)
  - [Nature Communications 2024, Why East Asian monsoon anomalies are more robust in post El Niño than in post La Niña summers](https://www.nature.com/articles/s41467-024-51885-7)
  - [Xie et al. 2009, Indian Ocean capacitor effect on Indo-western Pacific climate during the summer following El Niño](https://doi.org/10.1175/2008JCLI2544.1)

### Western Pacific pattern

- 현재 상태: CPC tele_index.nh 기준 2026년 3월 WP는 -2.13으로 강한 음의 위상이었고, 같은 달 PNA -1.99, EP/NP -1.17, NAO +2.42와 함께 중위도 파동열차의 평년 이탈이 컸습니다.
- 동아시아/한반도 해석: WP는 ENSO와 동아시아 순환을 연결하는 북태평양-서북태평양 쪽 중위도 응답을 보여주는 핵심 모드입니다. 현재처럼 음의 WP가 강할 때는 필리핀해-일본 남쪽-북태평양 쪽 기압장 재배치 가능성이 커지므로, 5월과 6월 강수대 위치 변동성 설명에 중요합니다.
- 신뢰도: 중간
- 최신성 판정: `fresh`
- 참고 문헌/기관 자료:
  - [CPC tele_index.nh](https://ftp.cpc.ncep.noaa.gov/wd52dg/data/indices/tele_index.nh)
  - [CPC Northern Hemisphere Teleconnection Patterns](https://www.cpc.ncep.noaa.gov/data/teledoc/telecontents.shtml)
  - [JGR Atmospheres 2023, Teleconnection pathways associated with the western Pacific pattern and East Asia](https://agupubs.onlinelibrary.wiley.com/doi/full/10.1029/2022JD037905)

### Indian Ocean Basin / IOBW

- 현재 상태: JMA IOBW deviation은 2026년 1월 -0.24°C, 2월 -0.14°C, 3월 -0.02°C로 거의 중립에 가깝고, WMO는 early 2026 IOD가 near-average였다고 진단했습니다.
- 동아시아/한반도 해석: 인도양 분지 또는 positive IOD background는 서북태평양 대기-해양 capacitor를 통해 동아시아 여름 강수대와 WNPSH를 조절할 수 있습니다. 다만 현재 관측값은 중립에 가까워 M+2~M+3 강수에만 약한 상향 보정으로 제한했습니다.
- 신뢰도: 중간
- 최신성 판정: `fresh`
- 참고 문헌/기관 자료:
  - [WMO Global Seasonal Climate Update for April-May-June 2026 (2026-03-23)](https://wmo.int/media/update/global-seasonal-climate-update-april-may-june-2026)
  - [JMA El Niño Monitoring Indices / IOBW deviation](https://ds.data.jma.go.jp/tcc/tcc/products/elnino/index/)
  - [Yang et al. 2007, Impact of the Indian Ocean SST basin mode on the Asian summer monsoon](https://doi.org/10.1029/2006GL028571)
  - [Frontiers in Climate 2022, Drivers and characteristics of the Indo-western Pacific Ocean capacitor](https://www.frontiersin.org/journals/climate/articles/10.3389/fclim.2022.1014138/full)

### Arctic Oscillation

- 현재 상태: CPC monthly AO index는 2026년 3월 +2.04로 강한 양의 위상이었지만, warm-season persistence는 높지 않아 lead가 늘수록 영향 가중치를 낮췄습니다.
- 동아시아/한반도 해석: 양의 AO가 늦겨울~초봄에 강할 때 동아시아 제트와 초여름 강수대 위치를 바꾸며 5월 이후 온도·강수 배경을 일부 조절할 수 있다는 연구가 있습니다. 하지만 여름철 직접 예측인자로 쓰기에는 불안정하므로 M+1 보조인자로만 취급했습니다.
- 신뢰도: 중간 이하
- 최신성 판정: `fresh`
- 참고 문헌/기관 자료:
  - [CPC Arctic Oscillation page](https://www.cpc.ncep.noaa.gov/products/precip/CWlink/daily_ao_index/new.ao.shtml)
  - [Chen et al. 2017 review, Impact of Arctic Oscillation on the East Asian climate](https://doi.org/10.1016/j.earscirev.2016.10.014)
  - [Climate Research 2019, Linkage between the Arctic Oscillation and East Asian summer climate](https://www.int-res.com/articles/cr_oa/c078p237.pdf)

### QBO 30 hPa

- 현재 상태: NOAA PSL 30 hPa QBO는 2026년 2월 -23.13 m/s로 강한 easterly phase입니다.
- 동아시아/한반도 해석: easterly QBO는 MJO와 아시아 몬순 순환을 변조해 동중국·한반도 주변 초여름 강수 변동성을 키울 수 있지만, ENSO와 MJO 위상에 따라 신호가 달라집니다. 그래서 M+2 강수의 조건부 상향 요인으로만 사용했습니다.
- 신뢰도: 낮음
- 최신성 판정: `usable_with_lag`
- 참고 문헌/기관 자료:
  - [NOAA PSL QBO page](https://psl.noaa.gov/data/timeseries/month/QBO/)
  - [ACP 2023, Modulation of the intraseasonal variability in early summer precipitation in eastern China by the Quasi-Biennial Oscillation and the Madden-Julian Oscillation](https://acp.copernicus.org/articles/23/14903/2023/acp-23-14903-2023.html)
  - [ACP 2023, Summertime ozone pollution in China affected by stratospheric quasi-biennial oscillation](https://acp.copernicus.org/articles/23/1533/2023/acp-23-1533-2023.html)

### Pacific Decadal Oscillation

- 현재 상태: NOAA PSL PDO monthly feed의 최신 유효값은 2025년 12월 -1.22로 음의 위상이 유지되고 있으나, 본 보고서 발행시점 대비 4개월 지연되어 배경장 설명에만 사용했습니다.
- 동아시아/한반도 해석: PDO는 동아시아 여름철 계절예측에서 직접 인자라기보다 북태평양 배경장과 ENSO teleconnection 효율을 조절하는 decadal modulator에 가깝습니다. 이번 호에서는 warm signal을 뒤집는 인자가 아니라 고온 증폭을 다소 완화하는 배경 요인으로만 해석했습니다.
- 신뢰도: 낮음
- 최신성 판정: `usable_with_lag`
- 참고 문헌/기관 자료:
  - [NOAA PSL PDO page](https://psl.noaa.gov/data/timeseries/month/PDO/)
  - [Newman et al. 2016, The Pacific Decadal Oscillation, Revisited](https://doi.org/10.1175/JCLI-D-15-0508.1)
  - [Scientific Reports 2016, The Pacific Ocean variation pattern and East Asia summer monsoon rainfall](https://www.nature.com/articles/srep32725)

## 6. 빠른 인자와 한계

- MJO, PJ, BSISO, 아시아 몬순 전이 신호는 PSL 핵심 지수보다 예측 수명이 짧지만 2~6주 리드에서는 더 중요할 수 있으므로, 실시간 운영에서는 CPC MJO update와 OLR·850hPa wind anomaly를 반드시 함께 확인해야 합니다.
- PMM은 ENSO 발달 전조로 중요하지만 현재 버전 파이프라인에는 안정적인 공개 최신 monthly ingest를 아직 넣지 않았기 때문에, 보고서 서술에서만 보조 설명으로 유지했습니다.
- 강수는 기온보다 사건성·계절내 변동성이 커서, 상위 확률이 가장 높더라도 강한 wet call로 단정하지 않았습니다.
- PDO처럼 지연된 지수는 배경장 설명에만 사용했고, 이번 호 확률의 직접 앵커로 쓰지 않았습니다.

