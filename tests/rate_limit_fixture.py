"""Inert native Workers rate-limit bindings for local production fixtures."""
from norulo_server.cloudflare_auth_admission import API_RATE_LIMITS


class AdmitAll:
    def __init__(self):
        self.keys = []

    async def limit(self, options):
        self.keys.append(options["key"])
        return {"success": True}


def admitting_api_rate_limits():
    """Production fixtures test application behavior beyond frequency admission."""
    return {name: AdmitAll() for name, _, _ in API_RATE_LIMITS}
