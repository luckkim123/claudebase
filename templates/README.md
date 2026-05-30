# Project `.claude/` Boilerplate

새 프로젝트 시작 시 `.claude/` 디렉토리의 표준 시작점.

## 사용법

```bash
# 새 프로젝트 루트에서:
cp ~/claudebase/templates/project-settings.json .claude/settings.json
cp ~/claudebase/templates/project-CLAUDE.md CLAUDE.md
cat ~/claudebase/templates/project-gitignore >> .gitignore
```

## 파일

| 템플릿 | 복사 위치 | 용도 |
|---|---|---|
| `project-settings.json` | `<project>/.claude/settings.json` | Project-level hooks/permissions (이 프로젝트에만 적용) |
| `project-CLAUDE.md` | `<project>/CLAUDE.md` | Project-specific 지침. Claude Code가 자동 로드 |
| `project-gitignore` | `<project>/.gitignore`에 append | `.claude/settings.local.json` 같은 머신별 파일 제외 |
| `project-refactor-workflow.md` | `<project>/.claude/rules/refactor-workflow.md` | 다단계 리팩토링의 4축 추적(branch/commit/CHANGELOG/PR) 규율 |

## 원칙

- **범용 설정**(plugins, alwaysThinking 등)은 `~/.claude/settings.json` (= `claude-settings` repo)에 있음. 여기는 **이 프로젝트에만** 의미 있는 것만.
- `.claude/settings.local.json`은 절대 commit 금지 (gitignore 처리됨).
- `CLAUDE.md`는 Critical Rules 위주로 짧게 — 디테일은 `.claude/rules/<topic>.md`로 분산.
