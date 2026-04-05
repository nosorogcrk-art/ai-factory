import difflib
import logging
from typing import List, Optional
from datetime import datetime

from app.models.config import (
    ConfigCreate, ConfigResponse, ConfigContentResponse, 
    ConfigDiffResponse, RollbackRequest
)
from app.repositories.config_repository import ConfigRepository


logger = logging.getLogger(__name__)


class ConfigService:
    """Сервисный слой для управления версиями конфигураций"""
    
    def __init__(self, repository: Optional[ConfigRepository] = None):
        """Инициализация сервиса"""
        self.repository = repository or ConfigRepository()
    
    def create_config(self, config_data: ConfigCreate) -> ConfigContentResponse:
        """
        Создание новой версии конфигурации
        
        Args:
            config_data: Данные для создания конфигурации
            
        Returns:
            Созданная конфигурация
            
        Raises:
            ValueError: Если версия уже существует
        """
        logger.info(f"Создание новой версии конфигурации: {config_data.version}")
        
        config_id = self.repository.save_config(
            version=config_data.version,
            config_type=config_data.config_type,
            content=config_data.content,
            description=config_data.description
        )
        
        config = self.repository.get_config_by_id(config_id)
        if not config:
            raise RuntimeError(f"Не удалось получить созданную конфигурацию с ID {config_id}")
        
        logger.info(f"Конфигурация создана: {config.version} (ID: {config.id})")
        return config
    
    def get_config(self, version: str) -> Optional[ConfigContentResponse]:
        """
        Получение конфигурации по версии
        
        Args:
            version: Версия конфигурации
            
        Returns:
            Конфигурация или None если не найдена
        """
        logger.debug(f"Получение конфигурации: {version}")
        return self.repository.get_config_by_version(version)
    
    def get_all_configs(self, limit: int = 100, offset: int = 0) -> List[ConfigResponse]:
        """
        Получение списка всех конфигураций
        
        Args:
            limit: Максимальное количество записей
            offset: Смещение
            
        Returns:
            Список конфигураций
        """
        logger.debug(f"Получение списка конфигураций (limit={limit}, offset={offset})")
        return self.repository.get_all_configs(limit, offset)
    
    def get_config_versions(self) -> List[str]:
        """
        Получение списка всех версий
        
        Returns:
            Список версий
        """
        return self.repository.get_config_versions()
    
    def get_latest_config(self) -> Optional[ConfigContentResponse]:
        """
        Получение последней версии конфигурации
        
        Returns:
            Последняя конфигурация или None если нет конфигураций
        """
        logger.debug("Получение последней версии конфигурации")
        return self.repository.get_latest_config()
    
    def delete_config(self, version: str) -> bool:
        """
        Удаление конфигурации по версии
        
        Args:
            version: Версия для удаления
            
        Returns:
            True если удалено, False если не найдено
        """
        logger.info(f"Удаление конфигурации: {version}")
        return self.repository.delete_config(version)
    
    def get_diff(self, from_version: str, to_version: str) -> Optional[ConfigDiffResponse]:
        """
        Получение разницы между двумя версиями
        
        Args:
            from_version: Исходная версия
            to_version: Целевая версия
            
        Returns:
            Разница между версиями или None если версии не найдены
        """
        logger.info(f"Получение разницы между версиями: {from_version} -> {to_version}")
        
        diff_result = self.repository.get_diff(from_version, to_version)
        if not diff_result:
            return None
        
        from_content, to_content, changes_count = diff_result
        
        # Генерация diff в формате unified diff
        diff_lines = list(difflib.unified_diff(
            from_content.splitlines(keepends=True),
            to_content.splitlines(keepends=True),
            fromfile=f"a/{from_version}",
            tofile=f"b/{to_version}",
            lineterm='\n'
        ))
        
        diff_text = ''.join(diff_lines)
        
        return ConfigDiffResponse(
            from_version=from_version,
            to_version=to_version,
            diff=diff_text,
            changes_count=changes_count
        )
    
    def rollback_to_version(self, rollback_request: RollbackRequest) -> Optional[ConfigContentResponse]:
        """
        Откат к указанной версии
        
        Args:
            rollback_request: Запрос на откат
            
        Returns:
            Новая версия конфигурации после отката или None если целевая версия не найдена
        """
        target_version = rollback_request.target_version
        if not target_version:
            logger.error("Целевая версия не указана в запросе на откат")
            return None
            
        logger.info(f"Откат к версии: {target_version}")
        
        # Получение целевой конфигурации
        target_config = self.repository.get_config_by_version(target_version)
        if not target_config:
            logger.error(f"Целевая версия не найдена: {target_version}")
            return None
        
        if rollback_request.create_new_version:
            # Создание новой версии с содержимым целевой версии
            new_version = f"{target_config.version}-rollback-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
            
            config_data = ConfigCreate(
                content=target_config.content,
                version=new_version,
                description=f"Откат к версии {target_config.version}",
                config_type=target_config.config_type
            )
            
            return self.create_config(config_data)
        else:
            # Просто возвращаем целевую конфигурацию
            return target_config
    
    def health_check(self) -> dict:
        """
        Проверка здоровья сервиса
        
        Returns:
            Словарь с информацией о здоровье сервиса
        """
        db_healthy = self.repository.health_check()
        version_count = self.repository.get_count()
        
        return {
            "database_status": "healthy" if db_healthy else "unhealthy",
            "version_count": version_count,
            "timestamp": datetime.now()
        }