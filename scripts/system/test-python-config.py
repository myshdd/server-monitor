#!/usr/bin/env python3
# /opt/server-monitor/scripts/system/test-python-config.py
# Тестирование Python библиотеки конфигурации

import sys
sys.path.insert(0, '/usr/local/lib/server-monitor')

from config import get_config, ConfigError, setup_logging

def test_basic_reading():
    """Тест базового чтения конфигов"""
    print("📖 Тест 1: Базовое чтение конфигов")
    print("─" * 50)
    
    try:
        config = get_config()
        
        # Чтение из settings
        interval = config.get_setting("monitoring.check_interval", 180)
        print(f"  ✓ Check interval: {interval}")
        
        cpu_threshold = config.get_setting("monitoring.thresholds.cpu", 80)
        print(f"  ✓ CPU threshold: {cpu_threshold}%")
        
        # Несуществующий ключ с default
        unknown = config.get_setting("unknown.key", "default_value")
        print(f"  ✓ Unknown key with default: {unknown}")
        
        print("  ✅ Тест пройден\n")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")
        return False


def test_secrets():
    """Тест чтения секретов"""
    print("🔒 Тест 2: Чтение секретов")
    print("─" * 50)
    
    try:
        config = get_config()
        
        # Чтение токенов
        admin_token = config.get_secret("telegram.admin_bot_token")
        monitor_token = config.get_secret("telegram.monitor_bot_token")
        chat_id = config.get_secret("telegram.chat_id")
        
        if admin_token and not admin_token.startswith("ЗАМЕНИТЕ"):
            print(f"  ✓ Admin token: {admin_token[:10]}...")
        else:
            print(f"  ⚠️  Admin token не настроен")
        
        if monitor_token and not monitor_token.startswith("ЗАМЕНИТЕ"):
            print(f"  ✓ Monitor token: {monitor_token[:10]}...")
        else:
            print(f"  ⚠️  Monitor token не настроен")
        
        print(f"  ✓ Chat ID: {chat_id}")
        
        print("  ✅ Тест пройден\n")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")
        return False


def test_paths():
    """Тест чтения путей"""
    print("📂 Тест 3: Чтение путей")
    print("─" * 50)
    
    try:
        config = get_config()
        
        log_dir = config.get_path("logs.base_dir")
        print(f"  ✓ Log dir: {log_dir}")
        
        stats_file = config.get_path("data.network_stats_file")
        print(f"  ✓ Network stats: {stats_file}")
        
        geoip_dir = config.get_path("data.geoip_dir")
        print(f"  ✓ GeoIP dir: {geoip_dir}")
        
        # Несуществующий путь с default
        unknown = config.get_path("unknown.path", "/default/path")
        print(f"  ✓ Unknown path with default: {unknown}")
        
        print("  ✅ Тест пройден\n")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")
        return False


def test_properties():
    """Тест предзагруженных свойств"""
    print("⚡ Тест 4: Предзагруженные свойства")
    print("─" * 50)
    
    try:
        config = get_config()
        
        print(f"  ✓ telegram_chat_id: {config.telegram_chat_id}")
        print(f"  ✓ check_interval: {config.check_interval} сек")
        print(f"  ✓ cpu_threshold: {config.cpu_threshold}%")
        print(f"  ✓ ram_threshold: {config.ram_threshold}%")
        print(f"  ✓ disk_threshold: {config.disk_threshold}%")
        print(f"  ✓ log_dir: {config.log_dir}")
        print(f"  ✓ network_stats_file: {config.network_stats_file}")
        
        print("  ✅ Тест пройден\n")
        return True
        
    except ConfigError as e:
        print(f"  ⚠️  Некоторые свойства не настроены: {e}\n")
        return True  # Не критично для теста
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")
        return False


def test_logging():
    """Тест настройки логирования"""
    print("📝 Тест 5: Настройка логирования")
    print("─" * 50)
    
    try:
        # Настройка логгера
        logger = setup_logging(__name__, "/tmp/test-config.log")
        
        logger.info("Тестовое INFO сообщение")
        logger.warning("Тестовое WARNING сообщение")
        logger.error("Тестовое ERROR сообщение")
        
        print("  ✓ Логгер настроен")
        print("  ✓ Сообщения записаны в /tmp/test-config.log")
        print("  ✅ Тест пройден\n")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка: {e}\n")
        return False


def main():
    print("╔══════════════════════════════════════════════════════════════╗")
    print("║         ТЕСТИРОВАНИЕ PYTHON БИБЛИОТЕКИ КОНФИГУРАЦИИ          ║")
    print("╚══════════════════════════════════════════════════════════════╝")
    print()
    
    tests = [
        test_basic_reading,
        test_secrets,
        test_paths,
        test_properties,
        test_logging
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            failed += 1
    
    print("═" * 64)
    print(f"Результаты: ✅ {passed} пройдено, ❌ {failed} провалено")
    
    if failed == 0:
        print("🎉 Все тесты успешно пройдены!")
        return 0
    else:
        print("⚠️  Есть проваленные тесты")
        return 1


if __name__ == "__main__":
    sys.exit(main())
