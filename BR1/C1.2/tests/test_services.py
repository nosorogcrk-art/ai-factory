import pytest
from unittest.mock import patch
from services import decompose_task


@patch("services.decomposer.decompose")
def test_decompose_task_success(mock_decompose):
    mock_decompose.return_value = ["IMP-20260324-001"]
    result = decompose_task("Test description", {"task_id": "TEST"})
    assert result == ["IMP-20260324-001"]
    mock_decompose.assert_called_once_with("Test description", {"task_id": "TEST"})


@patch("services.decomposer.decompose")
def test_decompose_task_empty_description(mock_decompose):
    mock_decompose.return_value = []
    result = decompose_task("", {})
    assert result == []
    mock_decompose.assert_called_once()


def test_decompose_task_error_handling():
    with patch("services.decomposer.decompose", side_effect=RuntimeError("Boom")):
        with pytest.raises(RuntimeError):
            decompose_task("Test", {})