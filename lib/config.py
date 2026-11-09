#!/usr/bin/env python3
# /opt/server-monitor/lib/config.py
# Библиотека для загрузки конфигурации в Python-скриптах

import json
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Пути к конфигурационным файлам
CONFIG_DIR = Path("/opt/server-monitor/config")
SETTINGS_FILE = CONFIG_DIR / "settings.json"
SECRETS_FILE = CONFIG_DIR / "secrets.json"
PATHS_FILE = CONFIG_DIR / "paths.json"


class ConfigError(Exception):
    """Ошибка загрузки конфигурации"""
    pass


class Config:
    """Класс для работы с конфигурацией"""
    
    def __init__(self):
        self._settings = {}
        self._secrets = {}
        self._paths = {}
        self._load_all()
    
    def _load_json(self, filepath: Path) -> dict:
        """Загрузка JSON файла"""
        if not filepath.exists():
            raise ConfigError(f"Конфигурационный файл не найден: {filepath}")
        
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigError(f"Ошибка парсинга JSON в {filepath}: {e}")
        except Exception as e:
            raise ConfigError(f"Ошибка чтения {filepath}: {e}")
    
    def _load_all(self):
        """Загрузка всех конфигурационных файлов"""
        try:
            self._settings = self._load_json(SETTINGS_FILE)
            self._secrets = self._load_json(SECRETS_FILE)
            self._paths = self._load_json(PATHS_FILE)
        except ConfigError as e:
            print(f"❌ {e}", file=sys.stderr)
            print(f"💡 Запустите: init-server-monitor-config.sh", file=sys.stderr)
            raise
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """
        Получить значение из settings.json
        
        Args:
            key: Путь к значению через точку, например "monitoring.check_interval"
            default: Значение по умолчанию
            
        Returns:
            Значение настройки или default
        """
        keys = key.split('.')
        value = self._settings
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def get_secret(self, key: str) -> Optional[str]:
        """
        Получить секрет из secrets.json
        
        Args:
            key: Путь к значению через точку, например "telegram.admin_bot_token"
            
        Returns:
            Значение секрета или None
        """
        keys = key.split('.')
        value = self._secrets
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        
        return value
    
    def get_path(self, key: str, default: str = "") -> str:
        """
        Получить путь из paths.json
        
        Args:
            key: Путь к значению через точку, например "logs.fail2ban"
            default: Значение по умолчанию
            
        Returns:
            Путь к файлу/директории
        """
        keys = key.split('.')
        value = self._paths
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return str(value) if value else default
    
    # ============================================
    # ПРЕДЗАГРУЖЕННЫЕ СВОЙСТВА ДЛЯ УДОБСТВА
    # ============================================
    
    @property
    def telegram_admin_token(self) -> str:
        """Токен admin бота"""
        token = self.get_secret("telegram.admin_bot_token")
        if not token or token.startswith("ЗАМЕНИТЕ"):
            raise ConfigError("Telegram admin_bot_token не настроен в secrets.json")
        return token
    
    @property
    def telegram_monitor_token(self) -> str:
        """Токен monitor бота"""
        token = self.get_secret("telegram.monitor_bot_token")
        if not token or token.startswith("ЗАМЕНИТЕ"):
            raise ConfigError("Telegram monitor_bot_token не настроен в secrets.json")
        return token
    
    @property
    def telegram_chat_id(self) -> int:
        """Chat ID для уведомлений"""
        chat_id = self.get_secret("telegram.chat_id")
        if not chat_id or chat_id == 0:
            raise ConfigError("Telegram chat_id не настроен в secrets.json")
        return int(chat_id)
    
    @property
    def check_interval(self) -> int:
        """Интервал проверки мониторинга (секунды)"""
        return self.get_setting("monitoring.check_interval", 180)
    
    @property
    def cpu_threshold(self) -> int:
        """Порог CPU (%)"""
        return self.get_setting("monitoring.thresholds.cpu", 80)
    
    @property
    def ram_threshold(self) -> int:
        """Порог RAM (%)"""
        return self.get_setting("monitoring.thresholds.ram", 90)
    
    @property
    def disk_threshold(self) -> int:
        """Порог диска (%)"""
        return self.get_setting("monitoring.thresholds.disk", 95)
    
    @property
    def log_dir(self) -> str:
        """Директория логов"""
        return self.get_path("logs.base_dir", "/var/log/server-monitor")
    
    @property
    def network_stats_file(self) -> str:
        """Файл сетевой статистики"""
        return self.get_path("data.network_stats_file", "/opt/server-monitor/data/stats.json")


# Глобальный экземпляр конфигурации
_config_instance = None


def get_config() -> Config:
    """
    Получить глобальный экземпляр конфигурации (singleton)
    
    Returns:
        Объект Config
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


# ============================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ============================================

def ensure_dir(path: str) -> None:
    """
    Создать директорию если не существует
    
    Args:
        path: Путь к директории
    """
    Path(path).mkdir(parents=True, exist_ok=True)


def setup_logging(name: str, log_file: Optional[str] = None):
    """
    Настройка логирования для Python-скриптов
    
    Args:
        name: Имя логгера (обычно __name__)
        log_file: Путь к файлу лога (опционально)
        
    Returns:
        Настроенный logger
    """
    import logging
    
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Формат
    formatter = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Консольный handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Файловый handler (если указан)
    if log_file:
        ensure_dir(os.path.dirname(log_file))
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    return logger


# ============================================
# ПРИМЕР ИСПОЛЬЗОВАНИЯ
# ============================================

if __name__ == "__main__":
    # Тестирование загрузки конфигурации
    try:
        config = get_config()
        
        print("✅ Конфигурация успешно загружена\n")
        
        print("📊 Примеры значений:")
        print(f"  Check interval: {config.check_interval} сек")
        print(f"  CPU threshold: {config.cpu_threshold}%")
        print(f"  RAM threshold: {config.ram_threshold}%")
        print(f"  Chat ID: {config.telegram_chat_id}")
        print(f"  Log dir: {config.log_dir}")
        print(f"  Network stats: {config.network_stats_file}")
        
    except ConfigError as e:
        print(f"❌ Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
