"""QA Phase 1 gate tests for issue #392.

Asserts that .githooks/pre-push and .github/workflows/app-ci.yml both use
a 90% coverage threshold, eliminating the pre-push/CI drift introduced when
CI was raised from 85 → 90 without updating the hook.

All tests are xfail(strict=True) until the fix lands.
"""

import pathlib
import re

import pytest

pytestmark = pytest.mark.unit

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
_PRE_PUSH = _REPO_ROOT / ".githooks" / "pre-push"
_APP_CI = _REPO_ROOT / ".github" / "workflows" / "app-ci.yml"

EXPECTED_THRESHOLD = 90


@pytest.mark.xfail(
    reason="#392: .githooks/pre-push still uses --cov-fail-under=85; needs 90",
    strict=True,
)
def test_pre_push_threshold_is_90():
    """pre-push hook must specify --cov-fail-under=90."""
    content = _PRE_PUSH.read_text()
    match = re.search(r"--cov-fail-under=(\d+)", content)
    assert match is not None, "--cov-fail-under not found in pre-push"
    actual = int(match.group(1))
    assert actual == EXPECTED_THRESHOLD, (
        f"pre-push uses --cov-fail-under={actual}, expected {EXPECTED_THRESHOLD}"
    )


@pytest.mark.xfail(
    reason="#392: app-ci.yml header comment still reads '85% coverage gate'; needs 90",
    strict=True,
)
def test_app_ci_stale_comment_references_90():
    """app-ci.yml header comment must reference 90%, not 85%."""
    content = _APP_CI.read_text()
    # The stale comment pattern: "→ ... 85% coverage gate"
    stale_pattern = re.compile(r"#.*→.*85%.*coverage gate", re.IGNORECASE)
    assert not stale_pattern.search(content), (
        "app-ci.yml still contains a stale comment referencing 85% coverage gate"
    )


def test_app_ci_pytest_threshold_is_90():
    """app-ci.yml pytest step already uses --cov-fail-under=90 (should pass now)."""
    content = _APP_CI.read_text()
    match = re.search(r"--cov-fail-under=(\d+)", content)
    assert match is not None, "--cov-fail-under not found in app-ci.yml"
    actual = int(match.group(1))
    assert actual == EXPECTED_THRESHOLD, (
        f"app-ci.yml uses --cov-fail-under={actual}, expected {EXPECTED_THRESHOLD}"
    )


@pytest.mark.xfail(
    reason="#392: pre-push threshold (85) does not match app-ci.yml threshold (90)",
    strict=True,
)
def test_pre_push_and_app_ci_thresholds_match():
    """Both files must use the same --cov-fail-under value."""
    pre_push_content = _PRE_PUSH.read_text()
    ci_content = _APP_CI.read_text()

    pre_push_match = re.search(r"--cov-fail-under=(\d+)", pre_push_content)
    ci_match = re.search(r"--cov-fail-under=(\d+)", ci_content)

    assert pre_push_match is not None, "--cov-fail-under not found in pre-push"
    assert ci_match is not None, "--cov-fail-under not found in app-ci.yml"

    pre_push_val = int(pre_push_match.group(1))
    ci_val = int(ci_match.group(1))

    assert pre_push_val == ci_val, (
        f"Coverage threshold mismatch: pre-push={pre_push_val}, app-ci.yml={ci_val}"
    )
