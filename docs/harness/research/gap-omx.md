# oh-my-experiments(omx) 갭 분석 — v0.11.2 실측

## 결론 (BLUF)

사용자가 "만들고 싶다"고 표현한 5개 요구(논의·읽기·분석·계획·검증)는 **이미 omx v0.11.2에
전부 구현돼 있고, 그중 4개는 실제로 albc 프로젝트에서 실사용된 흔적이 확인된다.** 유일하게
확인 안 된 축은 "사용자와의 논의"이며, 이것도 exp-init 단계에만 국한된 1회성 인터뷰로
**부분** 구현이다. 새로 만들 필요가 있는 것은 없다 — 이번 조사가 om* 갱신 방향에 주는
시사점은 "omx에 무엇을 추가할까"가 아니라 "oms가 상위 레이어가 될 때 omx의 기존 결합
지점(wiki query, report-parse, campaign ledger)을 어떻게 재사용할까"다.

CLI verb는 스킬 4개가 아니라 **약 46개 top-level + wiki 하위 12개 = 58개**이며, 이 규모가
207(사용자 추정)~154(.py 실측) 파일 수를 설명한다. verb 이름 문자열은 테스트 스위트
(1,019개 test 함수)에서 전부 최소 1회 이상 참조되지만, **실사용(albc)에서 실제로 호출된
흔적이 확인된 verb는 그중 일부뿐**이다 — 아래 "실사용 실측" 참조.

---

## 1. CLI verb 전수 목록 (`omx-core/omx_core/cli.py:1865-2411`)

정독 방식: `grep -n "add_parser(" cli.py`로 등록 지점 전수 추출 (verified, cli.py:1865-2411).

### Top-level (약 40개)

| 그룹 | verb |
|:---|:---|
| 코어 I/O | `ingest`, `reduce summarize`, `reduce tb-final`, `session-id`, `doctor`, `card-check` |
| 평가 | `eval`, `profile-seal` |
| 시각화 | `plot`, `promote-plots` |
| 부트스트랩 | `init` |
| 트리 관리 | `tree-codify`, `tree-audit`, `tree-scaffold`, `tree-alias`, `tree-index` |
| 리포트 | `report-parse`, `report-verify`, `report-coverage`, `report-review` |
| 제안 | `proposal-lint`, `probe-novelty` |
| 런치/루프 | `queue-launch`, `loop-status`, `loop-arm`, `loop-disarm`, `loop-mark-done`, `loop-health` |
| 재현 | `run-seed`, `run-record`, `revert-config` |
| 정리 | `clean` |
| 캠페인 | `campaign-init`, `campaign-log`, `campaign-status`, `campaign-list`, `campaign-plan-add`, `campaign-drift` |
| 프로그램 | `program-init`, `program-lint`, `program-status` |

### `wiki` 하위 verb (12개, cli.py:2205-2304)

`add`, `capture-session`, `capture-flush`, `promote-recipe`, `query`, `lint`, `list`, `read`,
`sync-profile`, `gc`, `gc-apply`, `delete`

**파일 수의 이유**: `omx-core/omx_core/`에 top-level 모듈 28개(atomic/campaign/cardcheck/clean/
clock/coverage/decision/doctor/evaluator/integrity/ledger/lock/loop/omx_paths/profile/program/
proposal/report/revert/review/root/seal/state/tree_audit/tree_ops/tree/cli — verified,
`ls omx_core/*.py`) + `ingest/`(4 어댑터) + `reduce/`(다수) + `wiki/`(다수) 서브패키지 +
`tests/`(154개 .py 중 다수가 테스트) — verb 하나당 평균 1개 모듈이 아니라, CLI는 얇은
디스패처이고 실제 로직은 각 모듈에 있는 구조. verified, cli.py 전체가 얇은 wrapper(각
`_cmd_*` 함수는 대부분 10~40줄, 실제 로직을 `from omx_core.X import Y`로 지연 임포트).

---

## 2. 요구 항목별 있음/부분/없음 판정

