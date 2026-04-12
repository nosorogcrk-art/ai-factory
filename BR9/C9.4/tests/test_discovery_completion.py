import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from llm_client import _parse_l2_response
import services
import handlers

@pytest.mark.asyncio
async def test_parse_l2_response_completed_format():
    """Тест парсинга ответа с completed: true и l2."""
    # Формат с completed: true
    response = '''{
        "completed": true,
        "l2": {
            "title": "Telegram Parser",
            "description": "Monitor company mentions in Telegram",
            "requirements": ["Parse messages", "Filter by keywords", "Send alerts"],
            "technical_specs": {"stack": "Python", "database": "none"}
        }
    }'''
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == True
    assert isinstance(l2_data, dict)
    assert l2_data["title"] == "Telegram Parser"
    assert l2_data["description"] == "Monitor company mentions in Telegram"
    assert len(l2_data["requirements"]) == 3
    assert l2_data["technical_specs"]["stack"] == "Python"

@pytest.mark.asyncio
async def test_parse_l2_response_direct_format():
    """Тест парсинга прямого L2 формата (старый формат)."""
    # Прямой L2 формат
    response = '''{
        "title": "Test Project",
        "description": "Test description",
        "requirements": ["Req1", "Req2"],
        "technical_specs": {"stack": "Python"}
    }'''
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == True
    assert isinstance(l2_data, dict)
    assert l2_data["title"] == "Test Project"
    assert l2_data["description"] == "Test description"
    assert len(l2_data["requirements"]) == 2

@pytest.mark.asyncio
async def test_parse_l2_response_invalid():
    """Тест парсинга невалидного ответа."""
    # Не L2 ответ
    response = "Это обычный текстовый ответ, не JSON"
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == False
    assert l2_data is None

@pytest.mark.asyncio
async def test_parse_l2_response_completed_false():
    """Тест парсинга ответа с completed: false."""
    response = '''{
        "completed": false,
        "message": "Продолжаем диалог"
    }'''
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == False
    assert l2_data is None

@pytest.mark.asyncio
async def test_parse_l2_response_completed_no_l2():
    """Тест парсинга ответа с completed: true но без l2."""
    response = '''{
        "completed": true,
        "message": "Диалог завершен"
    }'''
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == False
    assert l2_data is None

@pytest.mark.asyncio
async def test_parse_l2_response_markdown_wrapped():
    """Тест парсинга ответа в markdown блоках."""
    response = '''```json
{
    "completed": true,
    "l2": {
        "title": "Markdown Test",
        "description": "Test in markdown",
        "requirements": ["R1"],
        "technical_specs": {"stack": "JS"}
    }
}
```'''
    
    is_l2, l2_data = _parse_l2_response(response)
    
    assert is_l2 == True
    assert isinstance(l2_data, dict)
    assert l2_data["title"] == "Markdown Test"

if __name__ == "__main__":
    # Быстрый запуск тестов
    import asyncio
    
    async def run_tests():
        print("Running test_parse_l2_response_completed_format...")
        await test_parse_l2_response_completed_format()
        print("✓ test_parse_l2_response_completed_format passed")
        
        print("Running test_parse_l2_response_direct_format...")
        await test_parse_l2_response_direct_format()
        print("✓ test_parse_l2_response_direct_format passed")
        
        print("Running test_parse_l2_response_invalid...")
        await test_parse_l2_response_invalid()
        print("✓ test_parse_l2_response_invalid passed")
        
        print("Running test_parse_l2_response_completed_false...")
        await test_parse_l2_response_completed_false()
        print("✓ test_parse_l2_response_completed_false passed")
        
        print("Running test_parse_l2_response_completed_no_l2...")
        await test_parse_l2_response_completed_no_l2()
        print("✓ test_parse_l2_response_completed_no_l2 passed")
        
        print("Running test_parse_l2_response_markdown_wrapped...")
        await test_parse_l2_response_markdown_wrapped()
        print("✓ test_parse_l2_response_markdown_wrapped passed")
        
        print("\n✅ All tests passed!")
    
    asyncio.run(run_tests())