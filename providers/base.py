"""
Provider contract — every provider module must expose:

    NAME: str          human-readable name (shown in terminal + Slack)
    PROVIDER_KEY: str  snake_case key (used in filenames and reports)

    def trigger() -> dict:
        Trigger one outbound call.
        Returns: {"status": "ok", "http_code": int, "response": str}
        Raises:  httpx.HTTPStatusError on non-2xx
"""