| 요구 | 판정 | 근거 |
|:---|:---|:---|
| (a) 사용자와의 논의 | **부분** | `exp-init` SKILL.md가 "interactive ambiguity-gated Socratic interview"를 명시 (skills/exp-init/SKILL.md:3, 11). 하지만 이는 **셋업 1회성**(프로파일 부트스트랩)에 한정 — exp-analyze/exp-design 단계에는 "논의"가 아니라 사용자 승인 게이트(`pending_approval`)만 있다(skills/exp-design/SKILL.md:17, cli.py:461 `"pending_approval": True`). 지속적 대화형 논의 verb/skill은 없음. |
| (b) 이전 결과 읽기 | **있음** | `exp-analyze` 전제조건이 "runs to analyze exist on disk... resolve them"(skills/exp-analyze/SKILL.md:35-37). `ingest`/`reduce`가 TB/wandb/csv/npz/eval_summary를 파싱(cli.py:70-104, `_adapters()`). |
| (c) 연구 내용 분석 | **있음** | exp-analyze의 "hybrid router"가 code-exec 통계 vs vision-read PNG를 질문별로 선택(skills/exp-analyze/SKILL.md:3, 13). 엔진 실행 강제("MUST, not MAY") + 빈 셀 검증("empty cell is a HYPOTHESIS, not a fact") 규율이 SKILL.md에 명문화(skills/exp-analyze/SKILL.md:39-80). |
| (d) 다음 실험 계획 | **있음** | `exp-design`이 3-lane 감별진단(code-path/config-DR-hyperparam/measurement-artifact)으로 단일 discriminating probe를 제안, `proposals/<id>.md`로 기록(skills/exp-design/SKILL.md:3, 11-17). `queue-launch` verb가 승인 전 런치를 pending-approval 아티팩트로만 큐잉(cli.py:923-928, 절대 직접 실행 안 함). |
| (e) 결과 평가·검증 | **있음** | `omx eval`(cli.py:272-337, evaluator 실행+판정), `report-coverage`(cli.py:621-779, 진단그룹·엔진인용 완결성 게이트+baseline 회귀 게이트), `proposal-lint`(cli.py:829-840, 감별 예측 계약 게이트), `report-review`(cli.py:782-805, 기계적 리뷰), 4개 리뷰 agent(`agents/proposal-reviewer.md`, `agents/report-reviewer.md`, `agents/campaign-auditor.md`, `agents/wiki-curator.md`). |

---

## 3. 실사용 실측 — 무엇이 실제로 돌았나

**이 머신·vault에서 `.omx/` 상태 디렉터리 검색 결과** (verified, `find /Users/kimseungmin -maxdepth 6 -type d -name '.omx'`):

- `/Users/kimseungmin/ksm_Obsidian/0_Project/in_progress/albc/.omx` — 실제 프로젝트 상태
  (session-gate 훅이 로봇 안전 상태 미확인 세션의 접근을 차단 — albc는 물리 로봇이 위험
  상태(J1 −1.375바퀴 감김, 관절 버스 사망)라 이번 조사에서는 **안쪽 내용을 열지 않았다**,
  gate를 우회해서 볼 필요가 없는 조사 범위이므로. 존재 자체만 확인 — verified).
- `/Users/kimseungmin/.claude/jobs/e027c397/tmp/seedcheck{,2}/.omx` — job 임시 디렉터리,
  실사용이라기보다 테스트/디버그 산출물로 추정 (unverified — 내용 미확인).
- `~/.claude/plugins/marketplaces/omc/.omx` — omc 마켓플레이스 캐시 내부, omx 자체 사용
  흔적 아님 (unverified, 경로명만으로 판단).

**tokensave_search "omx"로 확인된 albc 내 omx 사용 텍스트 증거** (verified, vault index):

- `sim_validation/findings/README.md` — "omx wiki 지식 초안 12건, 2026-08-14 기준 전건
  원격 반영 완료"라고 명시. `omx wiki add`/`query` verb가 실사용됐다는 1차 증거.
- 대조 재현 커맨드가 원격 컨테이너에서 실행됨: `ssh ksm@141.223.223.195 'docker exec
  marinelab-isaaclab bash -lc "cd /workspace/constrained-albc && omx wiki query --root .
  servo --limit 5"'` (findings/README.md:47-50) — **`omx wiki query` verb 실사용 확정**.
- `.omx/programs/simtoreal-thrusters-live/HANDOFF.md`를 정본으로 인용하며 두 `.omx`
  저장소(marinelab vs vault-albc)의 경계를 "무엇을 바꾸는 실험인가"로 규정(findings/README.md:9-16)
  — **`program-init` verb + programs/ 구조 실사용 확정**.
- `docs/2026-07-29-sim-gap-probe-plan.md:88` "백로그 대조 (omx 열린 lead 전수 — 2026-07-29
  16:20 조회)" — wiki list/query류 verb의 반복 조회 흔적.

