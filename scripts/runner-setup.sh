#!/usr/bin/env bash
# Register this devcontainer as the repo's self-hosted runner for the
# release-verify job (.github/workflows/build.yml, job `verify`).
#
# Registering is an outward-facing grant: the runner then accepts workflow
# code from this repository and that code drives the testbench. Run it only
# with the owner's explicit yes.
#
#   scripts/runner-setup.sh          install dependencies, register, start
#
# Per-repo, ephemeral (one job per registration), labels self-hosted,testbench.
# .devcontainer/devcontainer.json starts the restart loop on every container start.
set -euo pipefail

REPO="SensorsIot/gplug-mini-test"
RUNNER_DIR="/home/dev/actions-runner"
NAME="gplug-mini-test-devcontainer"

cd "$RUNNER_DIR"
sudo ./bin/installdependencies.sh

# An ephemeral registration is consumed by its one job, so the loop
# registers afresh before every run.
cat > loop.sh <<LOOP
#!/usr/bin/env bash
# Ephemeral runner: register, run one job, repeat.
cd $RUNNER_DIR
while true; do
  rm -f .runner .credentials .credentials_rsaparams   # stale registration from a consumed job
  TOKEN=\$(gh api -X POST "repos/$REPO/actions/runners/registration-token" --jq .token) \\
    && ./config.sh --unattended --replace --ephemeral \\
         --url "https://github.com/$REPO" --token "\$TOKEN" \\
         --name "$NAME" --labels testbench --work _work \\
    && ./run.sh
  sleep 5
done >> $RUNNER_DIR/loop.log 2>&1
LOOP
chmod +x loop.sh
pgrep -f 'actions-runner/loop[.]sh' >/dev/null || nohup bash loop.sh >/dev/null 2>&1 &
echo "runner loop started for $NAME on $REPO (labels: self-hosted, testbench)"
