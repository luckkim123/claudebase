# claudebase

> A hardened, cross-machine Claude Code rig — guard hooks that catch the model's failure modes, a curated plugin set, and one installer that renders both onto any machine.

Fix a setting on one machine, push, then `git pull` on every other machine to get it instantly. But sync is the plumbing, not the point. The point is the layer above dotfiles: **hooks that enforce what prose rules cannot**, each one written only after the failure it prevents was observed in a real transcript.

## What it guards

A rule in `CLAUDE.md` is advisory — the model can read it and still not follow it. A hook is not advisory. Eight are wired by default:

| Hook | Fires on | Failure mode it catches |
|:---|:---|:---|
| `askuserquestion-guard.py` | PreToolUse · AskUserQuestion | `AskUserQuestion` emitted with an empty `questions` array — the harness rejects it and the turn is wasted. Observed five times in a single session *after* a text-only CLAUDE.md rule was added, which is why it is a hook. |
| `askuserquestion_retry.py` | Stop | The same defect caught after the fact — forces an immediate retry instead of ending the turn on a dead call. |
| `detect_malformed_toolcall.py` | Stop | Tool-call markup leaking into the assistant's **text** channel. It self-poisons the session (retries reproduce it), so early detection is the only cheap fix. |
| `fix_surrogate.py` | Stop · SessionStart | Lone UTF-16 surrogates written into the session transcript, corrupting it. Common in non-ASCII sessions. |
| `emoji_guard.py` | Stop | Emoji in the final response — they mangle drag-select copying, so a copied answer comes back broken. |
| `agent-routing-guard.py` | PreToolUse · Agent/Task | Research-shaped work dispatched to a subagent that cannot do research. |
| `session-title-3words.py` | UserPromptSubmit | The built-in session namer ignoring its own stated length limit. Deterministic, no model call. |
| `hud-ensure.sh` | SessionStart | Plugin updates silently overwriting the customized HUD wrapper. |

Every hook records its own diagnosis — date, transcript evidence, and why *that* lifecycle event — in its docstring. `tests/hooks/` covers them with nine test modules; `tests/smoke/` asserts the installer is idempotent.

Four more ship unwired, as utilities: `askuserquestion_stats.py` (failure telemetry rollup), `merge-project-hook.py` (project-scope hook merge), `omc-reference-emit.py` and its loader.

## What's enabled

Fourteen plugins are common — enabled on **every** machine. Anything one machine alone needs stays in that machine's `settings.local.json` (see [Plugin reconciliation](CLAUDE.md)).

| Plugin | Marketplace | Why it is common |
|:---|:---|:---|
| `oh-my-claudecode` | `omc` | Default executor for multi-task work (`/team`, `autopilot`, `ralph`) and owner of the HUD statusline. |
| `superpowers` | official | Escalation path for correctness-sensitive work: a fresh implementer **plus** a spec-compliance and a code-quality reviewer per task — the one guarantee OMC cannot replicate. |
| `oh-my-heroacademia` | `heroacademia` | Per-turn routing. Decides which lane handles a request, and is the single source of truth for that decision. |
| `oh-my-project` | `heroacademia` | Project-folder governance — structure and naming rules, safe relocation, dataset manifests. |
| `oh-my-docs` | `heroacademia` | Document artifacts (pptx/docx/xlsx/hwpx) with a per-format knowledge card. |
| `oh-my-scholar` | `heroacademia` | Paper pipeline — survey, outline, draft, verify, mock review. |
| `oh-my-experiments` | `heroacademia` | Training-run analysis and next-experiment design, with a human gate before any launch. |
| `ponytail` | `ponytail` | Anti-over-engineering discipline: the laziness ladder, applied every response. |
| `context7` | official | Current library and framework docs, in preference to recalled API surfaces. |
| `claude-md-management` | official | Auditing and improving `CLAUDE.md` files. |
| `claude-code-setup` | official | Automation recommendations for a new codebase (hooks, skills, subagents). |
| `pyright-lsp` | official | Python language server. |
| `clangd-lsp` | official | C/C++ language server. |

Six skills are the repo's own, under `runtime/skills/`: `sync-claudebase`, `changelog`, `memory-update`, `gen-image`, `video-downloader`, `invoice-organizer`.

