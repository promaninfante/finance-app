import json
import logging

import httpx
from google.auth.transport.requests import Request
from google.oauth2 import service_account

from shared.http import get_client

logger = logging.getLogger(__name__)

_DRIVE_DOWNLOAD_URL = "https://www.googleapis.com/drive/v3/files/{file_id}?alt=media"
_SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
_MAX_FILE_BYTES = 50 * 1024 * 1024  # 50 MB


class DriveFileNotFoundError(Exception):
    pass


class DrivePermissionError(Exception):
    pass


class DriveFileTooLargeError(Exception):
    pass


def fetch_drive_file(file_id: str, service_account_json: str) -> bytes:
    """Download PDF bytes from Drive using the service account credentials.

    Raises DriveFileNotFoundError, DrivePermissionError, or DriveFileTooLargeError
    on known failure modes.
    """
    creds = _build_credentials(service_account_json)
    token = _get_access_token(creds)

    url = _DRIVE_DOWNLOAD_URL.format(file_id=file_id)
    with get_client(headers={"Authorization": f"Bearer {token}"}) as client:
        response = client.get(url)

    if response.status_code == 404:
        raise DriveFileNotFoundError(f"File {file_id} not found in Drive")
    if response.status_code == 403:
        raise DrivePermissionError(f"Service account lacks access to file {file_id}")
    if response.is_error:
        raise RuntimeError(f"Drive API error {response.status_code}: {response.text[:200]}")

    content = response.content
    if len(content) > _MAX_FILE_BYTES:
        raise DriveFileTooLargeError(
            f"File {file_id} is {len(content)} bytes, exceeds {_MAX_FILE_BYTES} limit"
        )

    logger.info("Fetched Drive file %s (%d bytes)", file_id, len(content))
    return content


def _build_credentials(service_account_json: str):
    info = json.loads(service_account_json)
    return service_account.Credentials.from_service_account_info(info, scopes=_SCOPES)


def _get_access_token(creds) -> str:
    if not creds.valid:
        creds.refresh(Request())
    return creds.token
