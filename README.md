# claudebase

> Cross-machine Claude Code rig — settings, skills, hooks, plugins synced via git + symlinks.

Fix a setting on one machine, push, then `git pull` on every other machine to get it instantly. No re-installs, no manual copies.

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

### Token compression via headroom (opt-in)

`headroom` routes Claude Code through a **local** proxy that compresses tool
outputs, file reads, and logs before they reach the model — cutting input
tokens (docs ~20 %, JSON 60–95 %) with the same answers. It runs on your
machine; data never leaves it. The CLI ships via **pip** (the npm `headroom-ai`
is an SDK, not the CLI).

```bash
pip install "headroom-ai[all]"     # needs Python >=3.10
headroom wrap claude               # launch Claude Code through the proxy (:8787)
headroom doctor                    # health-check the integration
headroom dashboard                 # live token savings
```

**Installing it does not turn it on.** `pip install` only puts the CLI on the
machine — compression starts only when Claude Code is *launched* through the
proxy, so a plain `claude` bypasses it entirely and silently. The tell is
`headroom doctor`: a machine that installed it and never wrapped reports
`proxy: not reachable`, `wrap_marker: no wrap marker found`, and
`savings: no savings recorded yet`. Non-zero savings is the only proof it is
actually routing.

**When nothing launches `claude` by hand, `wrap` has no hook point.** In a
container or under a harness that spawns `claude` for you, route it with an env
setting instead — in **`settings.local.json`**, never `config/settings.json`
(that one is synced to every machine, so the proxy URL would reach machines with
no proxy running and fail every request there):

```jsonc
// ~/.claude/settings.local.json  — plus a running `headroom proxy`
{ "env": { "ANTHROPIC_BASE_URL": "http://127.0.0.1:8787" } }
```

