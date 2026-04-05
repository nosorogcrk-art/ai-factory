"""
Репозиторий для работы с тестами и их результатами
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
import logging

from app.models.config import (
    TestType, TestStatus, TestRequest, TestResult,
    TestResponse, TestResultsResponse
)

logger = logging.getLogger(__name__)


class TestRepository:
    """Репозиторий для хранения результатов тестов"""
    
    def __init__(self, db_path: str = "test_results.db"):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Инициализация базы данных"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Таблица тестов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tests (
                id TEXT PRIMARY KEY,
                repo TEXT NOT NULL,
                commit_hash TEXT NOT NULL,
                status TEXT NOT NULL,
                passed BOOLEAN,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP,
                results_json TEXT
            )
        """)
        
        # Таблица результатов по типам тестов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                test_type TEXT NOT NULL,
                passed BOOLEAN NOT NULL,
                errors_json TEXT,
                warnings_json TEXT,
                duration_ms INTEGER,
                FOREIGN KEY (test_id) REFERENCES tests (id)
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"Database initialized at {self.db_path}")
    
    def save_test(self, test_response: TestResponse) -> bool:
        """Сохранение информации о тесте"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO tests (id, repo, commit_hash, status, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                test_response.test_id,
                test_response.repo,
                test_response.commit,
                test_response.status.value,
                test_response.created_at.isoformat()
            ))
            
            conn.commit()
            conn.close()
            logger.info(f"Test {test_response.test_id} saved to database")
            return True
        except Exception as e:
            logger.error(f"Failed to save test {test_response.test_id}: {e}")
            return False
    
    def update_test_results(self, test_id: str, results: TestResultsResponse) -> bool:
        """Обновление результатов теста"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Обновляем основную информацию о тесте
            cursor.execute("""
                UPDATE tests 
                SET status = ?, passed = ?, completed_at = ?, results_json = ?
                WHERE id = ?
            """, (
                results.status.value,
                results.passed,
                results.completed_at.isoformat() if results.completed_at else None,
                json.dumps({
                    test_type: {
                        "passed": result.passed,
                        "errors": result.errors,
                        "warnings": result.warnings,
                        "duration_ms": result.duration_ms
                    }
                    for test_type, result in results.results.items()
                }),
                test_id
            ))
            
            # Удаляем старые результаты
            cursor.execute("DELETE FROM test_results WHERE test_id = ?", (test_id,))
            
            # Сохраняем новые результаты
            for test_type, result in results.results.items():
                cursor.execute("""
                    INSERT INTO test_results (test_id, test_type, passed, errors_json, warnings_json, duration_ms)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    test_id,
                    test_type.value,
                    result.passed,
                    json.dumps(result.errors),
                    json.dumps(result.warnings),
                    result.duration_ms
                ))
            
            conn.commit()
            conn.close()
            logger.info(f"Test results for {test_id} updated in database")
            return True
        except Exception as e:
            logger.error(f"Failed to update test results for {test_id}: {e}")
            return False
    
    def get_test(self, test_id: str) -> Optional[TestResultsResponse]:
        """Получение теста по ID"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, repo, commit_hash, status, passed, created_at, completed_at, results_json
                FROM tests WHERE id = ?
            """, (test_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return None
            
            test_id, repo, commit_hash, status_str, passed, created_at_str, completed_at_str, results_json = row
            
            # Парсим результаты
            results_dict = json.loads(results_json) if results_json else {}
            results = {}
            
            for test_type_str, result_data in results_dict.items():
                test_type = TestType(test_type_str)
                results[test_type] = TestResult(
                    test_type=test_type,
                    passed=result_data.get("passed", False),
                    errors=result_data.get("errors", []),
                    warnings=result_data.get("warnings", []),
                    duration_ms=result_data.get("duration_ms")
                )
            
            return TestResultsResponse(
                test_id=test_id,
                status=TestStatus(status_str),
                passed=bool(passed),
                results=results,
                created_at=datetime.fromisoformat(created_at_str),
                completed_at=datetime.fromisoformat(completed_at_str) if completed_at_str else None
            )
        except Exception as e:
            logger.error(f"Failed to get test {test_id}: {e}")
            return None
    
    def get_recent_tests(self, limit: int = 10) -> List[TestResultsResponse]:
        """Получение последних тестов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, repo, commit_hash, status, passed, created_at, completed_at, results_json
                FROM tests 
                ORDER BY created_at DESC 
                LIMIT ?
            """, (limit,))
            
            rows = cursor.fetchall()
            conn.close()
            
            tests = []
            for row in rows:
                test_id, repo, commit_hash, status_str, passed, created_at_str, completed_at_str, results_json = row
                
                # Парсим результаты
                results_dict = json.loads(results_json) if results_json else {}
                results = {}
                
                for test_type_str, result_data in results_dict.items():
                    test_type = TestType(test_type_str)
                    results[test_type] = TestResult(
                        test_type=test_type,
                        passed=result_data.get("passed", False),
                        errors=result_data.get("errors", []),
                        warnings=result_data.get("warnings", []),
                        duration_ms=result_data.get("duration_ms")
                    )
                
                tests.append(TestResultsResponse(
                    test_id=test_id,
                    status=TestStatus(status_str),
                    passed=bool(passed),
                    results=results,
                    created_at=datetime.fromisoformat(created_at_str),
                    completed_at=datetime.fromisoformat(completed_at_str) if completed_at_str else None
                ))
            
            return tests
        except Exception as e:
            logger.error(f"Failed to get recent tests: {e}")
            return []
    
    def cleanup_old_tests(self, days: int = 30) -> int:
        """Очистка старых тестов"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Удаляем тесты старше указанного количества дней
            cursor.execute("""
                DELETE FROM tests 
                WHERE created_at < datetime('now', ?)
            """, (f"-{days} days",))
            
            deleted_count = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            logger.info(f"Cleaned up {deleted_count} old tests")
            return deleted_count
        except Exception as e:
            logger.error(f"Failed to cleanup old tests: {e}")
            return 0