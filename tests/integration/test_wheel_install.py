# Copyright 2026 Cisco Systems, Inc. and its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# SPDX-License-Identifier: Apache-2.0

# oss-safe
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
UV = shutil.which("uv")

pytestmark = pytest.mark.skipif(UV is None, reason="uv not on PATH")


@pytest.mark.slow
def test_wheel_install_resolves_bundled_spec(tmp_path):
    # Verifies the packaged distribution can properly find and load
    # its bundled OpenAPI spec file after installation. Simulates a
    # real user's installation by building a wheel, installing it
    # into an isolated venv, and confirming the bundled spec resolves
    # in site-packages. Anchor logic is duplicated inline (not imported)
    # to keep the probe free of the dependency tree.
    dist_dir = tmp_path / "dist"
    venv_dir = tmp_path / "venv"

    subprocess.run(  # noqa: S603
        [UV, "build", "--wheel", str(REPO_ROOT), "-o", str(dist_dir)],
        check=True,
        capture_output=True,
    )
    wheels = list(dist_dir.glob("cisco_meraki_mcp-*.whl"))
    assert len(wheels) == 1, f"expected 1 wheel, found {wheels}"

    subprocess.run(  # noqa: S603
        [UV, "venv", str(venv_dir), "--python", sys.executable],
        check=True,
        capture_output=True,
    )
    subprocess.run(  # noqa: S603
        [
            UV,
            "pip",
            "install",
            "--no-deps",
            "--python",
            str(venv_dir / "bin" / "python"),
            str(wheels[0]),
        ],
        check=True,
        capture_output=True,
    )

    isolated_env = {
        k: v
        for k, v in os.environ.items()
        if k not in {"PYTHONPATH", "VIRTUAL_ENV"}
    }

    probe = (
        "import gzip, json; "
        "from importlib import resources; "
        "from pathlib import Path; "
        "anchor = resources.files('cisco_meraki_mcp').joinpath("
        "'specs', 'meraki.json.gz'); "
        "path = Path(str(anchor)); "
        "assert path.exists(), path; "
        "assert 'site-packages' in str(path), path; "
        "spec = json.loads(gzip.decompress(path.read_bytes())); "
        "print(len(spec['paths']))"
    )
    result = subprocess.run(  # noqa: S603
        [str(venv_dir / "bin" / "python"), "-c", probe],
        capture_output=True,
        text=True,
        env=isolated_env,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, (
        f"probe failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert int(result.stdout.strip()) > 0
