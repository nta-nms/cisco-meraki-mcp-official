# Cisco Meraki MCP Server

[![python]][python version] [![uv badge]][uv] [![ruff badge]][ruff]
[![ty badge]][ty]

The Cisco Meraki MCP Server connects AI agents and coding
assistants directly to the Meraki Dashboard API, enabling natural-language
queries and agentic network automation through a standardized interface.

Use it to build agents that answer questions about your network, generate
reports, troubleshoot connectivity issues, and audit configurations—without
writing custom API integration code.

## What Is MCP?

[Model Context Protocol (MCP)](https://modelcontextprotocol.io/) is an open
standard for connecting AI agents to external tools and data sources. MCP lets
clients such as Claude Code, Cursor, VS Code, and Codex call structured tools
at runtime, so agents can read live data rather than rely on training knowledge
alone.

The Cisco Meraki MCP Server implements this standard for the
Meraki Dashboard API. Your AI agent calls MCP tools; the server translates those
calls into authenticated Meraki API requests and returns the results.

## Choose Your Meraki MCP Deployment

Meraki MCP is available as a Cisco-hosted remote service or as a self-hosted,
open-source server. Both provide the same core MCP functionality; choose the
deployment model that best fits your operational and compliance requirements.

| | Cisco-hosted remote MCP | Local, open-source MCP |
| --- | --- | --- |
| **Deployment** | Cisco hosts and manages the MCP server. Connect your client to [`https://mcp.meraki.com/mcp`](https://mcp.meraki.com/mcp). | Run the MCP server in your own environment. |
| **Core functionality** | Provides the Meraki MCP capabilities described in this guide. | Provides the same core Meraki MCP functionality. |
| **Meraki environments** | Supports Meraki.com only. Federal, GovCloud, and localized Meraki environments are not supported. | Can work with any Meraki environment. |
| **Code and customization** | Cisco manages the service and its implementation. | Review and customize the source code to meet your requirements. |
| **Setup and compatibility** | Follow the hosted client configuration guidance below. | Follow the local stdio setup in this README. |

> **Important:** You are responsible for any changes you make to the local,
> open-source MCP. Meraki does not support modified local MCP code.

## Meraki MCP Terms and Policy

Your use of the Cisco Meraki MCP Server and any Cisco API leveraged by the MCP
Server is governed by the [Cisco Networking Model Context Protocol (MCP) Server
Terms](https://www.thousandeyes.com/pdf/mcp-server-addendum.pdf), [Cisco
Baseline API License Terms](https://www.cisco.com/c/dam/en_us/about/doing_business/legal/supplemental-terms/Baseline-API-Terms.pdf),
[Cisco Acceptable Use Policy](https://www.cisco.com/c/dam/en_us/about/legal/cisco-acceptable-use-policy.pdf),
[Cisco Meraki Cloud Service Offer Description](https://www.cisco.com/c/dam/en_us/about/doing_business/legal/OfferDescriptions/meraki.pdf),
and [Cisco General Terms](https://www.cisco.com/c/dam/en_us/about/doing_business/legal/Cisco_General_Terms.pdf).

## Prerequisites

- A Meraki Dashboard account
- A Meraki Dashboard API key, generated in **Dashboard → Organization → API &
  Webhooks**
- An MCP-compatible client, such as Claude Code, Cursor, VS Code, or Codex

> **Warning:** The MCP server supports only read operations. However, an AI
> agent with a Dashboard API key may attempt to call the Dashboard API directly.
> If the agent receives a read-write key, those direct calls could make changes
> outside the MCP server. Use an API key associated with read-only Dashboard
> access to ensure the agent cannot make changes.

## Hosted Cloud Setup

Use the hosted MCP server for the fastest setup when you do not need to run the
server locally.

### MCP Server URL

```text
https://mcp.meraki.com/mcp
```

### Authentication

The hosted server authenticates with a Meraki Dashboard API key passed as a
bearer token:

```http
Authorization: Bearer <MERAKI_DASHBOARD_API_KEY>
```

Before configuring Cursor, VS Code, Codex, or Claude Code, set
`MERAKI_DASHBOARD_API_KEY` in the environment used to launch that client. Restart
the client after setting or changing the variable.

```bash
export MERAKI_DASHBOARD_API_KEY="your-meraki-dashboard-api-key"
```

### Client Configuration

#### Claude Desktop

Claude Desktop does not support configuring remote MCP servers through
`claude_desktop_config.json`. Add remote servers through **Settings →
Connectors** instead. This flow currently supports unauthenticated and
OAuth-based servers; an API-key-authenticated Meraki MCP connection is not yet
supported in Claude Desktop.

#### Claude Code

Add the following to your `.mcp.json`:

```json
{
  "mcpServers": {
    "meraki": {
      "type": "http",
      "url": "https://mcp.meraki.com/mcp",
      "headers": {
        "Authorization": "Bearer ${MERAKI_DASHBOARD_API_KEY}"
      },
      "env": {
        "MERAKI_DASHBOARD_API_KEY": "${MERAKI_DASHBOARD_API_KEY}"
      }
    }
  }
}
```

#### Cursor

Add the following to your `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "meraki": {
      "url": "https://mcp.meraki.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MERAKI_DASHBOARD_API_KEY}"
      }
    }
  }
}
```

#### VS Code

Add the following to your `.vscode/mcp.json` to avoid hardcoding your API key:

```json
{
  "servers": {
    "meraki": {
      "type": "http",
      "url": "https://mcp.meraki.com/mcp",
      "headers": {
        "Authorization": "Bearer ${env:MERAKI_DASHBOARD_API_KEY}"
      }
    }
  }
}
```

#### Codex

Add the following to your `~/.codex/config.toml`:

```toml
[mcp_servers.meraki]
url = "https://mcp.meraki.com/mcp"
bearer_token_env_var = "MERAKI_DASHBOARD_API_KEY"
```

## Local Stdio Setup

Use local stdio when you want the MCP server to run entirely on your machine.
This setup clones the public source repository and connects your AI client to
the local command.

> **Security note:** Secure remote HTTP deployment—including TLS, certificate
> management, authentication, and network controls—is outside the scope of this
> project. For local use, use stdio or bind the server to localhost and do not
> allow remote connections. To expose the service on any network, including a
> private intranet, work with a qualified infrastructure or security
> professional.

### Prerequisites

- Python 3.14+ [installed on your machine]
- [uv] installed
- A Meraki Dashboard API key with access to the organizations and networks you
  query
  - To minimize surprises, create or reuse an API key from a read-only admin,
    not your primary admin

### Clone and install

```bash
git clone https://github.com/CiscoDevNet/meraki-mcp-official.git
cd meraki-mcp-official
uv sync
```

### Store your API key securely

For local stdio, do not put the raw API key in your MCP client configuration,
shell history, prompts, or checked-in files. Store it in your operating
system's credential store, then use a small launch script that reads the key at
server startup.

#### macOS

Store the key in Keychain:

```bash
printf "Meraki API key: "
read -r -s KEY
printf "\n"

security add-generic-password \
  -U \
  -a "$USER" \
  -s cisco-meraki-mcp-meraki-api-key \
  -w "$KEY"

unset KEY
```

Create a launcher:

```bash
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cisco-meraki-mcp-stdio" <<'EOF'
#!/bin/zsh
KEYCHAIN_SERVICE="cisco-meraki-mcp-meraki-api-key"
MERAKI_DASHBOARD_API_KEY="$(security find-generic-password \
  -a "$USER" \
  -s "$KEYCHAIN_SERVICE" \
  -w)"
export MERAKI_DASHBOARD_API_KEY
exec uv --directory "/path/to/meraki-mcp-official" \
  run cisco-meraki-mcp
EOF
chmod +x "$HOME/.local/bin/cisco-meraki-mcp-stdio"
```

#### Linux

On Linux desktops that support [Secret Service], store the key with
`secret-tool`:

```bash
secret-tool store \
  --label="Meraki MCP API key" \
  service cisco-meraki-mcp \
  username "$USER"
```

Create a launcher:

```bash
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/cisco-meraki-mcp-stdio" <<'EOF'
#!/bin/sh
MERAKI_DASHBOARD_API_KEY="$(secret-tool lookup \
  service cisco-meraki-mcp \
  username "$USER")"
export MERAKI_DASHBOARD_API_KEY
exec uv --directory "/path/to/meraki-mcp-official" \
  run cisco-meraki-mcp
EOF
chmod +x "$HOME/.local/bin/cisco-meraki-mcp-stdio"
```

For headless Linux, use your organization's secret manager or service manager
to inject `MERAKI_DASHBOARD_API_KEY` into the MCP server process while keeping
it out of client configuration and logs.

#### Windows

Use [Microsoft SecretManagement] with the local SecretStore vault:

```powershell
Install-Module Microsoft.PowerShell.SecretManagement -Scope CurrentUser
Install-Module Microsoft.PowerShell.SecretStore -Scope CurrentUser
Register-SecretVault `
  -Name LocalStore `
  -ModuleName Microsoft.PowerShell.SecretStore `
  -DefaultVault

$apiKey = Read-Host "Meraki API key" -AsSecureString
$secretName = "cisco-meraki-mcp-meraki-api-key"
Set-Secret -Name $secretName -Secret $apiKey
Remove-Variable apiKey
```

Create `cisco-meraki-mcp-stdio.ps1`:

```powershell
$secretName = "cisco-meraki-mcp-meraki-api-key"
$env:MERAKI_DASHBOARD_API_KEY = Get-Secret -Name $secretName -AsPlainText
uv --directory "C:\path\to\meraki-mcp-official" `
  run cisco-meraki-mcp
```

### Configure your MCP client to use the launcher

```json
{
  "mcpServers": {
    "cisco_meraki_mcp": {
      "command": "/path/to/cisco-meraki-mcp-stdio"
    }
  }
}
```

For VS Code, use the same server entry beneath `servers` in
`.vscode/mcp.json`. For Windows clients, use PowerShell to run the launcher:

```json
{
  "mcpServers": {
    "cisco_meraki_mcp": {
      "command": "pwsh",
      "args": [
        "-NoProfile",
        "-File",
        "C:\\path\\to\\cisco-meraki-mcp-stdio.ps1"
      ]
    }
  }
}
```

For Codex on macOS or Linux, edit `~/.codex/config.toml`:

```toml
[mcp_servers.cisco_meraki_mcp]
command = "/path/to/cisco-meraki-mcp-stdio"
```

For Codex on Windows:

```toml
[mcp_servers.cisco_meraki_mcp]
command = "pwsh"
args = [
  "-NoProfile",
  "-File",
  "C:\\path\\to\\cisco-meraki-mcp-stdio.ps1",
]
```

## Usage

### Example Workflow

Tell your AI assistant:

> _"Find the Meraki API capability for listing wireless SSIDs on a network."_

The assistant should:

1. Call `semantic_search` with your natural-language request.
2. Review the ranked capabilities and select the best `capability_id`.
3. Call `execute_api` with that `capability_id` and any required parameters.

```text
semantic_search(query="list wireless SSIDs", top_k=5)
execute_api(
  capability_id="getNetworkWirelessSsids",
  parameters={"networkId": "N_123"}
)
```

`execute_api` validates the selected capability, passes the request through the
Meraki Dashboard SDK using the configured `MERAKI_DASHBOARD_API_KEY`, and
returns the live Dashboard API response.

## Capabilities

### Tools

| Tool | Purpose |
| :--- | :--- |
| `semantic_search` | Search Meraki API capabilities with a natural-language query and return ranked `capability_id` results. |
| `execute_api` | Validate and execute a selected read-only API capability. |

### Resources

| Resource URI | Content |
| :--- | :--- |
| `info://service` | Service metadata |

## Rate Limits

The server respects the [Meraki Dashboard API rate limits][Meraki API rate
limits]:

- **Default limit:** 10 requests per second per organization
- **Backoff behavior:** The server automatically retries with exponential
  backoff on `429 Too Many Requests` responses.
- **Per-organization isolation:** Multi-organization sessions do not share a
  single rate-limit bucket.

## Limitations (Current Release)

- **Read-only:** Write operations are not supported.
- **API-key authentication only:** OAuth is not yet supported; a bearer token
  is required for the hosted service.
- **Hosted service:** The Cisco-hosted service supports Meraki.com only.
  Federal, GovCloud, and localized Meraki environments are not supported. The
  local, open-source server can work with any Meraki environment.

## Troubleshooting

### Dashboard API Key Errors

Confirm `MERAKI_DASHBOARD_API_KEY` is available in the environment that
launches your MCP client and that the API key is enabled in Dashboard with
access to the target organization, network, and endpoint.

### Local Install Errors

Run `uv sync` from the cloned repository root. If dependency installation
fails, confirm you are using a supported Python version and that your network
can access public Python package indexes.

### Client Cannot Find the Server

For hosted setup, confirm the configured MCP URL and bearer-token environment
variable are correct. For local stdio, confirm the `--directory` path points to
the cloned repository and that `uv run cisco-meraki-mcp` works from a
terminal.

## License

This project is licensed under the [Apache License, Version 2.0](LICENSE).

## Policies and Support

- [NOTICE](NOTICE.txt) describes the Cisco Meraki and API terms that apply when
  this software communicates with Meraki. Those terms are separate from the
  open-source license governing this code.
- [SECURITY](SECURITY.md) explains how to report a security issue privately.
- [CONTRIBUTING](CONTRIBUTING.md) describes the project's issue and
  contribution policy.
- For Dashboard API help, use [Meraki API docs] or your normal Meraki support
  channel.

[Apache License, Version 2.0]: LICENSE
[installed on your machine]: https://www.python.org/downloads/
[Meraki API docs]: https://developer.cisco.com/meraki/api-v1/
[Meraki API rate limits]: https://developer.cisco.com/meraki/api-v1/rate-limit-overview/
[Microsoft SecretManagement]:
  https://learn.microsoft.com/powershell/utility-modules/secretmanagement/overview
[python]: https://img.shields.io/badge/python-3.14-blue.svg
[python version]: https://docs.python.org/3/
[ruff]: https://docs.astral.sh/ruff/
[ruff badge]:
  https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
[Secret Service]: https://specifications.freedesktop.org/secret-service-spec/latest/
[ty]: https://docs.astral.sh/ty/
[ty badge]:
  https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ty/main/assets/badge/v0.json
[uv]: https://docs.astral.sh/uv/
[uv badge]:
  https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json