**실사용이 확인된 스킬/verb**: `exp-analyze`(리포트 작성 → wiki 반영 흐름), `wiki add`,
`wiki query`, `program-init`(programs/HANDOFF.md), 그리고 경계 결정 문서가 암시하는
`campaign` 개념("무엇을 바꾸는 실험인가"는 campaign 경계 규칙과 동일 어휘, campaign-init
verb의 실사용은 **unverified** — 텍스트가 개념을 인용할 뿐 verb 호출 로그는 없음).

**실사용이 확인되지 않은 것 (부재의 증거 아님, "확인 안 함")**: `exp-init`의 대화형
인터뷰, `exp-design`의 proposal 파이프라인, `exp-loop`의 자율 루프(`loop-arm`/
`loop-status`/`queue-launch`), `tree-*` 5종, `run-seed`/`run-record`/`revert-config`,
`clean`, `card-check`. 이 목록은 vault·이 머신 범위 검색으로 못 찾았다는 뜻이며, MEMORY.md
어디에도 `exp-init`/`exp-design`/`exp-loop` 스킬명이 직접 언급되지 않는다(MEMORY.md 전체
스캔, verified — "omx 관련 기록"으로 검색된 항목은 모두 인프라 배포·설정 관련이지 4개 스킬
실행 기록이 아님, 예: `project_code_graph_stack`, `machine_omx_registry_write_locus`,
`project_omx_empty_gate_fix`). marinelab 컨테이너 내부(원격 서버) 실행 기록은 이 조사
범위 밖(unverified — 접근 안 함).

---

## 4. 위상 재료 (판정 보류 — 사용자·설계 결정 대상)

### "zero runtime dependency" 선언

- 선언 위치: README.md:17-19 — "It is a first-class omha tier-1 lane alongside
  `oh-my-claudecode` and `superpowers`, but carries **zero runtime dependency** on any
  other harness."
- 코드 반영 확인 (verified): `omx-core/pyproject.toml` dependencies = `numpy`, `pandas`,
  `matplotlib`, `pyyaml`만 있고 optional-dependencies(`analyze`)에 `wandb`, `tensorboard`.
  omc/omp/oms/omd에 대한 `import`/`from` 문 0건 (`grep -rn "import om[cpds]\|from om[cpds]"
  omx-core/omx_core --include='*.py'` → 결과 없음, verified).
- **선례 문서 존재**: `docs/cross-harness-backport-decision.md` — 2026-05-31, omp 0.2.0의
  5개 후보 기능을 전부 REJECT하며 "omx의 정체성은 외부 패턴을 직접 import하지 않고 자기
  코드에 재구현하는 것"이라고 명문화(문서:19-22). 이는 이번 조사 지시가 묻는 "oms가 상위가
  될 때 omx에서 무엇이 깨지는가"와 정확히 같은 질문을 2026-05-31에 이미 한 번 던졌고, 그때
  결론은 **결합 거부**였다는 뜻. oms를 상위로 두는 새 결정은 이 선례를 명시적으로 뒤집는
  결정이 될 것 — 판정은 사용자 몫.

### 기존 결합 지점 후보 (코드에 이미 존재하는 인터페이스, 재사용 가능성 평가는 보류)

| 인터페이스 | 위치 | 성격 |
|:---|:---|:---|
| `report-parse` | cli.py:564-600 | report.md를 구조화 JSON({claim, evidence, confidence})으로 파싱. 무결성 스탬프 검증(`_integrity.verify_report`) 포함 — 위조/미게이트 리포트 거부. |
| `proposal` lint/novelty | cli.py:829-920 | `proposal-lint`(감별 예측 계약 게이트), `probe-novelty`(wiki+과거 proposal+campaign ledger 대조 — jaccard 유사도로 재시도 경고). |
| `wiki query` | cli.py:2248-2256, `omx_core/wiki/query.py` | 키워드+태그 검색(임베딩 없음, CJK-aware). CLI verb이자 Python 함수(`query_wiki`)로 내부에서도 재사용됨(cli.py:859 `probe-novelty`가 직접 호출). |
| campaign ledger | cli.py:2319-2367, `omx_core/campaign.py` | `.omx/campaigns/<id>/ledger.jsonl` append-only 이벤트 로그(`launched`/`analyzed`/`kept`/`discarded`/`note`). `record_analyzed`/`record_launched`가 report-coverage/queue-launch에서 자동 호출됨(cli.py:723, 991) — advisory(실패해도 게이트 안 막음). |

