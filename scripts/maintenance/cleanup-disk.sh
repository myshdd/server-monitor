#!/bin/bash
#===============================================================================
# Скрипт автоматической очистки диска
# Расположение: ~/cleanup-disk.sh
#===============================================================================

set -e

echo "=========================================="
echo "  Очистка диска"
echo "=========================================="
echo ""

# Показываем текущее состояние
echo "=== Использование диска до очистки ==="
df -h / | grep -v Filesystem
echo ""

# 1. Journal логи
echo "1. Очистка journal логов (оставляем последние 7 дней)..."
journalctl --vacuum-time=7d
echo ""

# 2. APT кэш
echo "2. Очистка APT кэша..."
apt-get clean -y > /dev/null 2>&1
apt-get autoclean -y > /dev/null 2>&1
apt-get autoremove -y > /dev/null 2>&1
echo "✓ APT кэш очищен"
echo ""

# 3. Docker образы (закомментировано для безопасности)
# echo "3. Очистка неиспользуемых Docker образов..."
# docker image prune -a -f
# echo ""

# 4. Старые ядра (если есть)
echo "3. Проверка старых ядер..."
OLD_KERNELS=$(dpkg -l | grep '^rc.*linux-image' | awk '{print $2}')
if [ -n "$OLD_KERNELS" ]; then
    echo "Удаление старых ядер..."
    apt-get purge -y $OLD_KERNELS > /dev/null 2>&1
    apt-get autoremove --purge -y > /dev/null 2>&1
    echo "✓ Старые ядра удалены"
else
    echo "✓ Старых ядер не найдено"
fi
echo ""

# 5. Архивирование старых логов
echo "4. Архивирование старых логов (старше 30 дней)..."
ARCHIVED=$(find /var/log -type f -name "*.log" -mtime +30 -exec gzip {} \; -print 2>/dev/null | wc -l)
echo "✓ Заархивировано файлов: $ARCHIVED"
echo ""

# 6. Удаление очень старых архивов
echo "5. Удаление архивов логов старше 60 дней..."
DELETED=$(find /var/log -type f -name "*.gz" -mtime +60 -delete -print 2>/dev/null | wc -l)
echo "✓ Удалено файлов: $DELETED"
echo ""

# 7. Специфичные логи
echo "6. Ротация больших логов..."

# Ротация monit.log если больше 50 MB
if [ -f /var/log/monit.log ]; then
    SIZE=$(stat -f%z /var/log/monit.log 2>/dev/null || stat -c%s /var/log/monit.log 2>/dev/null)
    if [ "$SIZE" -gt 52428800 ]; then
        mv /var/log/monit.log /var/log/monit.log.old
        touch /var/log/monit.log
        chown root:adm /var/log/monit.log
        chmod 640 /var/log/monit.log
        gzip /var/log/monit.log.old
        echo "✓ monit.log ротирован"
    fi
fi

# Очистка f2b-analysis.log если больше 50 MB
if [ -f /var/log/f2b-analysis.log ]; then
    SIZE=$(stat -c%s /var/log/f2b-analysis.log 2>/dev/null)
    if [ "$SIZE" -gt 52428800 ]; then
        tail -10000 /var/log/f2b-analysis.log > /var/log/f2b-analysis.log.tmp
        mv /var/log/f2b-analysis.log.tmp /var/log/f2b-analysis.log
        echo "✓ f2b-analysis.log усечён до последних 10000 строк"
    fi
fi
echo ""

# Итоговое состояние
echo "=========================================="
echo "  Результат"
echo "=========================================="
df -h / | grep -v Filesystem
echo ""
echo "Освобождено: $(df -h / | awk 'NR==2 {print $4}')"
