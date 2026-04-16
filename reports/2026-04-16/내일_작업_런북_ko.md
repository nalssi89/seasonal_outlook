# 내일 작업 런북

## 목표

- 학습·검증 자료는 `1973-01`부터 `2025-12` 목표월까지로 제한한다.
- `2025-12`를 기준월로 두고 `2026-01`, `2026-02`, `2026-03`의 한반도 기온·강수 `-, 0, +` 확률을 산출한다.
- 추가 모델(`XGBoost`, `CatBoost`)은 성능 개선 가능성을 비교하되, 전체 백테스트가 너무 오래 걸리면 기존 모델군 결과를 먼저 확보한다.

## 바로 실행할 명령

### 1. 2025-12까지 전체 백테스트

```powershell
py -m seasonal_outlook.cli backtest-objective-forecast --history-end 2025-12
```

### 2. 2025-12 기준 2026년 1~3월 예측

```powershell
py -m seasonal_outlook.cli run-objective-forecast --issue-date 2025-12-16 --history-end 2025-12
```

설명:
- 현재 objective 코어는 `issue_date`의 `연-월`을 기준월로 사용한다.
- 따라서 `2025-12-16`은 사실상 `2025년 12월 기준 예측`을 뜻한다.
- 결과 목표월은 `2026-01`, `2026-02`, `2026-03`으로 생성된다.

## 결과 확인 파일

- 현재 예보 보고서:
  - `reports/2025-12-16/objective_forecast_ko.md`
- 학습 모델 요약:
  - `reports/2025-12-16/objective_model_training_ko.md`
- 구조화 예보 JSON:
  - `state/objective_forecast/objective_forecast_2025-12-16.json`
- 구조화 학습 요약 JSON:
  - `state/objective_forecast/trained_models_2025-12-16.json`
- 모델별 백테스트 요약:
  - `state/objective_forecast/backtest_summary.md`

## 시간이 너무 오래 걸릴 때

먼저 축약 검증으로 상태만 확인:

```powershell
py -m seasonal_outlook.cli backtest-objective-forecast --history-end 2025-12 --max-origins 60
py -m seasonal_outlook.cli run-objective-forecast --issue-date 2025-12-16 --history-end 2025-12
```

그 다음 전체 백테스트를 다시 실행한다.

## 내일 우선 확인할 것

1. `backtest_summary.md`에서 `XGBoost`, `CatBoost`가 실제로 `RPSS > 0`인지 확인
2. 강수 `M+1/M+2/M+3`에서 기존 `kNN/LightGBM`보다 개선되는지 확인
3. 기온 `M+1/M+2/M+3`에서 `LightGBM` 대비 추가 개선이 있는지 확인
4. `objective_forecast_ko.md`의 2026년 1~3월 확률과 대표기호를 최종 정리

## 메모

- 현재 코드에는 `--history-end YYYY-MM` 옵션이 추가되어 있어 `2025-12`까지만 학습·검증하도록 제한할 수 있다.
- 현재 objective 코어는 동적모델 결과를 섞지 않는다.
- 스냅샷 기후인자는 아직 설명용 참고값이며, 역사 시계열이 연결된 인자만 학습 입력으로 사용된다.
