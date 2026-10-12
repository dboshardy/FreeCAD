#!/usr/bin/env bash
# Start an isolated dev container with this repo mounted at /workspace.
# Base: Microsoft's official C++ dev container (gcc, cmake, ninja, gdb, git);
# pixi supplies the Python/conda toolchain from pixi.toml. Claude Code and gh
# are added on top. Host git identity, GitHub token and Claude login are passed in.
# A virtual display (Xvfb :99) runs the FreeCAD GUI; Claude screenshots and drives
# it, and you can watch at vnc://localhost:5900 (macOS Screen Sharing).
#   ./docker-dev.sh            interactive shell
#   ./docker-dev.sh claude     run a command instead
set -euo pipefail

repo="$(cd "$(dirname "$0")" && pwd)"
image=mycad-dev

# Docker Desktop < 4.44.3 lets containers reach the engine API (CVE-2025-9074),
# which means full access to the host's shared folders. Refuse to start on it.
dd="$(docker version --format '{{.Server.Platform.Name}}' | sed -n 's/^Docker Desktop \([0-9.]*\).*/\1/p')"
if [ -n "$dd" ] && [ "$(printf '%s\n' 4.44.3 "$dd" | sort -V | head -1)" != 4.44.3 ]; then
  echo "error: Docker Desktop $dd is vulnerable to CVE-2025-9074; update to 4.44.3 or later" >&2
  exit 1
fi

docker build -q -t "$image" - <<'DOCKERFILE' >/dev/null
FROM mcr.microsoft.com/devcontainers/cpp:ubuntu-24.04
RUN apt-get update && apt-get install -y --no-install-recommends gh python3 python3-venv \
      xvfb x11vnc xdotool scrot x11-utils libgl1 libegl1 libxkbcommon-x11-0 \
      libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-render-util0 \
 && rm -rf /var/lib/apt/lists/* \
 && mkdir -p /workspace/.pixi /workspace/build && chown -R vscode:vscode /workspace
USER vscode
RUN curl -fsSL https://pixi.sh/install.sh | bash \
 && curl -fsSL https://claude.ai/install.sh | bash \
 && echo '{"hasCompletedOnboarding":true}' > ~/.claude.json \
 && mkdir -p ~/.claude && printf '%s\n' \
  '# GUI in this container' \
  'FreeCAD runs on the virtual X display $DISPLAY (:99, 1920x1080). Build and launch:' \
  '`pixi run configure && pixi run build`, then `pixi run freecad > /tmp/freecad.log 2>&1 &`.' \
  'To see the GUI: `scrot -o /tmp/gui.png` then Read /tmp/gui.png. Screenshot after every' \
  'GUI action to confirm what changed; check /tmp/freecad.log for errors.' \
  'To drive it: `xdotool mousemove X Y click 1`, `xdotool type "text"`, `xdotool key ctrl+s`,' \
  '`xdotool search --name FreeCAD windowactivate`. List windows: `xwininfo -root -tree`.' \
  > ~/.claude/CLAUDE.md
ENV PATH=/home/vscode/.pixi/bin:/home/vscode/.local/bin:$PATH DISPLAY=:99
DOCKERFILE

# GitHub: reuse the token git already stores on the host (osxkeychain helper).
GH_TOKEN="${GH_TOKEN:-$(printf 'protocol=https\nhost=github.com\n\n' | GIT_TERMINAL_PROMPT=0 git credential fill 2>/dev/null | sed -n 's/^password=//p' || true)}"
export GH_TOKEN
[ -n "$GH_TOKEN" ] || echo "warning: no GitHub token found; export GH_TOKEN=<personal access token> to push" >&2

# Claude: prefer a long-lived token from `claude setup-token`; otherwise copy the
# host login out of the macOS keychain into a container-only credentials file.
claude_args=()
if [ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
  claude_args=(-e CLAUDE_CODE_OAUTH_TOKEN)
elif [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  claude_args=(-e ANTHROPIC_API_KEY)
elif creds="$(security find-generic-password -s 'Claude Code-credentials' -w 2>/dev/null)"; then
  creds_file="$(mktemp)"; trap 'rm -f "$creds_file"' EXIT
  chmod 600 "$creds_file"; printf '%s' "$creds" > "$creds_file"
  claude_args=(-v "$creds_file":/tmp/claude-credentials.json:ro)
else
  echo "warning: no Claude credentials found; run 'claude setup-token' and export CLAUDE_CODE_OAUTH_TOKEN" >&2
fi

tty=(-i); [ -t 0 ] && tty=(-it)

docker run "${tty[@]}" --rm --name mycad-dev \
  --cap-drop=ALL --security-opt=no-new-privileges \
  -v "$repo":/workspace \
  -v "$repo/.git/config":/workspace/.git/config:ro \
  -v "$repo/.git/hooks":/workspace/.git/hooks:ro \
  -v "$repo/docker-dev.sh":/workspace/docker-dev.sh:ro \
  -v mycad-pixi:/workspace/.pixi \
  -v mycad-build:/workspace/build \
  -w /workspace \
  -p 127.0.0.1:5900:5900 \
  -e GH_TOKEN \
  -e GIT_AUTHOR_NAME="$(git config user.name)" -e GIT_AUTHOR_EMAIL="$(git config user.email)" \
  -e GIT_COMMITTER_NAME="$(git config user.name)" -e GIT_COMMITTER_EMAIL="$(git config user.email)" \
  -e GIT_CONFIG_COUNT=2 \
  -e GIT_CONFIG_KEY_0=credential.https://github.com.helper \
  -e GIT_CONFIG_VALUE_0='!f() { echo username=x-access-token; echo "password=$GH_TOKEN"; }; f' \
  -e GIT_CONFIG_KEY_1=safe.directory -e GIT_CONFIG_VALUE_1=/workspace \
  ${claude_args[@]+"${claude_args[@]}"} \
  "$image" bash -c '
    Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp >/tmp/xvfb.log 2>&1 &
    until xdpyinfo >/dev/null 2>&1; do sleep 0.1; done
    x11vnc -display :99 -forever -shared -nopw -quiet -bg -o /tmp/x11vnc.log >/dev/null
    [ -f /tmp/claude-credentials.json ] && install -D -m 600 /tmp/claude-credentials.json ~/.claude/.credentials.json
    exec "$@"' _ "${@:-bash}"