이 네 인터페이스는 모두 **파일 기반 + CLI verb + 순수 Python 함수**로 삼중 노출돼 있어,
상위 레이어(oms)가 프로세스 호출(`omx wiki query ...`) 또는 직접 import(`from
omx_core.wiki.query import query_wiki`) 중 하나를 택할 수 있는 구조다. 다만 후자를 택하면
"zero runtime dependency" 원칙이 **omx→외부는 여전히 0이지만 외부→omx는 이미 위 실사용
사례(albc가 원격 컨테이너에서 `omx wiki query` 프로세스 호출)에서 확인된 대로 프로세스
경계를 통해서만 이루어진다**는 관례와 일치한다. 이 프로세스 경계 관례를 유지할지, oms가
import 결합으로 들어갈지는 이번 조사 범위 밖의 설계 결정.

---

## 5. 제거 관점 — 죽은 코드가 있는가

**낮은 신뢰도 결론(unverified 다수)**: `tokensave_dead_code`가 omx-core에 색인이 없어
grep 기반으로만 판단했고, 이 방법은 "테스트에서 문자열로 언급됨"만 확인할 뿐 "실행 경로가
살아있음"을 증명하지 않는다.

- **verb 문자열 커버리지**: 46개 top-level verb 전부 `tests/`에서 최소 1회 이상 문자열
  매치됨(verified, 개별 grep 루프 결과 "NO TEST REF" 0건). → 테스트 스위트 관점에서 명백한
  사장 코드는 없다.
- **README 버전 배지 불일치**: README.md:5 배지가 `0.7.4`인데 `pyproject.toml`은
  `0.11.2`(verified, 두 파일 직접 대조) — 코드는 아니지만 **문서 드리프트**이자 "지우기"
  관점에서 정정 대상.
- **cards/ 디렉터리**: `.gitkeep`만 있고 실질 카드 파일 0개(verified, `find cards -type f`).
  omx 자체는 라우팅 카드를 갖지 않고 omha 쪽 카드에 의존하는 구조로 추정(unverified —
  omha 쪽 카드 파일 미대조).
- **실사용 대비 verb 규모 격차**: 46개 top-level + 12개 wiki 하위 verb 중, 이번 머신에서
  실사용이 텍스트로 확인된 것은 `wiki add/query`, `report-coverage`(간접, 스탬프 언급),
  `program-init` 정도로 **10% 미만**이다. 이것이 "죽은 코드"라는 결론은 **내리지 않는다**
  — 사용자 결정 방향에 명시된 대로 "이 머신·vault 실측"만으로는 원격 컨테이너(marinelab)
  실행 기록과 다른 프로젝트(krit 등)에서의 사용을 볼 수 없기 때문. tree-*/loop-*/run-*
  계열 verb의 무사용은 "이 세션에서 못 찾았다"이지 "안 쓰인다"의 증거가 아니다.

**제거 후보로 제시 가능한 것 (증거 기반, 판정 아님)**:
1. README.md 버전 배지 정정 (`0.7.4` → `0.11.2`) — 안전한 제거/수정, 코드 변경 없음.
2. `cards/.gitkeep`만 있는 빈 디렉터리 — omx가 카드 체계를 실제로 쓰지 않는다면 디렉터리
   자체 제거 후보 (단, omha 라우팅과의 결합 여부 미확인이므로 삭제 전 대조 필요).

---

## 6. 열린 질문 (사용자·다음 세션 결정 대상)

1. omx의 "zero runtime dependency" 선언과 2026-05-31 backport-reject 선례를 oms 상위화
   결정이 명시적으로 뒤집을 것인지, 아니면 프로세스 경계(CLI 호출)만 유지한 채 결합할지.
2. tree-*/loop-*/run-record/revert-config/clean/card-check 6개 verb군의 실사용 여부 —
   이 머신 밖(marinelab 컨테이너, krit 등 다른 프로젝트) 확인이 필요.
3. cards/ 빈 디렉터리가 omha 라우팅과 실제로 연결돼 있는지(omha 쪽 카드 파일 대조 필요).
4. exp-init의 "논의"가 1회성 인터뷰에 그치는 것이 의도된 설계인지, 아니면 이번 조사가
   드러낸 실제 갭(지속적 논의 부재)인지 — "이득은 스킬 존재가 아니라 훅 컨텍스트에서
   나왔다"는 실측(SSOT: claudebase/eval/README.md)에 비추어, exp-analyze/exp-design
   단계에 "논의" 기능을 새로 추가하는 것이 정당화되려면 스킬 호출 자체가 이미 낮았던
   전례를 감안한 높은 입증 부담이 걸린다.
