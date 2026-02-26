#!/bin/bash
# Скрипт отправки уведомлений fail2ban в Telegram
# Использует централизованную конфигурацию

# Загружаем конфигурацию
source /usr/local/lib/server-monitor/load-config.sh

# Получаем токен и chat_id
TOKEN=$(get_secret "telegram.monitor_bot_token")
CHAT_ID=$(get_secret "telegram.chat_id")

# Проверяем что токен и chat_id получены
if [[ -z "$TOKEN" ]] || [[ -z "$CHAT_ID" ]]; then
    echo "Ошибка: не удалось получить токен или chat_id из конфигурации" >&2
    exit 1
fi

ACTION="$1"
JAIL="$2"
IP="$3"

if [ "$ACTION" == "ban" ]; then
    MESSAGE="🚨 *IP заблокирован*%0AСервер: $(hostname)%0AТюрьма: \`$JAIL\`%0AIP: \`$IP\`%0AВремя: $(date '+%d.%m.%Y %H:%M:%S')"
elif [ "$ACTION" == "unban" ]; then
    MESSAGE="🔓 *IP разблокирован*%0AСервер: $(hostname)%0AТюрьма: \`$JAIL\`%0AIP: \`$IP\`%0AВремя: $(date '+%d.%m.%Y %H:%M:%S')"
else
    exit 0
fi

curl -s -X POST "https://api.telegram.org/bot${TOKEN}/sendMessage" \
    -d "chat_id=${CHAT_ID}" \
    -d "text=${MESSAGE}" \
    -d "parse_mode=Markdown" > /dev/null