Eight subagents live under `runtime/agents/`, vendored from [Everything Claude Code](https://github.com/affaan-m/ECC) (MIT) rather than written here — two language reviewers, a PyTorch error resolver, an ML-engineering reviewer, a transcript-mining hook finder, and the three-stage open-source release pipeline. Attribution and the local edits are in [docs/third-party-agents.md](docs/third-party-agents.md).

## What lives where

| Path | Contents | Reaches the machine as |
|:---|:---|:---|
| `config/` | `CLAUDE.md`, `settings.json`, `settings.critical.json`, `mcp.template.json` | `CLAUDE.md` symlinked; `settings.json` **rendered** with `settings.local.json` merged on top |
| `runtime/hooks/` | The eight guard hooks plus utilities | Referenced by absolute path from rendered settings |
| `runtime/skills/` | Seven repo-owned skills | Symlinked into `~/.claude/skills/` |
| `runtime/output-styles/` | `concise.md` — answer-first response style | Symlinked into `~/.claude/output-styles/`; activated by `outputStyle` in `config/settings.json` |
| `runtime/omc-patches/` | Patches applied to the OMC plugin after install | Applied by the installer |
| `installer/` | `install.sh` / `install.ps1`, 15 `lib/` modules, render and plugin-sync scripts, git hooks | Run once per machine |
| `platform/` | `macos/`, `linux/`, `windows/` specifics | Selected by the installer |
| `shell/` | `tmux.conf`, `claude-mouse.sh` | Symlinked; mouse script is opt-in |
| `secrets/` | `secrets.env` (gitignored), `secrets.example.env` | Substituted into `mcp.json` at render time |
| `templates/` | Per-project `CLAUDE.md`, settings, gitignore starters | Copied on demand |
| `tests/` | Hook tests, installer tests, install smoke test | `pytest` |
| `docs/` | Architecture, rationale, changelog | Read, not installed |

Adding a file under `config/`, `shell/`, `runtime/skills/`, or `runtime/output-styles/` means adding a `link_or_copy` line to **both** installers and a row to this table.

## Quick start

```bash
# Clone to ~/claudebase (the canonical path; hooks/skills reference it)
git clone https://github.com/luckkim123/claudebase.git ~/claudebase
cd ~/claudebase

# Install
installer/install.sh                  # macOS / Linux
# pwsh installer/install.ps1          # Windows
```

That symlinks `~/.claude/CLAUDE.md`, your skills and hooks into the repo, and **renders** `~/.claude/settings.json` from `config/settings.json` plus this machine's `settings.local.json`. To update: `git pull` — enough for everything symlinked; a change to `config/settings.json` needs one `installer/install.sh` run to re-render.

### Code graphs (installed by the same run)

Three of them, because they answer different questions. `code-review-graph`
serves callers/importers/blast-radius from an incremental SQLite index;
`graphify` builds a whole-corpus knowledge graph and exports artifacts a human
opens; `tokensave` indexes symbols **and markdown headings** — the only one of
the three that reads prose without an LLM pass, which is what makes it the one
worth having in a notes repo. Full routing rules, and the failure modes that
make an empty graph look like a healthy one, are in
[`templates/project-code-review-graph.md`](templates/project-code-review-graph.md).

`installer/install.sh` installs the CLIs, renders graphify's `/graphify` skill
for this machine's `GRAPHIFY_OUT`, and registers the MCP servers. Prerequisites
are warned about rather than enforced: **`uv`** for the first two, and **`brew`**
(macOS) or **`cargo`** (Linux) for tokensave — the cargo path compiles 34
tree-sitter grammars, so give it several minutes.

It does **not** build a graph anywhere. That stays per-repo, and two hooks make
it self-managing:

- `GRAPH_REFRESH` (Stop) updates the graphs a repo *already has* — detached, so
  a turn never waits, and debounced to once a minute. No graph, no work.
- `GRAPH_OFFER` (SessionStart) tells the session, **once per repo ever**, that
  this repo has ≥20 tracked code files and no graph, and lets you decide. The
  marker lives in `.git/`, so the answer travels with the clone and is never
  committed.

Creation is a decision rather than a default because a blindly built graph is
worse than none: the `PreToolUse` guards then *require* consulting it. One
Obsidian vault produced 0 nodes from 746 tracked `.md` while 101 files of
vendored plugin JS produced 21,425 "functions" and a 212 MB index — with no
error anywhere. The offer therefore carries its own verification step.

### Installing tmux + clipboard tool

`tmux.conf`'s mouse-copy bindings need `tmux` and a clipboard helper. By
default the installer only warns if they're missing (keeps the install
idempotent and non-interactive). To have it install them for you:

```bash
INSTALL_TOOLS=1 installer/install.sh
```

This is best-effort and OS-aware — already-present tools are skipped, and it
never blocks on a sudo password prompt (falls back to a warn-only hint
instead):

| OS | Package manager | tmux | Clipboard |
|:---|:---|:---|:---|
| macOS | Homebrew | `brew install tmux` | built-in (`pbcopy`/`pbpaste`, nothing to install) |
| Linux (Debian/Ubuntu) | apt | `apt-get install -y tmux` | `wl-clipboard` (Wayland) or `xclip` (X11), picked by `$WAYLAND_DISPLAY` |
| Linux (Fedora/RHEL) | dnf | `dnf install -y tmux` | same as above |
| Linux (Arch) | pacman | `pacman -S --noconfirm tmux` | same as above |

Without `INSTALL_TOOLS=1`, a missing tool just prints the manual install
command for your platform instead.

