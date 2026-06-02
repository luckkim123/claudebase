# docker-env — claudebase 개인 docker 관리 스킬 설계

**Status**: DESIGN (구현 미착수 — 사용자가 design까지만 요청, 2026-06-02)
**Author**: 분석·조사 workflow(`~/Desktop/workspace/.omc/omp_docker_design_workflow.js`, 13 agents) 종합
**그릇 결정**: omp 스킬군 ✗ · 별도 하네스 ✗ · **claudebase 개인 스킬 ✓**
**배포 제약**: claudebase는 연구실 배포용 → ⚠️ **절대경로·개인값 하드코딩 금지**

---

## 1. 무엇을 만드는가 (한 줄)

임의의 docker 프로젝트에서 **Dockerfile·compose·env·이미지 인벤토리를 일관되게 생성·추적·audit** 해 주는, claudebase에 배포되는 범용 docker 관리 스킬. "빌드 실행 대행"이 아니라 **"생성 + 관리 전문가"**.

`gen-image`·`sync-claude-settings`와 같은 계열의 개인 워크플로 스킬(`~/.claude/skills/`, 모든 머신서 trigger). 정본 위치는 `claudebase/runtime/skills/docker-env/`.

---

## 2. 왜 이 그릇인가 (3안 비교 — 확정된 판단)

| 방식 | 판정 | 근거 |
|:---|:---:|:---|
| omp 스킬군 | ✗ | omp는 **metadata-only·사용자 파일 생성 금지** 철학. organizer조차 기존 파일을 *옮길 뿐* 새 소스를 authoring 안 함(적대 검토가 `organizer.md` L13으로 확증). "Dockerfile 생성"은 omp에 선례 없는 행위 클래스 → 끼우면 배포 omp가 오염. 게다가 docker 관리는 *임의 프로젝트*가 아니라 *특정 워크플로*라 omp의 범용 프로젝트 관리와 결이 다름 |
| 별도 하네스(oh-my-docker) | ✗ | 하네스 1개 = 9~10 스킬 + 5 에이전트 + 훅 + 테스트 + 배포(github·marketplace·claudebase enable). docker 파일 관리엔 **과투자**(메모리의 5개 하네스 부트스트랩 비용으로 확인) |
| **claudebase 개인 스킬** | **✓** | gen-image처럼 *개인 워크플로 전용*. omp 불가침 원칙에 안 묶이고, 생성·인벤토리·audit를 한 그릇에 자유롭게 담음. 배포·trigger·유지 비용 최소 |

---

## 3. 범위 (사용자 확정: 완전 범용)

- **범용 docker 관리** — ROS/시뮬 색채 제거. 사용자 `~/Desktop/workspace/0_docker`(ROS·Stonefish·IsaacGym 12개 환경)는 *참고 예시*일 뿐, 스킬은 임의 docker 프로젝트에 적용.
- `0_docker`는 **삭제 안 함** — 스킬의 입력 자료·검증된 패턴 출처로 유지.

### 3.1 담는 기능 (4 축)

1. **생성 (scaffold)** — 새 docker 자산을 best-practice 템플릿 + 프로젝트 명명규칙대로 생성: Dockerfile, compose.yaml, .env, .dockerignore. 기존 파일은 dry-run diff → 사용자 승인 → 새 파일/버전 스냅샷(절대 silent 덮어쓰기 금지). *omp가 못 하던 바로 그 기능 — 개인 스킬이라 가능.*
2. **인벤토리·추적** — 프로젝트의 이미지 ref·tag·digest·백업 위치(local/registry)·서비스 구성을 추적. **하이브리드 저장**(§5): 구조화 사실 → json, 서술 지식 → md.
3. **audit** — 새/기존 Dockerfile·compose가 규칙 어기나 검사: best-practice 규칙(§4) + 프로젝트 자체 규칙(서비스명 충돌·민감정보 마운트 등). read-only, PASS/FAIL + `file:line` 증거.
4. **검증된 함정 카드** — 도메인 함정을 스킬 본문에 박음(예: compose 폐기된 `version:` 키, secret을 ARG/ENV로 넘기면 image history 누출, GPU/X11 GUI 설정). 단 **개인값이 아닌 메커니즘만**.

### 3.2 담지 않는 것 (명시적 비범위)

- **빌드/run/push/prune 실행 대행** — `docker build`·`up`·`push`를 LLM이 대신 누르는 것은 가치 낮음(사용자가 직접 하는 게 빠름). 스킬은 *명령을 제안·검증*하되 실행은 사용자. (인벤토리 추적에 필요한 read-only 조회 `docker images`·`inspect`는 예외적 허용 — §6 미해결.)
- **CVE 스캔·SBOM·서명**(Trivy/cosign) — 시간변동·네트워크 의존. CI의 일이지 개인 관리 스킬의 일 아님. v1 비범위.
- **digest 원격 해석·drift 추적** — 네트워크·비결정론. 정적 텍스트에 쓰인 ref/tag만 기록(적대 검토가 omp-dataset의 로컬 hashlib과 대비해 잡은 함정).

