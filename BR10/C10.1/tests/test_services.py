from services import build_patches


def test_build_patches_success(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=True)
    mocker.patch("services.repositories.update_task_status", return_value=True)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is True
    assert "Build started" in msg


def test_build_patches_apply_fails(mocker):
    mocker.patch("services._apply_patches", return_value=False)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is False
    assert "Failed to apply patches" in msg


def test_build_patches_build_fails(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=False)
    success, msg = build_patches("DIALOG-123", ["IMP-001"], check_skills=True, run_tests=True)
    assert success is False
    assert "Build failed" in msg


def test_build_patches_without_task_id(mocker):
    mocker.patch("services._apply_patches", return_value=True)
    mocker.patch("services._run_build", return_value=True)
    success, msg = build_patches(None, ["IMP-001"], check_skills=True, run_tests=True)
    assert success is True
    assert "Build started" in msg