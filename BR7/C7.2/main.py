"""
C7.2 Handover (Аргус) - точка входа
Основной файл находится в api.py, этот файл создан для совместимости с промтом.
"""

from api import app, background_build_trigger, check_and_build_queue

# Экспортируем всё из api для совместимости
__all__ = ['app', 'background_build_trigger', 'check_and_build_queue']