---
name: docker-env
description: |
  Manage a Docker project's assets — scaffold Dockerfiles / compose / .env / .dockerignore from best-practice templates, track an image inventory, and audit for known anti-patterns. A "generate + manage expert", NOT a build runner: it proposes and verifies commands but the user runs `docker build`/`up`/`push` themselves. Every personal value (registry namespace, backup path, data root, DISPLAY) is resolved from the project `.env` or asked once — NEVER hardcoded, because this skill ships to other machines. Verifies generated files on disk (`test -f`, `docker compose config`) — never trusts a tool's stdout alone.
  Triggers: docker 관리, dockerfile 만들어, dockerfile 작성, compose 작성, 도커 환경, docker scaffold, docker 인벤토리, dockerfile audit, 도커파일 검토, manage docker, write a dockerfile, scaffold compose, audit dockerfile, docker inventory
argument-hint: "<scaffold|inventory|audit> [project-dir] [--name <purpose-base>] [--set|--single]"
level: 2
triggers:
  - "/docker-env"
  - "docker-env"
  - "docker 관리"
  - "dockerfile 만들어"
  - "dockerfile 작성"
  - "compose 작성"
  - "도커 환경"
  - "docker scaffold"
  - "docker 인벤토리"
  - "dockerfile audit"
  - "도커파일 검토"
  - "manage docker"
  - "write a dockerfile"
  - "scaffold compose"
  - "audit dockerfile"
  - "docker inventory"
---

# docker-env

Be the docker expert for an arbitrary project: **scaffold** new Dockerfile / compose / `.env` assets from best-practice templates, **track** an image inventory, and **audit** existing assets against known anti-patterns. It is a *generate + manage* tool, **not a build runner** — it writes and checks files and proposes commands, but the user runs `docker build`/`up`/`push`.

**Rigid** on two things: every personal value is *resolved, never hardcoded* (§2), and every generated file is *confirmed on disk* before claiming done (§7). **Flexible** elsewhere: base image choice, template wording, how deep the audit goes.

## When to invoke

- **Scaffold**: "도커파일 만들어줘", "compose 작성", "이 프로젝트 docker 환경 잡아줘", "scaffold a docker setup for …", `/docker-env scaffold`
- **Inventory**: "이미지 정리/추적", "어떤 이미지 어디 백업했는지", "docker inventory", `/docker-env inventory`
- **Audit**: "이 Dockerfile 검토", "compose 문제 없나", "audit dockerfile", `/docker-env audit`

Do **not** invoke for:
- **Running builds** — `docker build`/`up`/`push`/`prune`. The skill *proposes and verifies* the command; the user runs it. (Read-only `docker images`/`inspect` for inventory is opt-in only — §4.)
- **CVE scan / SBOM / image signing** (Trivy, cosign) — time-varying, network-bound, a CI job. Out of scope; point the user at a scanner.
- **Remote digest resolution / drift tracking** — non-deterministic network state. Record only the ref/tag written in the project's own text.

## The three modes

Pick the mode from the request. All three first run §2 (resolve personal values). Scaffold and audit are the common pair; inventory is the lighter bookkeeping mode.

---

## §1 — Project shape (read before writing)

Before scaffolding or auditing, read what the project already does — match its conventions, don't impose yours.

- `ls` for existing `Dockerfile*`, `*.Dockerfile`, `docker-compose*.y*ml`, `compose.y*ml`, `.dockerignore`, `.env*`.
- If a naming convention is already visible (e.g. `<purpose>-<base-system>:<version>`, a `compose/` + `environments/` split, a manager script), **adopt it** — a new file that breaks the project's own pattern is the bug, not a feature.
- If nothing exists, propose the layout in §3 and confirm once.

## §2 — Resolve personal values (RIGID — never hardcode)

This skill ships to other people's machines. **No absolute path, registry namespace, username, or host-specific value may appear in a file you generate.** Resolve each from the project `.env` (or ask once and write it there), exactly as `gen-image` resolves its output dir from a caller contract instead of a hardcoded path.

