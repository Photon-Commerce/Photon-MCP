from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx

SANDBOX_BASE_URL = "https://sandbox-api.photoncommerce.com"
PRODUCTION_BASE_URL = "https://api.photoncommerce.com"

EXTRACT_PATH = "/api/pro"
DEFAULT_TIMEOUT_SECONDS = 180.0

MIN_FILE_BYTES = 1024
MAX_FILE_BYTES = 50 * 1024 * 1024

SUPPORTED_SUFFIXES = {
    ".pdf", ".png", ".jpeg", ".jpg", ".tif", ".tiff", ".heic",
    ".doc", ".docx", ".xls", ".xlsx", ".html", ".txt",
}

DOCTYPES = {
    "invoice": "Invoice",
    "receipt": "Receipt",
    "check": "Check",
    "stub": "Pay stub",
    "remittance": "Remittance",
    "statement": "Bank or card statement",
    "bill-utility": "Utility bill (electric, gas, water, internet, voice)",
    "bol": "Bill of lading",
    "shippinglabel": "Shipping label",
    "invoice-commercial": "Commercial invoice",
}

BULKY_FIELDS = ("Raw_Text", "raw_text", "RawText")


class PhotonError(Exception):
    pass


class PhotonConfigError(PhotonError):
    pass


class PhotonAPIError(PhotonError):
    def __init__(self, status_code: int | None, message: str, payload: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


@dataclass(frozen=True)
class Credentials:
    client_id: str
    secret_key: str
    username: str
    api_key: str
    password: str

    @classmethod
    def from_env(cls) -> Credentials:
        names = {
            "client_id": "PHOTON_CLIENT_ID",
            "secret_key": "PHOTON_SECRET_KEY",
            "username": "PHOTON_USERNAME",
            "api_key": "PHOTON_API_KEY",
            "password": "PHOTON_PASSWORD",
        }
        values = {field: os.environ.get(var, "").strip() for field, var in names.items()}
        missing = sorted(names[field] for field, value in values.items() if not value)
        if missing:
            raise PhotonConfigError(
                "Missing Photon API credentials: " + ", ".join(missing) + ". "
                "Register at https://sandbox-api.photoncommerce.com/api/v4/register "
                "or contact api@photoncommerce.com, then set them in your MCP host config."
            )
        return cls(**values)

    def headers(self) -> dict[str, str]:
        return {
            "CLIENT-ID": self.client_id,
            "SECRET-KEY": self.secret_key,
            "AUTHORIZATION": f"apikey {self.username}:{self.api_key}",
            "PASSWORD": self.password,
        }


def resolve_base_url() -> str:
    override = os.environ.get("PHOTON_BASE_URL", "").strip().rstrip("/")
    if override:
        return override
    environment = os.environ.get("PHOTON_ENV", "sandbox").strip().lower()
    if environment in ("prod", "production", "live"):
        return PRODUCTION_BASE_URL
    if environment in ("sandbox", "dev", "test", ""):
        return SANDBOX_BASE_URL
    raise PhotonConfigError(
        f"PHOTON_ENV must be 'sandbox' or 'production', got {environment!r}"
    )


def resolve_allowed_dirs() -> list[Path]:
    raw = os.environ.get("PHOTON_ALLOWED_DIRS", "").strip()
    if not raw:
        return []
    return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p.strip()]


def suggested_doctype(detected: Any) -> str | None:
    key = str(detected or "").strip().lower()
    return key if key in DOCTYPES else None


def strip_bulky_fields(payload: Any) -> Any:
    if isinstance(payload, dict):
        return {k: strip_bulky_fields(v) for k, v in payload.items() if k not in BULKY_FIELDS}
    if isinstance(payload, list):
        return [strip_bulky_fields(v) for v in payload]
    return payload


