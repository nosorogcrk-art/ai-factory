import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock, ANY
from services import run_tests_async
from models import TestRequest
from pathlib import Path

@pytest.mark.asyncio
async def test_run_tests_async_product_not_found(tmp_path):
    job_id = "test_job"
    nonexistent = tmp_path / "nonexistent"
    with patch("pathlib.Path.exists", return_value=True):
        request = TestRequest(product_path=str(nonexistent), test_suite="tests", image="python:3.12-slim", timeout_seconds=600)
    with patch("services.repo.load_job", return_value={"job_id": job_id}), \
         patch("services.repo.save_job") as mock_save_job, \
         patch("services.send_to_br18", new_callable=AsyncMock) as mock_send:
        await run_tests_async(job_id, request)
        mock_save_job.assert_called()
        args, _ = mock_save_job.call_args
        job = args[0]
        assert job["status"] == "failed"
        assert "Product path not found" in job["error"]
        mock_send.assert_called_once_with("test_failed", {"job_id": job_id, "error": job["error"]})

@pytest.mark.asyncio
async def test_run_tests_async_timeout(tmp_path):
    job_id = "test_job"
    product_dir = tmp_path / "product"
    product_dir.mkdir()
    with patch("pathlib.Path.exists", return_value=True):
        request = TestRequest(product_path=str(product_dir), test_suite="tests", image="python:3.12-slim", timeout_seconds=1)
    with patch("services.repo.load_job", return_value={"job_id": job_id}), \
         patch("services.repo.save_job") as mock_save_job, \
         patch("services.send_to_br18", new_callable=AsyncMock) as mock_send, \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subprocess:
        proc = AsyncMock()
        proc.communicate.side_effect = asyncio.TimeoutError()
        mock_subprocess.return_value = proc
        await run_tests_async(job_id, request)
        mock_save_job.assert_called()
        args, _ = mock_save_job.call_args
        job = args[0]
        assert job["status"] == "timeout"
        assert "timed out" in job["error"]
        mock_send.assert_called_once_with("test_completed", {
            "job_id": job_id,
            "status": "timeout",
            "report_file": None,
            "error": job["error"]
        })

@pytest.mark.asyncio
async def test_run_tests_async_success(tmp_path):
    job_id = "test_job"
    product_dir = tmp_path / "product"
    product_dir.mkdir()
    with patch("pathlib.Path.exists", return_value=True):
        request = TestRequest(product_path=str(product_dir), test_suite="tests", image="python:3.12-slim", timeout_seconds=600)
    with patch("services.repo.load_job", return_value={"job_id": job_id}), \
         patch("services.repo.save_job") as mock_save_job, \
         patch("services.send_to_br18", new_callable=AsyncMock) as mock_send, \
         patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_subprocess, \
         patch("shutil.copy2") as mock_copy, \
         patch("pathlib.Path.mkdir"):
        proc = AsyncMock()
        proc.returncode = 0
        proc.communicate.return_value = (b"stdout", b"stderr")
        mock_subprocess.return_value = proc
        mock_report = MagicMock()
        mock_report.exists.return_value = True
        with patch("pathlib.Path.exists", return_value=True):
            await run_tests_async(job_id, request)
        mock_save_job.assert_called()
        args, _ = mock_save_job.call_args
        job = args[0]
        assert job["status"] == "completed"
        mock_send.assert_called_once_with("test_completed", {
            "job_id": job_id,
            "status": "completed",
            "report_file": ANY,
            "error": None
        })