| Value | How to resolve (NEVER hardcode) |
|:---|:---|
| Registry / namespace (e.g. a Docker Hub user) | `.env` `DOCKER_REGISTRY` / `DOCKER_NAMESPACE`; if absent, ask once and write it to `.env` |
| Image backup dir (e.g. an external SSD path) | `.env` `DOCKER_BACKUP_DIR` or an env var; if absent, fall back to project-local `images/` |
| Data root / mounted host paths | `.env` `DATA_ROOT`, `CLAUDE_MD_PATH` (reuse the project's existing variable names) |
| `DISPLAY` / GPU count / `shm_size` | compose/env variables, templated as `${VAR:-default}` (e.g. `${DISPLAY:-:0}`) |

Mechanism in the skill body is universal; **the values live in the project `.env`**. Generated Dockerfiles/compose reference `${VAR}` and never a literal `/home/<user>/…` or `<user>/<image>`. When you must show an example in chat, use a placeholder (`<registry>/<image>:<version>`), not a real value.

> **Release gate (for whoever edits this skill):** before shipping, `grep -rn` the skill body for any concrete personal value (a real username, `/media/…`, `/home/…`, a real registry id). It must return **0 hits**. A personal value in the body breaks every colleague's install.

## §3 — Scaffold

Generate docker assets from best-practice templates + the project's naming rule. Default to a **set** (Dockerfile + compose + `.env` + `.dockerignore`); a single file is fine when asked.

**Flow (safe-overwrite, never silent):**
1. **Resolve** personal values (§2) and read project shape (§1).
2. **Name**: derive `<purpose>-<base-system>` from the request (e.g. `sensor-dev-ros2-humble`); image ref = `${DOCKER_REGISTRY}/<purpose>-<base-system>:<version>` (semantic version, no `v` prefix). Container name = `<purpose>-<base-system>`. Service name = `<purpose>-<platform>`. Confirm these once.
3. **Dry-run**: if a target file exists, show a diff and **wait for approval**; never silently overwrite. On approval, write the new file (or a versioned snapshot beside it).
4. **Write** the set, then §7 verify.

**Best-practice defaults baked into the template** (these are the audit rules of §5 applied at birth):
- Multi-stage where a build toolchain isn't needed at runtime; deps installed **before** `COPY . .` so layer cache survives source edits.
- Pin the base (`FROM image:tag` at minimum, digest `@sha256:…` when reproducibility matters) — never bare `:latest`.
- `.dockerignore` always (`.git`, `node_modules`, build artifacts, `*.tar.gz`, data dirs).
- Secrets via BuildKit `--mount=type=secret`, **never** `ARG`/`ENV` (those leak into image history).
- `COPY` over `ADD`; exec-form `CMD ["…"]`; a `HEALTHCHECK` when the service has a readiness signal.
- compose: **no `version:` key** (obsolete — Compose Spec ignores it and warns); named volumes for persistence; `${VAR:-default}` for every host-specific value.

**Domain reality — GUI / GPU / ROS dev containers legitimately break the rules.** A simulator or ROS dev image needs `privileged`, `network_mode: host`, GPU passthrough, X11 socket, large `shm_size` — the opposite of distroless/non-root, and that is *correct* for the domain. When the project is this kind, scaffold the GPU/GUI block as data, not as a violation:

```yaml
# compose service — GPU + GUI passthrough (templated; no host-specific literals)
services:
  <purpose>-<platform>:
    image: ${DOCKER_REGISTRY}/<purpose>-<base>:${VERSION}
    container_name: <purpose>-<base>
    stdin_open: true
    tty: true
    privileged: true              # GUI/sim domain — intentional, audit-warns not fails
    network_mode: host
    ipc: host
    shm_size: ${SHM_SIZE:-16g}
    env_file: [ ../environments/<name>.env ]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [compute, utility, graphics]
    volumes:
      - ${CLAUDE_MD_PATH}:/root/CLAUDE.md:ro     # project guidance, read-only
      - ${DATA_ROOT}:/workspace/data:rw
      - /tmp/.X11-unix:/tmp/.X11-unix:rw         # X11 GUI socket
    environment:
      - DISPLAY=${DISPLAY:-:0}
      - QT_X11_NO_MITSHM=1
```

(Host prep for X11 — `xhost +SI:localuser:root` before `up` — goes in a comment or the project README, not the image.)

## §4 — Inventory (hybrid storage)

Track the project's images and where they live. Default to a `.docker-env/` dot-dir so the project tree stays clean. **Split by data type, not by size** — structured facts → JSON, narrative knowledge → md. (This is the verified verdict: md beats JSON ~34–38% on read tokens and is grep-first; JSON wins only for homogeneous keyed records. Don't "convert everything to JSON" — keep both.)