---

## 4. docker best-practice 규칙 (조사 결과 — audit·생성의 DATA)

생태계 전체가 **안정적 네임스페이스 rule ID(DATA)**로 수렴: hadolint `DL3007`, checkov `CKV_DOCKER_7`, dockle `CIS-DI-0001`. 스킬은 이를 **미러링**(불투명 자체 코드 발명 = 문서화된 안티패턴). Dockerfile은 정규식 아닌 **구조 파싱**이 표준(과소평가 주의: line continuation·heredoc·multi-stage·JSON vs shell form).

핵심 체크(요약): 멀티스테이지 / 레이어 순서(deps 설치 후 `COPY .`) / `:latest` 금지+digest 핀 / 최소·비-root(숫자 UID) / `.dockerignore` / secret은 ARG·ENV 금지(BuildKit `--mount=type=secret`) / `COPY` over `ADD` / exec-form CMD. compose: 폐기 `version:` 제거 / named volume / healthcheck+`start_period` / `depends_on` 조건 / `secrets:` 메커니즘.

⚠️ **도메인 인지**: GUI 시뮬·ROS 개발 컨테이너는 distroless·비-root가 *불가능*한 게 정상. audit는 규칙을 강제(fail)가 아니라 **severity로 경고**하고, 프로젝트가 `.env`/설정으로 특정 규칙을 끌 수 있어야 함(rule ID를 DATA로 다루는 이유).

선행 사례: `devcontainer.json`·`compose-spec.json`이 "컨테이너 설정을 DATA로 선언"하는 가장 완전한 prior art. Renovate/Dependabot이 FROM·compose ref를 의존성으로 추적.

전체 조사·출처: workflow 결과 `research[]` 4 facet (Dockerfile / 이미지·레지스트리 / compose / 거버넌스 도구), URL 60+ 인용.

---

## 5. 저장 포맷 — 하이브리드 (사용자 "md 비효율" 주장 검증 결과)

사용자 주장: "wiki가 커지면 md는 비효율 → 처음부터 yaml/json key-value로." → 3 렌즈 적대검증 + 다른 세션 결론 **수렴**:

**판정: 주장은 부분적으로만 맞고, "전환"은 답이 아니다. 분리축은 크기가 아니라 데이터 타입.**

| 축 | 결과 |
|:---|:---|
| 토큰 비용(읽기) | md가 JSON보다 34~38% 적음(JSON 최악), YAML보다 ~10% 적음. "커질수록 비효율"은 거꾸로 |
| 정확도 | 구조화 우위는 *깊은 중첩*에서만, 승자는 YAML>JSON. 서술형엔 무관 |
| 접근 패턴 | 실제는 KV 조회 아닌 grep/FTS + context 로드. md가 grep 1급 시민 |
| diff/merge | append 위주 진화 저장소엔 md 압승(prose diff). iCloud sync서 더 중요 |
| 스키마 drift | md는 스키마 없음(새 사실=새 문장). "처음부터 구조화"가 오히려 부채 |
| scale 실측 | 수백 노트도 grep sub-ms. 병목은 LLM context window(json 인덱스로 안 풀림) |

**적용**: docker-env 저장도 **데이터 타입으로 분리**(omp가 이미 하는 hybrid와 동형):
- **구조화 사실 → json** (`docker_inventory.json`): 이미지 ref·tag·digest·백업위치·서비스 목록. 동질 레코드를 키로 조회 → json이 맞음.
- **서술 지식 → md** (`docker-notes.md`): "왜 이 베이스 골랐나"·"GUI 설정 주의점"·빌드 함정. 이질 prose를 토픽으로 recall → md. (유일 정당 증분: md 본문 + YAML frontmatter(tags·date) + INDEX.)

근거 전체: workflow `wikiFormat[]` 3 렌즈, 출처 25+ URL(improvingagents 벤치마크·Karpathy LLM-wiki·Claude Code memory frontmatter 등).

---

## 6. ⚠️ 절대경로·개인값 분리 (배포 핵심 제약)

claudebase는 **연구실 배포용**. 사용자 `0_docker`엔 개인값 만재: `luckkim123`(Docker Hub ID), `/media/ksm/ksm-ssd`(외장 SSD), `/home/ksm/workspace`, `DISPLAY=:1`. **이 값들을 스킬 본문에 박으면 동료 설치 시 깨짐.**

