# 인계: 그래프 엔지니어링 재조사 (worker-graph)

이 작업의 소유권을 너에게 완전히 넘긴다. 감독 코디네이터는 없다 — `worker_done` 같은 lifecycle 메시지를 보내지 말고, 사용자에게 직접 보고하며 스스로 완주해라. 노트북(ksm)은 곧 꺼진다.

너의 handle: `term_d321f1b3-9b63-45ff-86b2-aaf47f39135e` (worker-graph)
동료 handle: `term_27ff03f0-2b01-4512-9d26-7b12b32402dc` (worker-audit) — 같은 ksm-mac, 같은 vault

시작: `cd ~/ksm_Obsidian && git pull --rebase origin main` (caeb38b8 이후를 받아라)

## 배경
`0_Project/in_progress/harness/` 는 2026-08-22 ksm-mac 에서 세운 "하네스 생태계 고도화" 계획이다. 사용자 요구 5건 원문이 DESIGN.md §0 에 있고 조사 결과가 research/ 14개 문서다.

오늘 요구 #2(에이전트 협업)를 재조사해 어제 판정이 뒤집혔다. **시작 전 `research/ext-agent-collaboration-v2.md` 를 반드시 정독해라** — 네가 쓸 방법론이 거기 실증돼 있다.

재조사가 찾아낸 실패 모드 3종:
1. **요구 원문의 어휘를 그대로 검색어로 쓰면, 원문이 안 쓴 축은 조사에서 통째로 사라진다.** ("커뮤니티/게시판/반박"으로 찾으면 debate 문헌만, "duplicate work/task allocation/passive awareness"로 찾으면 전혀 다른 계열이 나온다)
2. **"이미 배선이 있다"는 전제를 실측 안 하고 넘어간다.** (실측해보니 shared_memory 사용 0건, Agent Teams 41세션 전부 팀원 0명이었다)
3. **최신 문헌 누락, 그리고 한쪽 증거만 담기.** 긍정만 담으면 어제 조사의 거울상이 된다.

## 네 작업: `research/ext-graph-engineering.md` 재조사
요구 #1의 절반이다. 미흡 근거:
- 그 문서의 최신 arXiv 인용이 **2502**(2025-02)다. 같은 폴더 다른 문서들은 2607·2608을 인용한다. 2026년 문헌 0건.
- 확증: 검색 한 번에 **arXiv 2603.27277** "Codebase-Memory: Tree-Sitter-Based Knowledge Graphs for LLM Code Exploration via MCP" 가 나왔다. 이 rig 의 tokensave·code-review-graph 와 정확히 같은 주제인데 그 문서에 없다. **2606.28379**(LEDGER, dependency-aware graph retrieval), **2511.18194**(Agent-as-a-Graph)도 미인용.

할 일:
1. 2026년 문헌을 다시 훑되 **축을 갈라 검색해라** — 코드그래프 검색 효율 / 에이전트 메모리 그래프 / 의존성 인지 retrieval / 워크플로 그래프 엔진 / 그래프 vs RAG. 어제 문서의 어휘만 쓰지 마라.
2. **부정 증거를 반드시 같이 찾아라.** 수치가 있으면 수치로, 없으면 confidence 표기.
3. 어제 문서가 실측 없이 단정한 전제를 실측해라 — §0 의 두 공백 주장(claude-mem 이 평면 SQLite 다 / om* 에 런타임 그래프 엔진이 없다), §5 의 "3종 중 지울 수 있는 것" 판정. 이 rig 에서 tokensave·code-review-graph·graphify 가 실제로 얼마나 조회되는지 로그로 확인 가능한지 봐라(`.omc/logs/`, `~/.claude/metrics/`).
4. 산출물: **`research/ext-graph-engineering-v2.md`**. 원본은 고치지 말고 남겨라 — v2 가 무엇을 왜 뒤집는지가 기록의 핵심이다. 형식은 `ext-agent-collaboration-v2.md` 를 그대로 따라라 (한 문장 결론 → rig 실측 → 놓친 문헌 → 반대 증거 → 재판정 표 → 확인 안 함 → 다음에 잴 것 → Sources).
5. 확인 안 한 것은 반드시 "확인 안 함"으로 남겨라. 추측을 사실로 쓰지 마라.

## 파일 소유권 (겹치면 안 된다)
- **너만 쓴다**: `research/ext-graph-engineering-v2.md`
- **worker-audit 만 쓴다**: `research/AUDIT-2026-08-23.md`, 그리고 그 외 research/ 문서 감사
- **둘 다 쓰지 마라**: `DESIGN.md`, `PLAN.md` — 확정 판정 변경이라 사용자 승인 대상이다
- 공유 노트(둘 다 append 가능, 반드시 작성자 표기): `0_Project/in_progress/harness/notes/2026-08-23-worker-comms.md`

## 동료와의 협력 규약
worker-audit 이 research/ 전수 감사를 하며 **네 문서에 대한 감사 결과도 낼 수 있다**. 서로 발견을 나눠라.

보낼 때:
```
orca orchestration send --to term_27ff03f0-2b01-4512-9d26-7b12b32402dc --subject "<한 줄>" --body "<내용>" --type status --json
```
받을 때(작업 단계 사이사이에 한 번씩):
```
orca orchestration check --json
```
보낼 가치가 있는 것: 네가 실측한 rig 사실(로그 유무·사용량), 감사 기준에 쓸 만한 신호, 네 문서 범위와 겹치는 발견. 잡담·중계는 보내지 마라 — 새 신호 없는 중계는 문헌상 해롭다.

**이 통신이 실제로 작동했는지 사용자에게 반드시 보고해라.** send/check 가 되는지, 안 되면 어떤 에러인지. 안 되면 공유 노트 파일로 폴백해라. 이건 부탁이 아니라 측정이다 — 이 rig 에서 세션 간 발견 공유가 실제로 작동하는지가 요구 #2 재조사의 열린 질문이고, 너희 둘이 그 첫 데이터다.

## 규약
- vault 는 git 이다. 변경 후 커밋+푸시, 한국어 접두사(`[프로젝트]`).
- ksm-mac 에 다른 vault 터미널들이 훅 정리 중이다. 오늘 실제로 두 세션이 같은 훅 정리를 중복 분석한 사건이 있었다 — 겹칠 것 같으면 먼저 확인해라.
- 훈련 launch·로봇 조작은 이 작업 범위 밖이다.
- 각 단계가 끝나면 사용자에게 보고하고 다음 진행 여부를 물어라.
