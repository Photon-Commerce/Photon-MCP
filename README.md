# Photon Commerce MCP server

An [MCP](https://modelcontextprotocol.io) server that exposes the
[Photon Commerce API](https://apidocs.photoncommerce.com/) — extract structured JSON from
invoices, receipts, checks, remittances, bank statements, utility bills and bills of lading.

Runs locally over stdio. It talks only to the Photon Commerce REST API: no database, no
object storage, no OAuth server, no hosting. You bring your own API credentials and the
server acts on your behalf.

## Install

Requires Python 3.10+.

```bash
git clone <this repo> && cd photon-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Credentials

Register a free sandbox account (20 pages over 14 days):

```bash
curl -X POST https://sandbox-api.photoncommerce.com/api/v4/register \
  -F first_name=Jane -F last_name=Doe \
  -F email=you@example.com -F password='YourPassw0rd!'
```

The response contains the five values this server needs:

```json
{
  "client_id": "...", "api_key": "...", "secret_key": "...",
  "username": "you@example.com", "password": "YourPassw0rd!"
}
```

For a production account, contact api@photoncommerce.com.

## Configure your MCP host

**Claude Desktop** — `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "photon": {
      "command": "/absolute/path/to/photon-mcp/.venv/bin/photon-mcp",
      "env": {
        "PHOTON_CLIENT_ID": "...",
        "PHOTON_SECRET_KEY": "...",
        "PHOTON_USERNAME": "you@example.com",
        "PHOTON_API_KEY": "...",
        "PHOTON_PASSWORD": "...",
        "PHOTON_ENV": "sandbox",
        "PHOTON_ALLOWED_DIRS": "/Users/you/Documents/invoices"
      }
    }
  }
}
```

**Claude Code:**

```bash
claude mcp add photon /absolute/path/to/.venv/bin/photon-mcp \
  -e PHOTON_CLIENT_ID=... -e PHOTON_SECRET_KEY=... \
  -e PHOTON_USERNAME=... -e PHOTON_API_KEY=... -e PHOTON_PASSWORD=...
```

Then ask: *"Classify and extract ~/Documents/invoices/acme.pdf"*.

### Environment variables

| Variable | Required | Default | Notes |
|---|---|---|---|
| `PHOTON_CLIENT_ID` | Yes | — | |
| `PHOTON_SECRET_KEY` | Yes | — | |
| `PHOTON_USERNAME` | Yes | — | The email you registered with |
| `PHOTON_API_KEY` | Yes | — | |
| `PHOTON_PASSWORD` | Yes | — | |
| `PHOTON_ENV` | No | `sandbox` | `sandbox` or `production` |
| `PHOTON_BASE_URL` | No | — | Overrides `PHOTON_ENV` entirely |
| `PHOTON_ALLOWED_DIRS` | No | unrestricted | `:`-separated directories the server may read from and write to |
| `PHOTON_TIMEOUT_SECONDS` | No | `180` | |

**Set `PHOTON_ALLOWED_DIRS`.** Without it the server will upload any file path the model
asks for. With it, `process_document`, `classify_document`, `split_document` and
`save_original_document` refuse paths outside those directories. This is the main defence
against a prompt-injected model exfiltrating a local file to your Photon account.

## Tools

| Tool | Does | Notes |
|---|---|---|
| `list_document_types` | Lists doctype keys, supported formats, size limits | No API call |
| `process_document` | Extracts data from a local file or URL | |
| `get_extraction` | Fetches an extraction by `photon_key` | Read-only |
| `classify_document` | Detects a document's type | |
| `split_document` | Finds document boundaries in a stacked PDF | |
| `correct_fields` | Overwrites header fields on an extraction | |
| `add_line_item` | Appends a line item | |
| `correct_line_item` | Overwrites fields on one line item | |
| `delete_line_item` | Removes a line item | **Destructive** |
| `save_original_document` | Writes a processed document to disk | Honours `PHOTON_ALLOWED_DIRS` |
| `get_usage` | Reports API calls and pages consumed | Read-only |
| `check_connection` | Verifies credentials and API reachability | Read-only; start here when something fails |

Every tool returns `{"ok": true, ...}` or `{"ok": false, "error": "..."}`. Authentication
and quota failures carry a `hint` explaining what to change. `Raw_Text` is stripped from
every extraction before it reaches the model — it is large and rarely useful.

### Document types

`process_document` accepts: `invoice`, `receipt-expense`, `check`, `remittance`,
`statement`, `bill-utility`, `bol`, `hbl`, `mbl`. Omitting `doctype` means the API treats
the document as an invoice.

### Limits

Files must be 1 KB–50 MB. Supported: PDF, PNG, JPEG/JPG, TIF/TIFF, HEIC, DOC/DOCX,
XLS/XLSX, HTML, TXT. The API rate limit is 10 requests/second.

## Sync vs async

All extraction goes to `POST /api/pro`. Whether that returns data immediately or queues
the document is a property of the **account**, not of the request — asynchronous
processing is enabled per account by sales@photoncommerce.com, with a standard 24-hour
turnaround and faster tiers available.

`process_document` handles both — check `status` in the result:

- `"extracted"` — the data is in `extraction`
- `"queued"` — poll `get_extraction` with the `photon_key`

## Known gaps

These are limits of the documented API, not of this server:

- **No "list my documents" endpoint.** You can retrieve any extraction by `photon_key`,
  but nothing enumerates past documents. Keep the keys `process_document` returns.
- **The published docs contradict themselves on the extraction path.** `/api/pro` is
  correct and is what this server uses. Prose elsewhere in the same documentation still
  references `/api/v4` and `/statements/v1`; those references are stale and worth
  correcting at the source.
- **Doctype naming is inconsistent.** The classifier returns `receipt` and
  `invoice-commercial`, neither of which appears in the documented extraction doctype
  list. Use `receipt-expense` for receipts.
- **Webhooks are not exposed.** `/api/pro` accepts `webhook_url` and `auth_token`, but a
  local stdio server has no public URL to receive callbacks. Poll `get_extraction`
  instead.
- **Not exposed on purpose:** `/rotate-keys` (would invalidate your credentials mid-session)
  and `/delete-file` (deletes whole documents). Both are a poor fit for a model-driven tool.

## Development

```bash
pip install -e .
python -m photon_mcp          # starts the stdio server; expects JSON-RPC on stdin
```