- **`.docker-env/docker_inventory.json`** — homogeneous keyed facts, queried by key: image ref, tag, build context, backup location (local path *variable* or registry), service list. Schema is closed and stable.
  ```json
  {
    "images": [
      { "ref": "${DOCKER_REGISTRY}/sensor-dev-ros2-humble", "tag": "1.0.0",
        "dockerfile": "dockerfiles/sensor-dev-ros2-humble.Dockerfile",
        "compose": "compose/sensor-dev-ros2-humble.yml",
        "backup": "$DOCKER_BACKUP_DIR or registry", "size": null, "digest": null }
    ]
  }
  ```
- **`.docker-env/docker-notes.md`** — heterogeneous prose, recalled by topic: *why* this base image, GUI/GPU setup gotchas, build pitfalls hit. md body + a small YAML frontmatter (`tags`, `date`) + an INDEX line. This is grep-recalled, not key-queried.

**Daemon fields are opt-in and nullable.** Real `size`/`digest` need `docker images`/`inspect` (daemon-dependent, offline-impossible). Default to **static** — record only refs/tags written in the project's text; leave `size`/`digest` `null`. Fill them only if the user opts into a read-only daemon query, and omit (don't guess) when unavailable.

## §5 — Audit (read-only, severity-warn)

Check a Dockerfile/compose against best-practice rules + the project's own rules. Output `PASS`/`WARN`/`FAIL` with `file:line` evidence. **Parse structure, don't regex** — handle line-continuations, heredocs, multi-stage, JSON-vs-shell form (a naive `grep latest` misses `FROM ${BASE}` and false-flags a comment).

Mirror the ecosystem's **stable rule IDs as DATA** — don't invent opaque codes. Record both the upstream id and a plain description:

| Rule (upstream id) | Check |
|:---|:---|
| `DL3007` (hadolint) | base pinned, not `:latest` |
| `DL3009` / layering | `apt-get` cleans `/var/lib/apt/lists`; deps before `COPY .` |
| `DL3002` / `CIS-DI-0001` (dockle) | runs as non-root (`USER` set) — **warn**, see below |
| `CKV_DOCKER_2` (checkov) | `HEALTHCHECK` present when a service has readiness |
| secret-in-ARG/ENV | no secret material in `ARG`/`ENV` (leaks to history) → BuildKit secret |
| compose `version:` | obsolete top-level `version:` key removed |
| compose service-name clash | no two services/containers share a name within the project |
| sensitive mount | mounts like `CLAUDE.md` / config are `:ro`, not `:rw` |

**Severity, not enforcement.** GUI/sim containers *intentionally* break non-root/distroless/privileged rules. So audit **warns**; it does not fail the build. A project may turn a specific rule off via `.env` / a `.docker-env/audit.toml` (rule id → off) precisely because rule ids are data. Default posture: warn-only; never block.

## §6 — Verified pitfall cards (mechanism only, no personal values)

