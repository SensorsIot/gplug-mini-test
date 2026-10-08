FROM mcr.microsoft.com/devcontainers/base:debian

# Rename the base image's vscode user to dev, keeping UID 1000 so it matches the
# host user. Host-owned bind mounts are then readable directly and per-user npm
# needs no sudo.
RUN usermod -l dev -d /home/dev -m vscode \
    && groupmod -n dev vscode \
    && sed -i 's/vscode/dev/g' /etc/sudoers.d/vscode || true \
    && mv /etc/sudoers.d/vscode /etc/sudoers.d/dev 2>/dev/null || true

# Drop zsh/oh-my-zsh (~15MB, unused here)
RUN rm -rf /home/*/.oh-my-zsh /root/.oh-my-zsh \
    && apt-get purge -y zsh && apt-get autoremove -y

# Editing plus the host tier only. The ESP-IDF toolchain is deliberately NOT
# installed — firmware is built by GitHub Actions on espressif/idf:v6.0.2, see
# .github/workflows/build.yml. Keep this image lean; do not add idf.py, the
# riscv toolchain or a pip-installed esp-idf here.
#
# cmake/ninja/build-essential mirror what the `host` job of build.yml installs,
# so
# `cmake -S test/host -B build/host -G Ninja && ctest --test-dir build/host`
# runs here exactly as it does in CI.
#
# jq and curl are what the operational procedures in
# docs/UserDocumentation/User-Manual.md actually type.
#
# The GitHub Actions runner also needs libicu, but it is NOT listed here: the
# package name carries the soname version (libicu76 on this base today), so
# naming one pins the image to a Debian release and breaks the build on the next
# base bump. scripts/runner-setup.sh runs the runner's own installdependencies.sh,
# which resolves whichever version is present.
RUN apt-get update && apt-get install -y --no-install-recommends \
        tmux \
        cmake \
        ninja-build \
        build-essential \
        python3 \
        python3-pip \
        python3-venv \
        socat \
        jq \
        curl \
        && rm -rf /var/lib/apt/lists/*

# Per-user npm prefix on PATH for every shell, interactive or not. Must be an
# image ENV: Debian's .bashrc returns early for non-interactive shells, so an
# export there would be invisible to `ssh <host> claude ...`, hooks and scripts.
ENV PATH="/home/dev/.npm-global/bin:/home/dev/.venv/bin:${PATH}"

USER dev

# The bench test tier and the release-verify job both run pytest from here.
# A venv rather than `pip install --break-system-packages`: Debian's python3 is
# externally managed, and the runner must not be able to disturb it. Versions
# are pinned so a rebuild does not silently change what the gate enforces.
RUN python3 -m venv /home/dev/.venv \
    && /home/dev/.venv/bin/pip install --no-cache-dir \
        'pytest==8.*' \
        'requests==2.*' \
        'paho-mqtt==2.*' \
        'pyserial==3.*'

# UTF-8 so tmux renders block glyphs correctly (claude's splash logo)
RUN echo 'export LANG=C.UTF-8' >> /home/dev/.bashrc

# Persistent claude session: interactive SSH logins attach to a tmux session
# "main" so work survives disconnects. Skips non-interactive shells, shells
# already inside tmux, VS Code terminals, and any login while ~/.no-tmux exists.
RUN printf '%s\n' \
    '' \
    '# --- Persistent claude session (auto-attach tmux on interactive SSH) ---' \
    'if [ -n "$SSH_CONNECTION" ] && [ -z "$TMUX" ] && [ "$TERM_PROGRAM" != "vscode" ] && [ ! -f "$HOME/.no-tmux" ] && command -v tmux >/dev/null 2>&1; then' \
    '    case "$-" in' \
    '        *i*) exec tmux new-session -A -s main -c /workspaces/gplug-mini-test "claude; exec bash" ;;' \
    '    esac' \
    'fi' \
    >> /home/dev/.bashrc

WORKDIR /workspaces/gplug-mini-test
RUN echo 'cd /workspaces/gplug-mini-test 2>/dev/null' >> /home/dev/.bashrc
