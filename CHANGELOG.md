# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] - 2026-08-19

First public release.

### Added

- MCP server over stdio exposing 12 tools for the Photon Commerce document extraction
  API: `process_document`, `get_extraction`, `classify_document`, `split_document`,
  `correct_fields`, `add_line_item`, `correct_line_item`, `delete_line_item`,
  `save_original_document`, `get_usage`, `check_connection` and `list_document_types`.
- Ten document types shared by extraction and classification: `invoice`, `receipt`,
  `check`, `stub`, `remittance`, `statement`, `bill-utility`, `bol`, `shippinglabel` and
  `invoice-commercial`. `classify_document` reports types from this same set, so its
  `suggested_doctype` can be passed straight to `process_document`.
- `PHOTON_ALLOWED_DIRS` filesystem sandboxing for document reads and downloads, using
  the platform path separator (`:` on macOS and Linux, `;` on Windows).
- Sandbox and production environments via `PHOTON_ENV`, with `PHOTON_BASE_URL` as an
  override.
- Synchronous and queued processing, reported through the `status` field.

[Unreleased]: https://github.com/Photon-Commerce/Photon-MCP/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Photon-Commerce/Photon-MCP/releases/tag/v0.1.0
