"""
Сервис для выполнения тестов конфигураций
"""

import json
import yaml
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Optional, Any
import httpx

from app.models.config import (
    TestType, TestStatus, TestRequest, TestResult,
    TestResponse, TestResultsResponse, SyntaxTestResult,
    SemanticTestResult, FunctionalTestResult
)

logger = logging.getLogger(__name__)


class TestService:
    """Сервис для выполнения тестов конфигураций"""
    
    def __init__(self):
        self.active_tests: Dict[str, TestResultsResponse] = {}
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def run_tests(self, test_request: TestRequest) -> TestResponse:
        """Запуск тестов"""
        test_id = f"tst_{uuid.uuid4().hex[:8]}"
        
        test_response = TestResponse(
            test_id=test_id,
            status=TestStatus.PENDING,
            created_at=datetime.now(),
            repo=test_request.repo,
            commit=test_request.commit,
            tests=test_request.tests
        )
        
        # Инициализируем результаты тестов
        results = {}
        for test_type in test_request.tests:
            results[test_type] = TestResult(
                test_type=test_type,
                passed=False,
                errors=[],
                warnings=[]
            )
        
        self.active_tests[test_id] = TestResultsResponse(
            test_id=test_id,
            status=TestStatus.PENDING,
            passed=False,
            results=results,
            created_at=datetime.now()
        )
        
        # Запускаем тесты асинхронно
        logger.info(f"Starting tests {test_id} for repo {test_request.repo}, commit {test_request.commit}")
        
        return test_response
    
    async def get_test_results(self, test_id: str) -> Optional[TestResultsResponse]:
        """Получение результатов тестов"""
        return self.active_tests.get(test_id)
    
    async def execute_syntax_tests(self, files: List[Dict[str, Any]]) -> List[SyntaxTestResult]:
        """Выполнение синтаксических тестов"""
        results = []
        
        for file_data in files:
            file_path = file_data.get("path", "unknown")
            content = file_data.get("content", "")
            
            try:
                if file_path.endswith(".json"):
                    json.loads(content)
                    results.append(SyntaxTestResult(
                        file_path=file_path,
                        valid=True,
                        errors=[]
                    ))
                elif file_path.endswith((".yaml", ".yml")):
                    yaml.safe_load(content)
                    results.append(SyntaxTestResult(
                        file_path=file_path,
                        valid=True,
                        errors=[]
                    ))
                else:
                    # Для других типов файлов просто проверяем, что они не пустые
                    if content.strip():
                        results.append(SyntaxTestResult(
                            file_path=file_path,
                            valid=True,
                            errors=[]
                        ))
                    else:
                        results.append(SyntaxTestResult(
                            file_path=file_path,
                            valid=False,
                            errors=["File is empty"]
                        ))
            except json.JSONDecodeError as e:
                results.append(SyntaxTestResult(
                    file_path=file_path,
                    valid=False,
                    errors=[f"JSON parsing error: {str(e)}"]
                ))
            except yaml.YAMLError as e:
                results.append(SyntaxTestResult(
                    file_path=file_path,
                    valid=False,
                    errors=[f"YAML parsing error: {str(e)}"]
                ))
            except Exception as e:
                results.append(SyntaxTestResult(
                    file_path=file_path,
                    valid=False,
                    errors=[f"Unexpected error: {str(e)}"]
                ))
        
        return results
    
    async def execute_semantic_tests(self, files: List[Dict[str, Any]]) -> List[SemanticTestResult]:
        """Выполнение семантических тестов"""
        results = []
        
        # Здесь будет логика проверки ссылочной целостности
        # Пока возвращаем заглушку
        for file_data in files:
            file_path = file_data.get("path", "unknown")
            
            results.append(SemanticTestResult(
                file_path=file_path,
                valid=True,
                missing_references=[],
                duplicate_ids=[]
            ))
        
        return results
    
    async def execute_functional_tests(self, files: List[Dict[str, Any]]) -> List[FunctionalTestResult]:
        """Выполнение функциональных тестов"""
        results = []
        
        # Здесь будет интеграция с C17.4 Skill Tester
        # Пока возвращаем заглушку
        for file_data in files:
            file_path = file_data.get("path", "unknown")
            
            if "skill" in file_path.lower():
                results.append(FunctionalTestResult(
                    test_name=f"Skill test for {file_path}",
                    passed=True,
                    output="Skill test passed (stub)"
                ))
        
        return results
    
    async def health_check(self) -> bool:
        """Проверка здоровья сервиса"""
        try:
            # Проверяем, что можем создавать тесты
            test_id = f"health_{uuid.uuid4().hex[:4]}"
            logger.debug(f"Health check: created test ID {test_id}")
            return True
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False
    
    async def close(self):
        """Закрытие ресурсов"""
        await self.client.aclose()