**Routing turns off Remote Control and the 1M context window.** Claude Code gates
both on the base URL, client-side: point it at a local proxy and `/rc` stops
working and the 1M window no longer applies (upstream #746/#1158, which `headroom
doctor` names in its own output). This is not specific to the env route —
`headroom wrap claude` sets the same variable for its child, so it costs the same
for the session it wraps. Automatic compression and Remote Control + 1M are
therefore mutually exclusive; pick per machine, and leave routing off on any
machine you drive remotely or run a 1M-context model on. The MCP tools
(`headroom_compress`, `headroom_retrieve`) survive either choice, but they are
on-demand only — they cannot shrink a tool result that has already landed in the
context, so they do not substitute for the proxy.

**Run `installer/install.sh` after adding it.** Claude Code never reads
`settings.local.json` itself; the installer merges it into the rendered
`~/.claude/settings.json`, and that render is what actually routes the CLI. Skip
the run and the env block sits there doing nothing, silently. Once rendered,
`headroom doctor` reports it correctly too — its `claude: not routed` line reads
`~/.claude/settings.json`, which now contains the merged env. Either way the
`savings` row (or a rising `.summary.api_requests` from
`curl -s http://127.0.0.1:8787/stats`) is the ground truth. Note the proxy is not
a service: it dies with the container, and a dead proxy with this env set fails
every request — delete the `env` block and re-render to roll back. `headroom
install apply --preset persistent-service` promotes it to a keepalive service
(launchd/systemd at user scope) so it survives a reboot; `headroom install
status` is the check.

**One distinct port per machine — never the default 8787 on more than one.** The
default collides in a way that is easy to misread: VS Code Remote-SSH
auto-forwards a remote machine's listening ports to the *same* local port, so
opening a remote window makes your `localhost:8787` someone else's proxy. A local
deployment bound there then fails to bind and keepalive-respawns forever (`exit
code 3`), while `headroom install status` still reports `healthy` because the
forward answers the health probe — it cannot tell whose proxy replied. Confirm
ownership with `lsof -nP -iTCP:<port> -sTCP:LISTEN`: a local proxy shows a
`Python` process, a forward shows your editor's helper.

The allocation rule is one distinct port per machine, taken from the `18787+`
block (nothing forwards it by default) and recorded in that machine's own
`settings.local.json` — it is per-machine state and never belongs in a synced
file, this README included. So there is no central allocation list to consult:
pick any free number in the block and verify ownership on the spot with the
`lsof` check above. That check is authoritative where a list is not — it catches
a forward that a stale list would have called free.

Two invariants hold at any number of machines. Bind **`127.0.0.1` only, never
`0.0.0.0`** — on a flat overlay network (Tailscale, WireGuard, ZeroTier) that
publishes an unauthenticated credential-forwarding proxy to every node. And
point `ANTHROPIC_BASE_URL` at **this machine's own loopback, never another
host's address**, so requests never leave the box and one machine's dead proxy
cannot take another's sessions down with it. With the env route active,
`headroom wrap` is redundant — every `claude` already routes.

**Turn it off for full-fidelity reading.** Compression rewrites tool output, so
any task whose quality depends on the *exact* bytes — reading a codebase in full
(`/claude-mem:learn-codebase`), checking config values, reviewing a diff — must
run unrouted. Observed on v0.32.1: `Read` output came back re-encoded as
`"[22]{...:string,1:string}"` with `<<ccr:...>>` chunk refs, and — worse —
with tokens silently dropped (`from`, `class`, `def` vanishing from source
lines). Broken syntax is visible; a changed number or sign is not, and it
becomes a wrong conclusion nobody catches. A `[N items compressed to M]` marker
in tool output is the tell that it is active. Roll back by deleting the `env`
block above, re-rendering, and **starting a new session** — env vars are fixed
at process start, so an in-session edit changes nothing. Claude cannot restart
itself (it lives inside the wrapper), so this step is yours.

**Before turning it off, check the mode — the damage above is mostly `--mode
token`.** That mode is documented as "prior turns may be rewritten for max
savings", and in it `protect_recent_reads_fraction` defaults to `0.3`, so
everything but the most recent ~30% of `Read`/`Grep` results is silently
compressible. The default `cache` mode instead freezes prior turns to win on the
provider's prefix cache, which is where most of the money is anyway — one
machine measured 11.2% from compression against a far larger cache-read credit
over the same period. So prefer fixing the mode over dropping the proxy:

```bash
headroom proxy --mode cache \
  --protect-tool-results Read,Grep,Glob,Bash,Edit,Write,WebFetch,NotebookEdit
```

Passing `--protect-tool-results` also resets that `0.3` fraction to `0.0`, which
is what actually stops older file reads from being rewritten. A persistent
deployment keeps its flags in `~/.headroom/deploy/<profile>/manifest.json` —
edit `proxy_mode`, `base_env.HEADROOM_MODE`, and the `proxy_args` array together
(all three carry the mode), then `headroom install restart --profile <profile>`
and confirm the new flags landed with `ps`, since a restart silently keeps the
old ones if the file did not parse.

**What no flag protects: text you paste into the chat.** `--protect-tool-results`
covers tool results, and a pasted brief is a user message — so a long spec pasted
into the prompt can still come back with file:line citations and figures mangled,
which reads as if it were written that way. Write it to a file and pass the path
instead; that routes it through `Read`, which the flag does cover.

Opt-in and per-machine — nothing is installed by `install.sh`. Running
`/sync-claudebase` detects a missing `headroom` and offers to `pip install` it
(default No); step 4j also reports an installed-but-never-routed machine. See
[docs/ai-usage-fitting.md](docs/ai-usage-fitting.md) for the weekly
savings-vs-quality loop this feeds.

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
the skills' bare `python3` calls resolve to it:

```jsonc
// ~/.claude/settings.local.json  (machine-local, gitignored)
{ "env": { "PATH": "/Users/<you>/.claude/.venv/bin:$PATH" } }
```

The venv is machine-local (not git-synced) — re-running `installer/install.sh`
recreates it.

## Per-machine overrides

Put machine-specific plugins / permissions / model choice (e.g. `"model": "opus[1m]"`) in `~/.claude/settings.local.json` (gitignored). `installer/install.sh` merges it on top of `config/settings.json` and **renders** the result to `~/.claude/settings.json` — the only user-scope settings file Claude Code reads. Two consequences: edits to `settings.local.json` take effect on the next `install.sh` run rather than instantly, and anything the CLI writes into the rendered file (`/model`, `/config`, `claude plugin enable -s user`) is captured back into `settings.local.json` on that run, so personal preferences persist without ever touching the tracked baseline. See `templates/settings.local.example.json`.

## Learn more

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) — directory layout, symlink model, plugin sync, secrets, drift detection
- [docs/CHANGELOG.md](docs/CHANGELOG.md) — what changed and when
- [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) — fork / PR guide
- [CLAUDE.md](CLAUDE.md) — repo-internal rules

## License

[MIT](LICENSE).
