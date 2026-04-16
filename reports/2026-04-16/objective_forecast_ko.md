# 한반도 객관지수예보

- 발행일: `2026-04-16`
- 영속 산출물 정책: `json`과 `md`만 사용
- 독립성 원칙: 이 보고서는 핵심기후인자와 관측 기반 객관예측만 사용하며, 동적모델 prior는 사용하지 않음
- 학습 모델 요약은 같은 날짜의 `objective_model_training_ko.md`에 별도 저장

## 확률표

| 변수 | 리드 | 목표월 | 낮음 | 비슷 | 높음 | 대표기호 |
| --- | --- | --- | --- | --- | --- | --- |
| 강수 | M+1 | 2026-05 | 0.314 | 0.379 | 0.307 | 0 |
| 강수 | M+2 | 2026-06 | 0.555 | 0.326 | 0.119 | - |
| 강수 | M+3 | 2026-07 | 0.236 | 0.405 | 0.359 | + |
| 기온 | M+1 | 2026-05 | 0.119 | 0.208 | 0.673 | + |
| 기온 | M+2 | 2026-06 | 0.175 | 0.397 | 0.427 | + |
| 기온 | M+3 | 2026-07 | 0.133 | 0.339 | 0.528 | + |

## 상위 설명 변수

### 강수 M+1

- 앙상블 가중치: LightGBM=1.00
- 상위 설명 변수: Global Mean Land/Ocean Temperature Index 3개월 평균(+1.525), MEI V2 3개월 평균(-1.097), CPC POL 3개월 평균(-0.826), SH Sea-Ice Extent 3개월 평균(+0.758), 관측 기온 1개월 전(+0.681)

### 강수 M+2

- 앙상블 가중치: 유사사례 kNN=1.00
- 상위 설명 변수: SH Sea-Ice Extent 1개월 전(+0.696), Global Mean Land/Ocean Temperature Index 1개월 전(+0.634), Global Mean Land/Ocean Temperature Index 최신 가용값(+0.526), CPC ExplainedVariance 최신 가용값(+0.525), 관측 기온 최신 가용값(+0.492)

### 강수 M+3

- 앙상블 가중치: 유사사례 kNN=1.00
- 상위 설명 변수: 관측 강수 3개월 평균(+0.906), SH Sea-Ice Extent 3개월 평균(+0.885), SOI* 3개월 평균(+0.884), SH Sea-Ice Extent 1개월 전(+0.612), MEI V2 최신 가용값(-0.586)

### 기온 M+1

- 앙상블 가중치: 유사사례 kNN=0.40, LightGBM=0.59, 소프트맥스 회귀=0.01
- 상위 설명 변수: Global Mean Land/Ocean Temperature Index 3개월 평균(+1.803), SH Sea-Ice Extent 3개월 평균(-1.135), CPC POL 3개월 평균(+1.033), 관측 기온 1개월 전(+0.869), SOI* 1개월 전(-0.798)

### 기온 M+2

- 앙상블 가중치: 유사사례 kNN=0.64, LightGBM=0.35, 소프트맥스 회귀=0.02
- 상위 설명 변수: Global Mean Land/Ocean Temperature Index 3개월 평균(+1.340), SOI* 3개월 평균(+1.057), SOI* 최신 가용값(-1.007), Global Mean Land/Ocean Temperature Index 1개월 전(+0.977), Global Mean Land/Ocean Temperature Index 최신 가용값(+0.905)

### 기온 M+3

- 앙상블 가중치: 유사사례 kNN=0.14, LightGBM=0.86
- 상위 설명 변수: Global Mean Land/Ocean Temperature Index 3개월 평균(+1.798), Global Mean Land/Ocean Temperature Index 최신 가용값(+0.932), Global Mean Land/Ocean Temperature Index 1개월 전(+0.908), AO 최신 가용값(+0.594), 관측 기온 3개월 평균(-0.587)

