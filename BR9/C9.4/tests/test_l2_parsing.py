import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from llm_client import _parse_l2_response

def test_parse_l2_from_plain_json():
    text = '{"title":"Test","description":"Desc","requirements":["R1"],"technical_specs":{"stack":"Python"}}'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is True
    assert data['title'] == 'Test'

def test_parse_l2_from_markdown():
    text = '```json\n{"title":"Test","description":"Desc","requirements":["R1"],"technical_specs":{"stack":"Python"}}\n```'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is True
    assert data['title'] == 'Test'

def test_parse_non_l2_response():
    text = 'Какую главную проблему вы хотите решить?'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is False
    assert data is None

def test_parse_l2_with_extra_text():
    text = 'Вот ваш L2: ```json\n{"title":"Test","description":"Desc","requirements":["R1"],"technical_specs":{"stack":"Python"}}\n```'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is True
    assert data['title'] == 'Test'

def test_parse_l2_missing_required_field():
    # отсутствует technical_specs
    text = '{"title":"Test","description":"Desc","requirements":["R1"]}'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is False
    assert data is None

def test_parse_l2_with_extra_fields():
    text = '{"title":"Test","description":"Desc","requirements":["R1"],"technical_specs":{"stack":"Python"},"extra":"field"}'
    is_l2, data = _parse_l2_response(text)
    assert is_l2 is True
    assert data['title'] == 'Test'
    assert 'extra' in data

if __name__ == '__main__':
    pytest.main([__file__, '-v'])