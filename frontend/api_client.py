"""Thin HTTP client for the MVP FastAPI backend."""

from __future__ import annotations

import os
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8001"


def base_url() -> str:
    return os.environ.get("API_BASE_URL", DEFAULT_BASE_URL).rstrip("/")


class ApiClient:
    def __init__(self, url: str | None = None, timeout: float = 60.0) -> None:
        self._base = (url or base_url()).rstrip("/")
        self._timeout = timeout
        self._client = httpx.Client(base_url=self._base, timeout=timeout)

    def _request(self, method: str, path: str, *, timeout: float | None = None, **kwargs) -> httpx.Response:
        if timeout is not None:
            with httpx.Client(base_url=self._base, timeout=timeout) as client:
                return client.request(method, path, **kwargs)
        return self._client.request(method, path, **kwargs)

    def close(self) -> None:
        self._client.close()

    def health(self) -> dict[str, Any]:
        response = self._client.get("/health")
        response.raise_for_status()
        return response.json()

    def list_conferences(
        self,
        *,
        field: str | None = None,
        region: str | None = None,
        status: str | None = None,
        has_email: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"limit": limit}
        if field:
            params["field"] = field
        if region:
            params["region"] = region
        if status:
            params["status"] = status
        if has_email is not None:
            params["has_email"] = has_email
        response = self._client.get("/api/conferences", params=params)
        response.raise_for_status()
        return response.json()

    def get_conference(self, conference_id: str) -> dict[str, Any]:
        response = self._client.get(f"/api/conferences/{conference_id}")
        response.raise_for_status()
        return response.json()

    def update_conference(self, conference_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.patch(f"/api/conferences/{conference_id}", json=payload)
        response.raise_for_status()
        return response.json()

    def update_organizer(self, organizer_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self._client.patch(f"/api/organizers/{organizer_id}", json=payload)
        response.raise_for_status()
        return response.json()

    def run_full_pipeline(
        self,
        *,
        field: str,
        region: str,
        selected_months: list[str],
        max_conferences: int = 10,
        manual_official_url: str = "",
        pipeline_timeout: float = 900.0,
    ) -> dict[str, Any]:
        payload = {
            "field": field,
            "region": region,
            "selected_months": selected_months,
            "max_conferences": max_conferences,
            "manual_official_url": manual_official_url.strip(),
            "execute_search": True,
            "execute_crawl": True,
            "execute_extract": True,
        }
        response = self._request(
            "POST",
            "/api/search-runs",
            json=payload,
            timeout=pipeline_timeout,
        )
        response.raise_for_status()
        return response.json()

    def export_leads_xlsx(self) -> bytes:
        response = self._client.get("/api/export/leads.xlsx")
        response.raise_for_status()
        return response.content

    def retry_crawl(self, conference_id: str) -> dict[str, Any]:
        response = self._client.post(f"/api/conferences/{conference_id}/retry-crawl")
        response.raise_for_status()
        return response.json()