### Native drag-select in the terminal (opt-in)

Claude Code's TUI captures mouse events, which breaks native / tmux
drag-to-select (the selection gets "stuck" at the visible screen edge). The
installer can wrap the `claude` command so it launches with mouse capture
disabled, restoring terminal selection:

```bash
INSTALL_CLAUDE_MOUSE=1 installer/install.sh   # non-interactive
# or just run installer/install.sh and answer [y/N] at the prompt
```

On yes it appends one marked `source shell/claude-mouse.sh` line to your login
shell's rc (`~/.zshrc` / `~/.bashrc`) — the only place claudebase writes to your
rc, marker-guarded so re-runs are a no-op. **Tradeoff**: mouse-off also disables
in-TUI mouse clicks/scroll (use the keyboard / tmux copy-mode). Revert by
deleting the `claudebase:claude-mouse` line. Windows: documented no-op (Unix /
tmux concern).

### Optional extra plugins (opt-in)

A few non-core plugins are available as opt-in personal extras — **not** enabled
lab-wide (they're absent from `config/settings.json`):

| Plugin | Marketplace | What it is |
|:---|:---|:---|
| `remotion` | `remotion-dev/claude-code-plugin` | programmatic video (React / Remotion) |
| `ui-ux-pro-max` | `nextlevelbuilder/ui-ux-pro-max-skill` | UI/UX design intelligence |
| `marketing-skills` | `coreyhaines31/marketingskills` | 60+ marketing skills |
| `claude-mem` | `thedotmack/claude-mem` | cross-session memory (adds session-start injection — measure it, see fitting doc) |

Enable them by running `/sync-claudebase` (step 4k detects, asks per plugin, then
registers the marketplace + installs each at user scope), or manually:

```bash
claude plugin marketplace add <marketplace-ref>
claude plugin install <plugin> -s user
```

## MCP servers with API keys

```bash
cp secrets/secrets.example.env secrets/secrets.env
$EDITOR secrets/secrets.env
installer/install.sh                  # re-render mcp.json
```

`secrets/secrets.env` is gitignored.

## Document-skill Python dependencies

The `oh-my-docs` (omd) and `ppt-academic` skills build documents with Python
libraries: `python-pptx`, `python-docx`, `python-hwpx`, `matplotlib`,
`Pillow`. `installer/install.sh` installs these into a dedicated virtual
environment at `~/.claude/.venv` built on Python ≥3.10 (required by
`python-hwpx`; the system `python3` may be older, and Homebrew Python is PEP
668 externally-managed). Prepend the venv's `bin` to the session `PATH` so
the skills' bare `python3` calls resolve to it.

**Write the full absolute PATH — Claude Code does NOT expand variables in the
`env` block.** A value like `".venv/bin:$PATH"` is passed *literally*: the
`$PATH` becomes a bogus path component, so the venv dir effectively *replaces*
your PATH instead of prepending to it. Every hook subprocess then loses
`/opt/homebrew/bin`, `/bin`, `/usr/bin`, so `node`/`bash`/`security` become
"command not found" — which silently breaks `/login` too (it can't run
`security` to persist the token). Neither `$PATH` nor `${PATH}` is interpolated
([Claude Code env-vars docs](https://code.claude.com/docs/en/env-vars.md)), so
list every dir explicitly, venv first:

```jsonc
// ~/.claude/settings.local.json  (machine-local, gitignored)
// Apple Silicon Homebrew shown; on Intel Homebrew lives in /usr/local/bin.
{ "env": { "PATH": "/Users/<you>/.claude/.venv/bin:/Users/<you>/.local/bin:/opt/homebrew/bin:/opt/homebrew/sbin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin" } }
```

The venv is machine-local (not git-synced) — re-running `installer/install.sh`
recreates it.

## Per-machine overrides

Put machine-specific plugins / permissions / model choice (e.g. `"model": "opus[1m]"`) in `~/.claude/settings.local.json` (gitignored). `installer/install.sh` merges it on top of `config/settings.json` and **renders** the result to `~/.claude/settings.json` — the only user-scope settings file Claude Code reads. Two consequences: edits to `settings.local.json` take effect on the next `install.sh` run rather than instantly, and anything the CLI writes into the rendered file (`/model`, `/config`, `claude plugin enable -s user`) is captured back into `settings.local.json` on that run, so personal preferences persist without ever touching the tracked baseline. See `templates/settings.local.example.json`.

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — directory layout, symlink model, plugin sync, secrets, drift detection
- [docs/ai-usage-fitting.md](docs/ai-usage-fitting.md) — the weekly spend-vs-quality loop
- [docs/operating-rationale.md](docs/operating-rationale.md) — why each operational limit in `config/CLAUDE.md` exists
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed and when
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — fork / PR guide
- [CLAUDE.md](CLAUDE.md) — repo-internal rules

## License

[MIT](LICENSE).
