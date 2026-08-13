# Photon Commerce MCP server

Turn invoices, receipts, checks, remittances, bank statements, utility bills and bills of
lading into structured JSON, from inside Claude.

This is an [MCP](https://modelcontextprotocol.io) server for the
[Photon Commerce API](https://apidocs.photoncommerce.com/). It runs locally on your
machine over stdio and talks to nothing but the Photon REST API — no database, no cloud
storage, no hosting to stand up. You bring your own API credentials and it acts on your
behalf.

## Install

You'll need Python 3.10 or newer.

```bash
git clone <this repo> && cd photon-mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

## Get credentials

If you don't already have an account, register for a free sandbox one:

```bash
curl -X POST https://sandbox-api.photoncommerce.com/api/v4/register \
  -F first_name=Jane -F last_name=Doe \
  -F email=you@example.com -F password='YourPassw0rd!'
```

You'll get back a `client_id`, `api_key`, `secret_key` and `username` — those plus your
password are what the server needs. For a production account, email
api@photoncommerce.com.

## Point Claude at it

In `claude_desktop_config.json`:

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

Or from the terminal:

```bash
claude mcp add photon /absolute/path/to/.venv/bin/photon-mcp \
  -e PHOTON_CLIENT_ID=... -e PHOTON_SECRET_KEY=... \
  -e PHOTON_USERNAME=... -e PHOTON_API_KEY=... -e PHOTON_PASSWORD=...
```

Then just ask for what you want — *"pull the totals out of ~/Documents/invoices/acme.pdf"*
or *"what kind of document is this?"*

### A note on `PHOTON_ALLOWED_DIRS`

Worth setting. It's a colon-separated list of directories the server is allowed to read
documents from and write downloads to. Leave it unset and the server will happily upload
whatever path it's given; set it and anything outside those folders is refused. Since the
thing choosing the paths is a language model, it's a sensible boundary to draw.

### Settings

| Variable | Required | Default |
|---|---|---|
| `PHOTON_CLIENT_ID` | Yes | — |
| `PHOTON_SECRET_KEY` | Yes | — |
| `PHOTON_USERNAME` | Yes | your registered email |
| `PHOTON_API_KEY` | Yes | — |
| `PHOTON_PASSWORD` | Yes | — |
| `PHOTON_ENV` | No | `sandbox` — set to `production` for a live account |
| `PHOTON_BASE_URL` | No | overrides `PHOTON_ENV` |
| `PHOTON_ALLOWED_DIRS` | No | unrestricted |
| `PHOTON_TIMEOUT_SECONDS` | No | `180` |
| `PHOTON_LOG_LEVEL` | No | `WARNING` |

## What it can do

**Extracting.** `process_document` takes either a local file path or a public URL, with an
optional `doctype` and page range, and gives you back the extracted fields. If you're not
sure what a document is, `classify_document` will tell you and suggest the right doctype
to use — point it at a local file. `split_document` finds the page boundaries in a PDF
that has several documents stacked inside it.

Every processed document gets a `photon_key`. `get_extraction` fetches it back later, and
`save_original_document` downloads the source file to a folder you name.

**Editing.** `correct_fields`, `add_line_item`, `correct_line_item` and `delete_line_item`
amend a stored extraction when something came back wrong. Editing is enabled per account —
if these return an error, email support@photoncommerce.com to have it turned on.

**Housekeeping.** `get_usage` shows how many API calls and pages you've used.
`check_connection` confirms your credentials work and the API is up; it's the first thing
to try when something misbehaves. `list_document_types` lists the doctypes and file
formats without touching the network.

Results come back as `{"ok": true, ...}` or `{"ok": false, "error": "..."}`, with a hint
attached when there's something specific you can do about it. The bulky `Raw_Text` field
is stripped from extractions before they reach the model, since it eats context and is
rarely what you want.

## Document types and limits

Pass one of `invoice`, `receipt-expense`, `check`, `remittance`, `statement`,
`bill-utility`, `bol`, `hbl` or `mbl` as `doctype`. Leave it off and the document is
treated as an invoice.

Files need to be between 1 KB and 50 MB. PDF, PNG, JPEG, TIFF, HEIC, DOC/DOCX, XLS/XLSX,
HTML and TXT all work. The API allows 10 requests a second, and sandbox accounts include
20 pages over 14 days.

## Sync and async

Depending on how your account is set up, `process_document` either returns the extraction
straight away or queues the document. It handles both — check `status`:

- `extracted` — the data is in `extraction`
- `queued` — call `get_extraction` with the `photon_key` in a moment

Asynchronous processing is enabled per account by sales@photoncommerce.com, with a
standard 24-hour turnaround and faster options available.

## Development

```bash
pip install -e ".[dev]"
pytest
```

The test suite runs offline against a stubbed transport — no credentials or API calls
needed.