## 적용 방법

- 목표변수: 한반도 월평균기온과 강수량을 `-, 0, +` 3분위 기호로 예측합니다.
- 예측 단위: 기준월 `M`에서 `M+1`, `M+2`, `M+3`을 각각 별도 목표월로 둡니다.
- 참값: `inputs/observed_symbols/남한_월별_실황_기호화.md`의 관측 실황을 읽어 학습용 정답으로 사용합니다.
- 기후인자 입력: PSL 대표 시계열, `tele_index.nh` 보완 지수, 그리고 최근 한반도 관측 지속성 항을 사용합니다.
- 입력 시차 규칙: 대부분의 지수는 `M-1`, 지연 갱신 지수(예: `ONI`, `QBO`)는 `M-2`까지만 사용합니다.
- 특징량: 각 지수의 최신 가용값(`m0`), 1개월 전(`m1`), 3개월 평균(`roll3`), 1개월 변화량(`delta1`), 발행월/목표월 계절성(sin, cos)을 함께 만듭니다.
- 후보모형: 기후평년, 유사사례 kNN, 다항 로지스틱 회귀, LightGBM을 병렬로 학습합니다.
- 검증과 앙상블: 변수×리드별 expanding-window 백테스트에서 `RPSS > 0`인 모형만 남기고 softmax 가중으로 앙상블합니다.
- 대표기호 결정: 최종 확률에서 `P(+) - P(-)`가 `+0.08` 이상이면 `+`, `-0.08` 이하이면 `-`, 그 사이는 `0`으로 둡니다.
- 상위 설명 변수: 현재 사례에서 로지스틱 회귀 계열의 `+` 대 `-` 기여 차이를 기준으로 설명용 상위 항목을 제시합니다.
- 해석용 스냅샷 인자: 아래 스냅샷 인자는 현재 버전에서 확률 학습 입력이 아니라, 예보 해석을 돕는 별도 참고 정보입니다.

## 해석용 스냅샷 인자

- `enso` 신호=1 신뢰도=0.78 출처=NOAA CPC ENSO (ENSO-neutral persists in April 2026, with El Nino emergence favored into boreal summer.)
- `pdo` 신호=-1 신뢰도=0.66 출처=NOAA PSL PDO (Negative PDO background slightly tempers warm-signal amplification over the North Pacific sector.)
- `iod_iob` 신호=1 신뢰도=0.55 출처=JMA El Nino Outlook (IOD remains near neutral while Indian Ocean basin warmth modestly supports summer moisture transport.)
- `ao_nao` 신호=1 신뢰도=0.42 출처=NOAA CPC Teleconnections (High-latitude circulation is not strongly locked, so AO/NAO contributes as a low-weight transitional factor.)
- `pj` 신호=1 신뢰도=0.48 출처=Derived PJ Index (A weak positive PJ projection slightly lifts near-term East Asia rainfall and warmth risk, strongest for M+1.)
- `bsiso` 신호=1 신뢰도=0.50 출처=IPRC BSISO (BSISO signal is more relevant to M+1, with rapidly decreasing utility beyond the first target month.)
- `monsoon` 신호=1 신뢰도=0.46 출처=JMA Asian Monsoon Monitoring (Monsoon transition diagnostics support near-term precipitation uplift but with modest confidence.)
- `sea_ice` 신호=1 신뢰도=0.37 출처=NSIDC Sea Ice (Sea-ice anomalies are treated as a low-confidence background modifier rather than a stand-alone forecast anchor.)
- `snow_cover` 신호=1 신뢰도=0.34 출처=Rutgers Global Snow Lab (Snow-cover anomaly enters the system only as a secondary background signal.)
- `soil_moisture` 신호=1 신뢰도=0.40 출처=NOAA CPC Soil Moisture (Soil-moisture anomalies are used as a land-surface persistence term with modest positive temperature contribution.)
