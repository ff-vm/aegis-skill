#!/usr/bin/env bash
# Copy the skill pack to the Aegis, install the SDK there (offline), and run a skill.
#
#   ./run_on_robot.sh <user> [skill] [extra args...]
#
#   ./run_on_robot.sh myuser              # install + check (doesn't move)
#   ./run_on_robot.sh myuser greet
#   ./run_on_robot.sh myuser square --side 0.5
#
# Env: ROBOT_IP (default 192.168.234.1), FF_SDK_AEGIS_HOST (default 127.0.0.1),
#      FF_SDK_AEGIS_VARIANT (e.g. footed).
# Join the robot's Wi-Fi hotspot first. ssh asks for the password once.
set -euo pipefail

USER_NAME="${1:?usage: ./run_on_robot.sh <user> [skill] [args...]}"
SKILL="${2:-check}"
shift $(( $# >= 2 ? 2 : 1 ))
ROBOT_IP="${ROBOT_IP:-192.168.234.1}"
HOST="$USER_NAME@$ROBOT_IP"
APP_DIR='~/ff_app'

cd "$(dirname "$0")"
WHEELS=(aegis_devkit/wheels/ff_sdk-*-linux_aarch64.whl aegis_devkit/wheels/typing_extensions-*.whl)

echo "==> pinging $ROBOT_IP"
if ! ping -c 2 -t 3 "$ROBOT_IP" >/dev/null; then
  echo "Robot not reachable at $ROBOT_IP. Are you on its hotspot?"
  echo "Your gateway is: $(route -n get default 2>/dev/null | awk '/gateway/{print $2}')"
  echo "If that's the robot, rerun with ROBOT_IP=<that address>."
  exit 1
fi

# One shared ssh connection, so the password is asked only once.
SOCK="$(mktemp -u /tmp/aegis-ssh.XXXXXX)"
SSH=(ssh -o ControlMaster=auto -o ControlPath="$SOCK" -o ControlPersist=60)
trap '"${SSH[@]}" -O exit "$HOST" 2>/dev/null || true' EXIT

echo "==> copying files"
"${SSH[@]}" "$HOST" "mkdir -p $APP_DIR/wheels"
scp -o ControlPath="$SOCK" "${WHEELS[@]}" "$HOST:$APP_DIR/wheels/"
scp -o ControlPath="$SOCK" aegis_skills.py "$HOST:$APP_DIR/"

echo "==> installing SDK (skipped if already installed)"
"${SSH[@]}" "$HOST" "
  set -e
  [ -x $APP_DIR/venv/bin/python ] || python3 -m venv $APP_DIR/venv
  $APP_DIR/venv/bin/pip install -q --no-index --find-links $APP_DIR/wheels ff_sdk==0.1.0a10
  $APP_DIR/venv/bin/python -c 'import ff_sdk; print(\"ff_sdk\", ff_sdk.__version__)'
"

if [ "$SKILL" != "check" ]; then
  echo
  echo "!! '$SKILL' will MOVE the dog. 1 m clear floor all round, someone on the e-stop."
  read -r -p "Type yes to go: " ok
  [ "$ok" = "yes" ] || { echo "Aborted."; exit 1; }
fi

echo "==> running $SKILL"
# The robot's sdk_config.yaml expects the native link on 127.0.0.1; without
# this the SDK binds the hotspot address and check reports "native link down".
REMOTE_ENV="FF_SDK_AEGIS_HOST=${FF_SDK_AEGIS_HOST:-127.0.0.1}"
[ -n "${FF_SDK_AEGIS_VARIANT:-}" ] && REMOTE_ENV="$REMOTE_ENV FF_SDK_AEGIS_VARIANT=$FF_SDK_AEGIS_VARIANT"
"${SSH[@]}" -t "$HOST" "cd $APP_DIR && $REMOTE_ENV ./venv/bin/python -u aegis_skills.py $SKILL $*"
