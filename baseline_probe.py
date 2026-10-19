"""Verify that the original camera produces an image-regression failure."""

from __future__ import annotations

import ast
import logging
from pathlib import Path
import shutil
import subprocess
import sys
import textwrap

import pytest

import pyvista as pv

BASE = 'b148504c765615babd76ff569f33831c046106c1'


class ImageFailure:
    """Capture the specific regression failure, not unrelated setup errors."""

    def __init__(self) -> None:
        """Initialize the collected reports."""
        self.failures = []

    def pytest_runtest_logreport(self, report: pytest.TestReport) -> None:
        """Collect failed test reports."""
        if report.failed:
            self.failures.append(str(report.longrepr))


def main() -> None:
    """Load the base method in memory and check the new image test."""
    source = subprocess.check_output(
        [shutil.which('git'), 'show', f'{BASE}:pyvista/plotting/camera.py'], text=True
    )
    camera = next(
        node
        for node in ast.parse(source).body
        if isinstance(node, ast.ClassDef) and node.name == 'Camera'
    )
    method = next(
        node for node in camera.body if isinstance(node, ast.FunctionDef) and node.name == 'tight'
    )
    namespace = dict(pv.Camera.tight.__globals__)
    # Only the method from the fixed public base commit is executed in this process.
    exec(  # noqa: S102
        'from __future__ import annotations\n'
        + textwrap.dedent(ast.get_source_segment(source, method)),
        namespace,
    )
    original = pv.Camera.tight
    pv.Camera.tight = namespace['tight']
    capture = ImageFailure()
    try:
        result = pytest.main(
            [
                'tests/plotting/test_plotting.py::test_tight_airplane',
                '--image_cache_dir',
                str(Path(sys.argv[1]).resolve()),
                '--generated_image_dir',
                str(Path(sys.argv[2]).resolve()),
                '--failed_image_dir',
                str(Path(sys.argv[2]).resolve() / 'failures'),
                '-q',
                '--tb=short',
            ],
            plugins=[capture],
        )
    finally:
        pv.Camera.tight = original
    if result != pytest.ExitCode.TESTS_FAILED or len(capture.failures) != 1:
        msg = 'Expected exactly one image-regression failure from the base camera.'
        raise SystemExit(msg)
    failure = capture.failures[0]
    if 'RegressionError' not in failure or 'Exceeded' not in failure:
        msg = 'The base failed for a reason other than image comparison.'
        raise SystemExit(msg)
    logging.getLogger(__name__).warning(
        'Confirmed: the new image test detects the original camera regression.'
    )


if __name__ == '__main__':
    main()
