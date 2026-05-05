"""Proxy actor to forward RAN API calls to Omniver-RAN backend."""
import json
import requests
from django.http import JsonResponse
from main.utils.env_loader import get_str

OMNIVERSE_BACKEND_URL = get_str("OMNIVERSE_BACKEND_URL", "http://172.17.0.1:8001")


class OmniverseProxyActor:
    """Transparently proxy all /RAN/* requests to Omniver-RAN backend."""

    @staticmethod
    def proxy(request, subpath):
        """Forward POST request to Omniver-RAN backend.

        Args:
            request: Django HTTP request
            subpath: path after /RAN/ (e.g., 'Scene/BuildingController/create')

        Returns:
            JsonResponse with proxied response or error
        """
        target_url = f"{OMNIVERSE_BACKEND_URL}/api/v0.1/RAN/{subpath}"
        try:
            body = json.loads(request.body) if request.body else {}
            resp = requests.post(target_url, json=body, timeout=30)
            if resp.status_code == 204:
                return JsonResponse({"success": True, "message": "Deleted successfully"}, status=204)
            return JsonResponse(resp.json(), status=resp.status_code)
        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)}, status=502)