- **compose `version:` is obsolete.** The top-level `version:` key is ignored by Compose Spec and emits a warning. Remove it; schema is inferred.
- **Secrets leak through `ARG`/`ENV`.** Anything passed as a build `ARG` or set as `ENV` is recoverable from `docker history`. Use BuildKit `RUN --mount=type=secret=…` (build) or compose `secrets:` (runtime).
- **GPU passthrough is `deploy.resources.reservations.devices`**, not the old `runtime: nvidia`. `driver: nvidia`, `count: all`, `capabilities: [compute, utility, graphics]` (add `graphics` for OpenGL/GUI). Needs the NVIDIA Container Toolkit on the host.
- **X11 GUI from a container** = mount `/tmp/.X11-unix:/tmp/.X11-unix:rw`, pass `DISPLAY=${DISPLAY:-:0}` + `QT_X11_NO_MITSHM=1`, and host-side `xhost +SI:localuser:root` before `up`. Forgetting any one → "cannot connect to X server".
- **`shm_size` / `ipc: host` for DDS / large shared memory.** ROS2 DDS and some GPU stacks need shared memory above the 64 MB default; set `shm_size` (e.g. `${SHM_SIZE:-16g}`) and/or `ipc: host`.
- **CMD shell-form swallows signals.** `CMD foo` runs under `/bin/sh -c` and won't forward `SIGTERM`; exec-form `CMD ["foo"]` (or an `ENTRYPOINT` that `exec`s) stops cleanly.
- **`COPY . .` before installing deps busts the cache** on every source edit. Copy the manifest, install, *then* copy source.
- **A library's own build quirk** can need a one-line patch (e.g. a stray flag in a generated cmake config) — keep such fixes as a commented `RUN sed -i …` so the next person knows why it's there.

## §7 — Acceptance (RIGID — never claim done on stdout)

Generation isn't done until the file is verified on disk and parses:

```bash
test -f "$TARGET" && { stat -f%z "$TARGET" 2>/dev/null || stat -c%s "$TARGET"; }   # exists, non-empty
docker compose -f "$COMPOSE" config >/dev/null && echo "compose OK"                # parses (if daemon/CLI present)
```

- File exists, non-empty, and (for compose) `config` parses → done. Report the path.
- File missing while you "wrote" it, or `config` errors → **not done**; fix and re-verify.
- Never report success from a tool's "Saved!" / "Created!" text alone — check the filesystem. (Inherited from `gen-image`: the CLI lies.)

## Never

- Hardcode a personal value — username, absolute path, real registry id, `DISPLAY=:1` — into a generated file or this skill body. Resolve from `.env` (§2).
- Silently overwrite an existing Dockerfile/compose. Dry-run diff → approval → write (§3).
- Run `docker build`/`up`/`push`/`prune` on the user's behalf. Propose + verify the command; the user runs it.
- Fail a build for a GUI/sim container breaking distroless/non-root. Warn with severity; let the project opt out by rule id (§5).
- Claim done on stdout — always `test -f` + `compose config` (§7).
- Write `size`/`digest` you didn't actually read from the daemon. Leave them `null` (§4).

## Sources

Best-practice rules (§3, §5) and the storage verdict (§4) come from a 2026-06-02 analysis workflow (Dockerfile / image-registry / compose / governance facets + a 3-lens storage benchmark):
- **hadolint** rule reference (`DL3007`, `DL3009`, `DL3002` …) — Dockerfile linting rule ids as the canonical, stable namespace.
- **checkov** (`CKV_DOCKER_*`) and **dockle** (`CIS-DI-*`) — IaC/CIS docker rule ids; mirrored as data, not reinvented.
- **Compose Specification** — the `version:` key is obsolete; schema inferred. Named volumes, `secrets:`, `depends_on` conditions.
- **Docker BuildKit secrets** docs — `RUN --mount=type=secret`; why `ARG`/`ENV` leak to `docker history`.
- **NVIDIA Container Toolkit** + Compose `deploy.resources.reservations.devices` — GPU passthrough is a device reservation, not `runtime: nvidia`.
- `devcontainer.json` / `compose-spec.json` — prior art for "container config as declarative DATA."
- Storage split (md vs JSON): md ~34–38% fewer read tokens than JSON, grep-first access, append-friendly diff; JSON only for homogeneous keyed records — so a **hybrid**, split by data type not size, not a wholesale conversion.

**Origin**: designed 2026-06-02 (`claudebase/docs/specs/2026-06-02-docker-env-skill/design.md`) from a 13-agent research workflow. Reference patterns (GPU/X11/privileged/shm, `<purpose>-<base>:<version>` naming, CLAUDE.md `:ro` mount, the manager-script command set) were distilled from a real multi-environment ROS/sim docker setup — **mechanisms kept, every personal value stripped** for distribution.