class PhotonClient:
    def __init__(
        self,
        credentials: Credentials | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        allowed_dirs: list[Path] | None = None,
    ):
        self.credentials = credentials or Credentials.from_env()
        self.base_url = (base_url or resolve_base_url()).rstrip("/")
        self.allowed_dirs = allowed_dirs if allowed_dirs is not None else resolve_allowed_dirs()
        seconds = timeout if timeout is not None else float(
            os.environ.get("PHOTON_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_SECONDS)
        )
        self._client = httpx.Client(timeout=seconds, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def resolve_upload(self, file_path: str) -> Path:
        path = Path(file_path).expanduser().resolve()
        if not path.is_file():
            raise PhotonConfigError(f"No file found at {path}")
        if self.allowed_dirs and not any(
            path == root or root in path.parents for root in self.allowed_dirs
        ):
            allowed = ", ".join(str(root) for root in self.allowed_dirs)
            raise PhotonConfigError(
                f"{path} is outside the directories this server may read ({allowed}). "
                "Adjust PHOTON_ALLOWED_DIRS if this file should be readable."
            )
        size = path.stat().st_size
        if size < MIN_FILE_BYTES:
            raise PhotonConfigError(
                f"{path.name} is {size} bytes; the Photon API rejects files under "
                f"{MIN_FILE_BYTES} bytes."
            )
        if size > MAX_FILE_BYTES:
            raise PhotonConfigError(
                f"{path.name} is {size} bytes; the Photon API rejects files over "
                f"{MAX_FILE_BYTES} bytes."
            )
        if path.suffix.lower() not in SUPPORTED_SUFFIXES:
            supported = ", ".join(sorted(SUPPORTED_SUFFIXES))
            raise PhotonConfigError(
                f"{path.suffix or 'that file type'} is not supported. Supported: {supported}"
            )
        return path

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        upload: Path | None = None,
        upload_field: str = "pdf",
        expect_json: bool = True,
    ) -> Any:
        url = f"{self.base_url}{path}"
        clean_params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        handle = None
        try:
            files = None
            if upload is not None:
                handle = upload.open("rb")
                files = {upload_field: (upload.name, handle, "application/octet-stream")}
            response = self._client.request(
                method,
                url,
                params=clean_params,
                json=json_body,
                files=files,
                headers=self.credentials.headers(),
            )
        except httpx.RequestError as exc:
            raise PhotonAPIError(None, f"Could not reach the Photon API at {url}: {exc}") from exc
        finally:
            if handle is not None:
                handle.close()
        if not expect_json:
            if response.status_code >= 400:
                raise PhotonAPIError(
                    response.status_code, self._error_message(response, None), None
                )
            return response.content
        return self._parse(response)

    @staticmethod
    def _error_message(response: httpx.Response, payload: Any) -> str:
        if isinstance(payload, dict):
            for key in ("message", "detail", "error", "errors"):
                value = payload.get(key)
                if value:
                    return str(value)
        text = (response.text or "").strip()
        return text[:500] or f"HTTP {response.status_code} with an empty body"

    def _parse(self, response: httpx.Response) -> Any:
        try:
            payload = response.json()
        except ValueError:
            payload = None
        if response.status_code >= 400:
            raise PhotonAPIError(
                response.status_code,
                self._error_message(response, payload),
                payload,
            )
        if payload is None:
            raise PhotonAPIError(
                response.status_code,
                "The Photon API returned a non-JSON response: "
                + (response.text or "").strip()[:300],
                None,
            )
        return payload

    def extract(
        self,
        *,
        file_path: str | None = None,
        url: str | None = None,
        doctype: str | None = None,
        page_start: int | None = None,
        page_end: int | None = None,
        subaccount: str | None = None,
        reference_id: str | None = None,
    ) -> Any:
        if bool(file_path) == bool(url):
            raise PhotonConfigError("Pass exactly one of file_path or url.")
        if doctype and doctype not in DOCTYPES:
            valid = ", ".join(sorted(DOCTYPES))
            raise PhotonConfigError(f"Unknown doctype {doctype!r}. Valid values: {valid}")
        params = {
            "url": url,
            "doctype": doctype,
            "page_start": page_start,
            "page_end": page_end,
            "subaccount": subaccount,
            "ID": reference_id,
        }
        upload = self.resolve_upload(file_path) if file_path else None
        return self._request("POST", EXTRACT_PATH, params=params, upload=upload)

    def get_json(self, photon_key: str) -> Any:
        return self._request("GET", "/api/v4/json", params={"photon_key": photon_key})

    def classify(self, *, file_path: str | None = None, url: str | None = None) -> Any:
        if bool(file_path) == bool(url):
            raise PhotonConfigError("Pass exactly one of file_path or url.")
        upload = self.resolve_upload(file_path) if file_path else None
        return self._request(
            "POST", "/classify", params={"url": url}, upload=upload, upload_field="file"
        )

    def split(self, *, file_path: str | None = None, url: str | None = None) -> Any:
        if bool(file_path) == bool(url):
            raise PhotonConfigError("Pass exactly one of file_path or url.")
        upload = self.resolve_upload(file_path) if file_path else None
        return self._request(
            "POST", "/docsplitter", params={"url": url}, upload=upload, upload_field="file"
        )

    def update_fields(self, photon_key: str, fields: dict[str, Any]) -> Any:
        return self._request(
            "PUT", "/api/v4/update", params={"photon_key": photon_key}, json_body=fields
        )

    def add_line_item(self, photon_key: str, fields: dict[str, Any]) -> Any:
        return self._request(
            "POST",
            "/api/v4/update/line-items",
            params={"photon_key": photon_key},
            json_body=fields,
        )

    def update_line_item(self, photon_key: str, line_item_id: str, fields: dict[str, Any]) -> Any:
        return self._request(
            "PUT",
            f"/api/v4/update/line-items/{line_item_id}",
            params={"photon_key": photon_key},
            json_body=fields,
        )

    def delete_line_item(self, photon_key: str, line_item_id: str) -> Any:
        return self._request(
            "DELETE",
            f"/api/v4/update/line-items/{line_item_id}",
            params={"photon_key": photon_key},
        )

    def balance(
        self, year: int | None = None, month: int | None = None, subaccount: bool | None = None
    ) -> Any:
        params: dict[str, Any] = {"year": year, "month": month}
        if subaccount:
            params["subaccount"] = "True"
        return self._request("GET", "/balance", params=params)

    def download(self, doc_path: str) -> bytes:
        return self._request(
            "GET", "/download-file", params={"doc_path": doc_path}, expect_json=False
        )

    def health(self) -> Any:
        return self._request("GET", "/health")
