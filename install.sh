#!/usr/bin/env bash
set -euo pipefail

read -rp "TELEGRAM BOT TOKEN: " TOKEN
read -rp "SUDO ADMIN IDs (comma-separated, e.g. 123,456) [optional]: " SUDO_IN
read -rp "NORMAL ADMIN IDs (comma-separated) [optional]: " NORMAL_IN

APP_DIR="/root/joyu_bot"
PY_FILE="${APP_DIR}/joyu-bot.py"
LOG_FILE="${APP_DIR}/joyu.log"
SERVICE_FILE="/etc/systemd/system/joyu_bot.service"
PYBIN="$(command -v python3 || true)"

if [[ -z "${PYBIN}" ]]; then
  apt-get update -y
  apt-get install -y python3 python3-pip
  PYBIN="$(command -v python3)"
fi

mkdir -p "${APP_DIR}"
touch "${LOG_FILE}"

pip3 install --upgrade pip >/dev/null
pip3 install "python-telegram-bot==13.15" >/dev/null

if [[ ! -f "${PY_FILE}" ]]; then
  echo "ERROR: ${PY_FILE} not found. Put your bot code there and re-run."
  exit 1
fi

to_set() {
  local raw="$1"
  raw="$(echo "$raw" | tr -d ' ')"
  if [[ -z "$raw" ]]; then
    echo "set()"
    return
  fi
  IFS=',' read -r -a arr <<< "$raw"
  local items=()
  for a in "${arr[@]}"; do
    [[ -n "$a" ]] && items+=("$a")
  done
  if [[ "${#items[@]}" -eq 0 ]]; then
    echo "set()"
  else
    printf "{%s}\n" "$(IFS=,; echo "${items[*]}")"
  fi
}

SUDO_SET="$(to_set "${SUDO_IN:-}")"
NORMAL_SET="$(to_set "${NORMAL_IN:-}")"

sed -i -E "s|^TOKEN\s*=\s*\".*\"|TOKEN = \"${TOKEN}\"|g" "${PY_FILE}"

if grep -qE '^SUDO_ADMINS\s*=' "${PY_FILE}"; then
  sed -i -E "s|^SUDO_ADMINS\s*=.*|SUDO_ADMINS = ${SUDO_SET}|g" "${PY_FILE}"
else
  sed -i '1iSUDO_ADMINS = set()' "${PY_FILE}"
  sed -i -E "s|^SUDO_ADMINS\s*=.*|SUDO_ADMINS = ${SUDO_SET}|g" "${PY_FILE}"
fi

if grep -qE '^NORMAL_ADMINS\s*=' "${PY_FILE}"; then
  sed -i -E "s|^NORMAL_ADMINS\s*=.*|NORMAL_ADMINS = ${NORMAL_SET}|g" "${PY_FILE}"
else
  sed -i '1iNORMAL_ADMINS = set()' "${PY_FILE}"
  sed -i -E "s|^NORMAL_ADMINS\s*=.*|NORMAL_ADMINS = ${NORMAL_SET}|g" "${PY_FILE}"
fi

cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Joyu Telegram Bot
After=network.target

[Service]
WorkingDirectory=${APP_DIR}
ExecStart=${PYBIN} ${PY_FILE}
Restart=always
RestartSec=5
User=root
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable --now joyu_bot
systemctl status joyu_bot --no-pager || true
echo
echo "Logs (tail):"
journalctl -u joyu_bot -n 50 --no-pager || true