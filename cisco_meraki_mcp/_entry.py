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
"""Process entry point: configures environment before application imports.

``HF_HUB_DISABLE_XET`` is set here, before ``huggingface_hub`` is imported,
because the library reads it as a module-level constant at import time.
Disabling XET forces plain HTTPS downloads, which avoids partial model
downloads caused by XET chunk-ordering failures on VPNs and proxies.
Setting ``HF_HUB_DISABLE_XET=0`` in the process environment before launch
overrides this default.
"""

import os

os.environ.setdefault("HF_HUB_DISABLE_XET", "1")

from cisco_meraki_mcp.main import main


def run() -> None:
    main()
