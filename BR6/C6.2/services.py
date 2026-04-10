import os
import subprocess
import tempfile
from typing import Optional, Dict, Any

import httpx

from models import Violation, Severity, ReviewResponse


class SemanticAuditor:
    """Семантический аудитор для проверки кода на соответствие Золотому стандарту"""
    
    def __init__(self):
        self.rules = [
            ("has_tests", self._check_has_tests, Severity.ERROR),
            ("has_healthcheck", self._check_has_healthcheck, Severity.ERROR),
            ("has_passport", self._check_has_passport, Severity.ERROR),
            ("mypy_compliance", self._check_mypy, Severity.WARNING),
            ("ruff_compliance", self._check_ruff, Severity.WARNING),
        ]
    
    async def review_file(self, file_path: str, content: Optional[str] = None) -> ReviewResponse:
        """Проверяет файл на соответствие Золотому стандарту"""
        violations = []
        suggestions = []
        
        # Если передан контент, создаём временный файл
        if content is not None:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
                f.write(content)
                temp_file = f.name
            actual_path = temp_file
        else:
            if not os.path.exists(file_path):
                return ReviewResponse(
                    status="rework",
                    violations=[Violation(
                        rule="file_exists",
                        message=f"Файл не найден: {file_path}",
                        severity=Severity.ERROR
                    )],
                    suggestions=["Убедитесь, что путь к файлу корректен"]
                )
            actual_path = file_path
        
        try:
            # Проверяем по всем правилам
            for rule_name, check_func, default_severity in self.rules:
                try:
                    result = check_func(actual_path)
                    if result is not None:
                        violations.append(Violation(
                            rule=rule_name,
                            message=result,
                            severity=default_severity
                        ))
                except Exception as e:
                    violations.append(Violation(
                        rule=rule_name,
                        message=f"Ошибка при проверке {rule_name}: {str(e)}",
                        severity=Severity.WARNING
                    ))
            
            # Генерируем предложения на основе нарушений
            for violation in violations:
                if violation.rule == "has_tests":
                    suggestions.append("Добавьте тесты с использованием pytest")
                elif violation.rule == "has_healthcheck":
                    suggestions.append("Добавьте эндпоинт /health в FastAPI приложение")
                elif violation.rule == "has_passport":
                    suggestions.append("Создайте паспорт контейнера в формате .md")
                elif violation.rule == "mypy_compliance":
                    suggestions.append("Исправьте ошибки типизации с помощью mypy")
                elif violation.rule == "ruff_compliance":
                    suggestions.append("Исправьте стилистические ошибки с помощью ruff")
            
            # Определяем статус
            has_errors = any(v.severity == Severity.ERROR for v in violations)
            status = "approved" if not has_errors else "rework"
            
            return ReviewResponse(
                status=status,
                violations=violations,
                suggestions=list(set(suggestions))  # Убираем дубликаты
            )
            
        finally:
            # Удаляем временный файл если он был создан
            if content is not None and os.path.exists(actual_path):
                os.unlink(actual_path)
    
    def _check_has_tests(self, file_path: str) -> Optional[str]:
        """Проверяет наличие тестов"""
        dir_path = os.path.dirname(file_path)
        test_dir = os.path.join(dir_path, "tests")
        
        # Проверяем наличие папки tests
        if not os.path.exists(test_dir):
            return "Папка tests не найдена"
        
        # Проверяем наличие файлов тестов
        test_files = [f for f in os.listdir(test_dir) if f.startswith("test_") and f.endswith(".py")]
        if not test_files:
            return "Нет файлов тестов (test_*.py) в папке tests"
        
        return None
    
    def _check_has_healthcheck(self, file_path: str) -> Optional[str]:
        """Проверяет наличие healthcheck эндпоинта"""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Простая проверка на наличие /health в коде
            if '/health' not in content and 'healthcheck' not in content.lower():
                return "Не найден эндпоинт /health или healthcheck"
            
            return None
        except Exception:
            return "Не удалось прочитать файл для проверки healthcheck"
    
    def _check_has_passport(self, file_path: str) -> Optional[str]:
        """Проверяет наличие паспорта контейнера"""
        dir_path = os.path.dirname(file_path)
        
        # Ищем файлы .md в той же директории
        md_files = [f for f in os.listdir(dir_path) if f.endswith('.md')]
        
        # Проверяем, есть ли файл с именем контейнера (C6.2.md или подобное)
        container_name = os.path.basename(dir_path)
        expected_name = f"{container_name}.md"
        
        if expected_name not in md_files:
            return f"Не найден паспорт контейнера {expected_name}"
        
        return None
    
    def _check_mypy(self, file_path: str) -> Optional[str]:
        """Проверяет код с помощью mypy"""
        try:
            result = subprocess.run(
                ['mypy', '--ignore-missing-imports', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Берем только первые 3 ошибки чтобы не перегружать вывод
                errors = result.stderr.split('\n')[:3]
                error_summary = '; '.join(errors)
                return f"Обнаружены ошибки типизации: {error_summary}"
            
            return None
        except subprocess.TimeoutExpired:
            return "Проверка mypy превысила время ожидания"
        except Exception as e:
            return f"Ошибка при запуске mypy: {str(e)}"
    
    def _check_ruff(self, file_path: str) -> Optional[str]:
        """Проверяет код с помощью ruff"""
        try:
            result = subprocess.run(
                ['ruff', 'check', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                # Берем только первые 3 ошибки
                errors = result.stdout.split('\n')[:3]
                error_summary = '; '.join(errors)
                return f"Обнаружены стилистические ошибки: {error_summary}"
            
            return None
        except subprocess.TimeoutExpired:
            return "Проверка ruff превысила время ожидания"
        except Exception as e:
            return f"Ошибка при запуске ruff: {str(e)}"


async def review_code(code: str) -> Dict[str, Any]:
    """
    Вызывает навык code_review через C7.4 /execute.
    Возвращает словарь с полями passed, score, issues, suggestions.
    """
    url = "http://skill-integrator:8090/execute"
    payload = {
        "task_type": "code_review",
        "context": {
            "code": code,
            "language": "python",
            "standards": "Золотой стандарт 5.0"
        }
    }
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            # Формат ответа C7.4: {"result": {...}, "skill_id": "...", "warnings": []}
            result = data.get("result", {})
            return result
    except Exception:
        # Заглушка на случай недоступности сервиса
        return {
            "passed": False,
            "score": 0,
            "issues": ["Сервис code_review временно недоступен"],
            "suggestions": ["Проверьте доступность сервиса skill-integrator:8090"]
        }
