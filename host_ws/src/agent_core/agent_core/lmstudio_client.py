"""Small authenticated client for the LM Studio REST API."""

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional


class LMStudioError(RuntimeError):
    """Report an LM Studio transport or response error."""


class LMStudioClient:
    """Call LM Studio chat and Responses endpoints without extra packages."""

    def __init__(
        self,
        base_url: str,
        model: str,
        timeout: float = 60.0,
        api_token: Optional[str] = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout
        self._api_token = api_token or os.environ.get("LM_API_TOKEN", "")

    def chat(self, system_prompt: str, user_input: str) -> str:
        """Return text from LM Studio's native chat endpoint."""
        response = self._post(
            "/api/v1/chat",
            {
                "model": self._model,
                "system_prompt": system_prompt,
                "input": user_input,
                "temperature": 0,
            },
        )
        messages = [
            item.get("content", "")
            for item in response.get("output", [])
            if item.get("type") == "message"
        ]
        text = "\n".join(item for item in messages if item).strip()
        if not text:
            raise LMStudioError("LM Studio returned no message text")
        return text

    def call_tool(
        self,
        user_input: str,
        tool: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Return the first matching function call from Responses output."""
        response = self._post(
            "/v1/responses",
            {
                "model": self._model,
                "input": user_input,
                "tools": [tool],
                "tool_choice": "auto",
                "temperature": 0,
            },
        )
        try:
            return self._extract_tool_arguments(
                response.get("output", []),
                tool["name"],
            )
        except json.JSONDecodeError as error:
            raise LMStudioError(
                "LM Studio returned invalid tool arguments"
            ) from error

    @staticmethod
    def _extract_tool_arguments(
        output: List[Dict[str, Any]],
        tool_name: str,
    ) -> Optional[Dict[str, Any]]:
        for item in output:
            item_name = item.get("name") or item.get("tool")
            item_type = item.get("type")
            if item_name != tool_name or item_type not in {
                "function_call",
                "tool_call",
            }:
                continue
            arguments = item.get("arguments", {})
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            if isinstance(arguments, dict):
                return arguments
        return None

    def _post(self, path: str, body: Dict[str, Any]) -> Dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        request = urllib.request.Request(
            self._base_url + path,
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._timeout,
            ) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise LMStudioError(
                f"LM Studio HTTP {error.code}: {detail[:300]}"
            ) from error
        except (urllib.error.URLError, TimeoutError) as error:
            message = f"LM Studio request failed: {error}"
            raise LMStudioError(message) from error
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise LMStudioError("LM Studio returned invalid JSON") from error
        if not isinstance(payload, dict):
            raise LMStudioError("LM Studio returned a non-object response")
        return payload