**정본 패턴(gen-image 상속)**: gen-image가 출력 경로를 절대경로 대신 *caller 계약 + `$GEN_IMAGE_OUTDIR`*로 해석하듯 —

| 개인값 | 스킬이 해석하는 방법 (하드코딩 X) |
|:---|:---|
| 레지스트리/네임스페이스 (`luckkim123`) | 프로젝트 `.env`의 `DOCKER_REGISTRY`/`DOCKER_NAMESPACE`, 없으면 사용자에게 1회 물어 `.env`에 기록 |
| 이미지 백업 경로 (`/media/ksm/...`) | `.env`의 `DOCKER_BACKUP_DIR` 또는 환경변수, 없으면 프로젝트 로컬 `images/` |
| 데이터 루트·CLAUDE.md 경로 | `.env`의 `DATA_ROOT`·`CLAUDE_MD_PATH` (사용자가 이미 쓰는 변수명 그대로) |
| DISPLAY·GPU·shm 등 | compose/env 변수로, 템플릿은 `${VAR:-default}` 형식 |

스킬 본문은 **메커니즘·템플릿·규칙만 범용으로**. 모든 사용자별 값은 프로젝트 `.env`에서 해석하거나 1회 질문 후 기록. 마침 `0_docker`가 이미 `environments/*.env` + `docker-template.env`로 그 분리를 함 → 스킬은 그 패턴을 **일반화**.

claudebase 자기검증: 배포 전 `grep -rn` 으로 스킬 본문에 개인값(`luckkim123`·`/media/ksm`·`/home/ksm`·사용자명) 0건 확인을 release 게이트로.

---

## 7. 스킬 구조 (초안 — 구현 시 확정)

`runtime/skills/docker-env/SKILL.md` 한 파일(gen-image처럼 self-contained). 섹션:

- frontmatter: name·description·triggers(`docker 관리`·`dockerfile 만들어`·`compose 작성`·`도커 환경`·`docker scaffold`·영어 대응) + `level`.
- §1 **언제 invoke / 비범위** (생성·인벤토리·audit는 yes; 빌드실행·CVE스캔은 no).
- §2 **개인값 해석 규칙** (§6 표 — 하드코딩 금지, .env 해석, 정본).
- §3 **생성** — 템플릿 + 명명규칙, dry-run→승인→새파일/스냅샷(safe 덮어쓰기).
- §4 **인벤토리** — `docker_inventory.json`(구조화) + `docker-notes.md`(서술) 하이브리드 기록.
- §5 **audit** — best-practice rule ID(DATA) 미러 + 프로젝트 규칙, severity 경고, read-only PASS/FAIL.
- §6 **검증된 함정 카드** — compose `version:` 폐기·secret 누출·GPU/X11 등(개인값 아닌 메커니즘).
- §7 **Acceptance** — 생성 후 `test -f`·`docker compose config` 검증 전엔 "done" 아님(gen-image의 "CLI 신뢰 X" DNA 상속).

---

## 8. 미해결 결정 (구현 전 사람 게이트)

1. **docker daemon read-only 조회 허용?** — 인벤토리에 실제 이미지 size/digest를 넣으려면 `docker images`·`inspect`가 필요(daemon 의존·오프라인 불가). 권고: **정적 우선**(텍스트에 쓰인 ref/tag만 기본), daemon 조회는 *옵트인*이고 모든 daemon-파생 필드는 nullable·없으면 생략(omp-dataset의 "모르면 비워둠" 미러).
2. **생성이 .dockerignore·compose까지 한 세트인가, Dockerfile만인가** — 사용자 `0_docker`는 항상 3종 세트(Dockerfile+compose+env). 권고: **세트 생성**을 기본, 단건도 허용.
3. **audit가 강제(fail) vs 경고(severity)** — GUI/ROS 컨테이너는 best-practice와 정반대가 정상. 권고: **경고 기본**, 프로젝트가 `.env`로 규칙 on/off.
4. **rule ID 출처** — hadolint/checkov ID 그대로 vs 자체 매핑. 권고: 둘 다 기록(upstream id + 설명), 자체 불투명 코드 금지.
5. **인벤토리 파일 위치** — 프로젝트 루트 `docker_inventory.json`+`docker-notes.md` vs `.docker-env/` dot-dir. 권고: dot-dir(`.docker-env/`)로 묶어 프로젝트 트리 오염 최소.

---

## 9. 다음 단계

design 합의 후 → `runtime/skills/docker-env/SKILL.md` 구현(claudebase git 커밋은 사용자 승인 후) → 배포 전 개인값 grep 0건 게이트 → marketplace/설치 반영. 구현은 surgical(배포 repo).

**SSOT**: 이 문서. 분석·조사 원본: workflow 결과(`~/Desktop/workspace/.omc/` 산출). 관련 메모리: `docker_env_skill_design.md`.
