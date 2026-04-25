import httpx
from .http import get_client, raise_for_status_detail


class SupabaseError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class SupabaseClient:
    def __init__(self, url: str, service_key: str):
        self._base = url.rstrip("/") + "/rest/v1"
        self._headers = {
            "apikey": service_key,
            "Authorization": f"Bearer {service_key}",
            "Content-Type": "application/json",
        }
        self._client = get_client(headers=self._headers)

    def insert(self, table: str, data: dict) -> dict:
        """INSERT a row and return the created record."""
        response = self._client.post(
            f"{self._base}/{table}",
            json=data,
            headers={"Prefer": "return=representation"},
        )
        self._raise(response)
        rows = response.json()
        return rows[0] if rows else {}

    def upsert(self, table: str, data: dict, on_conflict: str) -> dict:
        """INSERT … ON CONFLICT DO UPDATE. Returns the upserted record."""
        response = self._client.post(
            f"{self._base}/{table}",
            json=data,
            headers={
                "Prefer": f"return=representation,resolution=merge-duplicates",
                "on_conflict": on_conflict,
            },
        )
        self._raise(response)
        rows = response.json()
        return rows[0] if rows else {}

    def update(self, table: str, match: dict, data: dict) -> None:
        """UPDATE rows matching all key=value pairs in match."""
        params = {k: f"eq.{v}" for k, v in match.items()}
        response = self._client.patch(
            f"{self._base}/{table}",
            json=data,
            params=params,
            headers={"Prefer": "return=minimal"},
        )
        self._raise(response)

    def select_one(self, table: str, match: dict) -> dict | None:
        """SELECT the first row matching all key=value pairs. Returns None if not found."""
        params = {k: f"eq.{v}" for k, v in match.items()}
        params["limit"] = "1"
        response = self._client.get(f"{self._base}/{table}", params=params)
        self._raise(response)
        rows = response.json()
        return rows[0] if rows else None

    def select_many(
        self,
        table: str,
        filters: dict[str, str] | None = None,
        order: str | None = None,
    ) -> list[dict]:
        """GET all rows matching PostgREST filter expressions.

        filters: {column: "operator.value"} e.g. {"user_id": "eq.abc", "user_confirmed": "eq.true"}
                 Use key "or" for OR: {"or": "(user_id.is.null,user_id.eq.abc)"}
                 httpx percent-encodes parens; PostgREST decodes them correctly.
        order:   PostgREST order string e.g. "priority.desc"
        Returns empty list when no rows match.
        """
        params: dict[str, str] = dict(filters or {})
        if order:
            params["order"] = order
        response = self._client.get(f"{self._base}/{table}", params=params)
        self._raise(response)
        return response.json()

    def rpc(self, func: str, args: dict | None = None) -> None:
        """Call a Postgres function via PostgREST RPC. Returns None (fire-and-forget)."""
        response = self._client.post(
            f"{self._base}/rpc/{func}",
            json=args or {},
        )
        self._raise(response)

    def _raise(self, response: httpx.Response) -> None:
        if response.is_error:
            raise SupabaseError(
                f"Supabase {response.status_code}: {response.text[:500]}",
                status_code=response.status_code,
            )
