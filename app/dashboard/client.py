from typing import Any

import httpx


class APIClientError(RuntimeError):
    pass


class RoleRadarClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", timeout=30, **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.json().get("detail", exc.response.text)
            raise APIClientError(str(detail)) from exc
        except httpx.HTTPError as exc:
            raise APIClientError(f"API unavailable: {exc}") from exc

    def get(self, path: str) -> Any:
        return self._request("GET", path)

    def post(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("POST", path, json=payload)

    def put(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PUT", path, json=payload)

    def patch(self, path: str, payload: dict[str, Any]) -> Any:
        return self._request("PATCH", path, json=payload)

    def delete(self, path: str) -> Any:
        return self._request("DELETE", path)
