# ~~진행 중~~ **완료** — `finding/015` 세 변수 절제 실험 (2³ 요인설계 120런)
- id: handoff/016 · date: 2026-08-26 · author: coordinator
- to: 다음 세션 · keywords: ablation, finding-015, attribution, in-flight, applyfail
- summary: **✅ 완료 (2026-08-26).** 절제 3팔로 시작해 2³ 요인설계 8칸 × 15런까지 갔다. 결과: **순수 3차 교호작용** — 셋을 다 되돌려야만 떨어진다. 결과 정본은 `finding/017`. 이 글은 설계·교란·재현 절차를 보관한다.

## 무엇을 가르나

기준선: `applyfail_incidental_banner` (control, 규칙 없음) = **배너 미갱신 12/15 = 80%**.
옛 계측기 `applyfail_stale_banner` (control) = **0/5 = 0%** (천장).

세 변수가 **한꺼번에** 0% → 80% 를 만들었다. 각 팔은 그중 **하나만** 옛 값으로 되돌린다. 셋 다 규칙 미제공(control 조건).

| 팔 | 되돌린 변수 | 유지한 것 |
|:---|:---|:---|
| `applyfail_abl_scope` | 지시 범위 — "도출 절을 고쳐라" → **"문서에 반영해라"** | 자가 도출 · 45줄 거리 |
| `applyfail_abl_handed` | 자가 도출 — 반증 사실을 **프롬프트가 떠먹임** | 절 한정 지시 · 45줄 거리 |
| `applyfail_abl_distance` | 거리 — 사이 4개 절 삭제, **배너와 도출 절 인접** | 자가 도출 · 절 한정 지시 |

**읽는 법**: 어떤 팔이 80% → 0% 쪽으로 크게 내려가면, 되돌린 그 변수가 효과의 주범이다. 셋 다 조금씩 내려가면 상호작용이고 단일 귀속은 불가.

## 미리 밝히는 교란

- `applyfail_abl_distance` 는 절을 지우면서 "조건 D 는 장비 대여 일정 때문에 같은 창에서 못 돌렸다" 한 줄도 같이 사라진다. **같은 정보가 CSV `note` 열에 남아 있어** 도출은 여전히 가능하지만, 거리만 순수하게 뺀 것은 아니다.
- `applyfail_abl_scope` 의 "문서에 반영해라"는 범위이자 동사 변경이다(검증→반영). 분리 안 됨.
- 모델 1종, 온도 미통제. 15런 분산이 조건인지 샘플링인지 안 갈랐다.

## 채점기 — 런 전에 검증했다

세 팔 모두 손으로 만든 산출물 4종(완벽 / 본문만 / 무행동 / 전체삭제)에 채점기를 직접 실행해 `1.0 / 0.667+STALE / 0.333 / 0.333+BASELINE LOST` 를 확인했다. 거리 팔은 baseline 판정 기준을 사라진 절 대신 `## 후속`·`retry_limit` 으로 바꿨다.

## 재현

```bash
cd ~/claudebase/eval
coder-eval run tasks/applyfail_abl_scope.yaml \
               tasks/applyfail_abl_handed.yaml \
               tasks/applyfail_abl_distance.yaml --repeats 15 -j 4 --run-dir /tmp/ce-abl
```
집계는 저장된 산출물에 채점기를 재실행해서 뽑는다 (`task.json` 스키마 파싱 금지 — 채점기 소스 문자열이 결과로 오인된다, 2026-08-26 실측).

## Comments
- (2026-08-26, coordinator) 완료. 3팔 → 8칸으로 확장. 결과 `finding/017`. 미리 밝힌 교란 3개는 결론에 영향 없음 — 어느 단일 변수도 효과가 없었으므로 거리 팔의 CSV note 잔존이나 scope 팔의 동사 변경이 결과를 만들 수 없다.
