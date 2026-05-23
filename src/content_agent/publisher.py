"""Buffer API publisher for scheduling social media posts."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from content_agent.models import ContentPiece

log = logging.getLogger(__name__)

BUFFER_API_BASE = "https://api.bufferapp.com/1"


class BufferPublisher:
    def __init__(
        self,
        access_token: str = "",
        profile_ids: dict[str, str] | None = None,
    ):
        self._token = access_token
        self._profile_ids = profile_ids or {}

    def has_credentials(self) -> bool:
        return bool(self._token)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def schedule_post(
        self,
        piece: ContentPiece,
        scheduled_time: str | None = None,
    ) -> dict:
        if not self._token:
            log.warning("No Buffer access token — skipping publish")
            return {}

        profile_id = self._profile_ids.get(piece.platform.value, "")
        if not profile_id:
            log.warning("No Buffer profile ID for %s — skipping", piece.platform.value)
            return {}

        body = piece.body
        if piece.hashtags:
            hashtag_str = " ".join(f"#{h}" for h in piece.hashtags)
            body = f"{body}\n\n{hashtag_str}"

        payload: dict = {
            "text": body,
            "profile_ids[]": profile_id,
        }

        if scheduled_time:
            payload["scheduled_at"] = scheduled_time

        if piece.media_paths:
            payload["media[photo]"] = piece.media_paths[0]

        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{BUFFER_API_BASE}/updates/create.json",
                params={"access_token": self._token},
                data=payload,
            )
            resp.raise_for_status()

        result = resp.json()
        log.info(
            "Scheduled post for %s: %s",
            piece.platform.value,
            result.get("updates", [{}])[0].get("id", "unknown"),
        )
        return result

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
    def get_profiles(self) -> list[dict]:
        if not self._token:
            return []

        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{BUFFER_API_BASE}/profiles.json",
                params={"access_token": self._token},
            )
            resp.raise_for_status()
        return resp.json()

    def publish_all(
        self,
        pieces: list[ContentPiece],
        posting_times: dict[str, str] | None = None,
    ) -> list[dict]:
        results = []
        for piece in pieces:
            scheduled_time = (posting_times or {}).get(piece.platform.value)
            try:
                result = self.schedule_post(piece, scheduled_time)
                results.append(result)
            except Exception as e:
                log.error("Failed to schedule %s for %s: %s",
                          piece.content_type.value, piece.platform.value, e)
                results.append({"error": str(e)})
        return results
