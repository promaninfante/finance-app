import httpx


DEFAULT_TIMEOUT = httpx.Timeout(30.0)


def raise_for_status_detail(response: httpx.Response) -> None:
    """Like raise_for_status() but includes the response body in the error message."""
    if response.is_error:
        raise httpx.HTTPStatusError(
            f"HTTP {response.status_code}: {response.text[:500]}",
            request=response.request,
            response=response,
        )


def get_client(**kwargs) -> httpx.Client:
    """Return an httpx.Client with project-wide defaults."""
    kwargs.setdefault("timeout", DEFAULT_TIMEOUT)
    return httpx.Client(**kwargs)
