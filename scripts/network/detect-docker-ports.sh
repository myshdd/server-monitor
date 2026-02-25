#!/bin/bash
# /usr/local/bin/detect-docker-ports.sh
# Динамическое определение портов Docker контейнеров

PORTS_FILE="/etc/docker-monitor-ports.conf"
TEMP_FILE="/tmp/docker-ports.tmp"

echo "# Автоматически сгенерировано $(date)" > "$TEMP_FILE"
echo "# Формат: протокол:порт" >> "$TEMP_FILE"
echo "" >> "$TEMP_FILE"

# Получаем список всех запущенных контейнеров
docker ps --format "{{.Names}}" | while read container; do
    # Получаем информацию о портах контейнера
    ports=$(docker inspect "$container" | jq -r '.[0].NetworkSettings.Ports | to_entries[] | "\(.key | split("/")[1]):\(.key | split("/")[0])"')
    
    if [ -n "$ports" ]; then
        echo "# Контейнер: $container" >> "$TEMP_FILE"
        echo "$ports" >> "$TEMP_FILE"
        echo "" >> "$TEMP_FILE"
    fi
done

# Обновляем файл если есть изменения
if ! cmp -s "$TEMP_FILE" "$PORTS_FILE" 2>/dev/null; then
    mv "$TEMP_FILE" "$PORTS_FILE"
    echo "Обновлены порты для мониторинга"
    
    # Перезапускаем мониторинг портов (если нужно)
    # systemctl restart port-monitor.service
else
    rm "$TEMP_FILE"
fi

# Вывод текущих портов
echo "Текущие порты Docker контейнеров:"
cat "$PORTS_FILE"
