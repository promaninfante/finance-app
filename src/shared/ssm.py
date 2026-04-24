import boto3
from functools import lru_cache


@lru_cache(maxsize=None)
def load_secrets(region: str = "eu-west-1") -> dict[str, str]:
    """Fetch all /finance/* SecureString parameters in one paginated call.

    Cached indefinitely — warm Lambda invocations skip SSM entirely.
    Keys are the last path segment: "supabase_url", "ingest_shared_secret", etc.
    """
    client = boto3.client("ssm", region_name=region)
    paginator = client.get_paginator("get_parameters_by_path")
    params: dict[str, str] = {}
    for page in paginator.paginate(Path="/finance", WithDecryption=True):
        for p in page["Parameters"]:
            key = p["Name"].rsplit("/", 1)[-1]
            params[key] = p["Value"]
    return params
