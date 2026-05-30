"""
mimo_client.py — MiMo AI client for generating onchain intelligence captions.

Uses MiMo v2.5 (OpenAI-compatible API) to generate professional,
data-driven content from onchain signals.
"""

import json
import logging
import requests
from typing import Optional

from config.settings import MIMO_API_KEY, MIMO_BASE_URL, MIMO_MODEL

logger = logging.getLogger(__name__)


class MiMoClient:
    def __init__(self):
        self.api_key = MIMO_API_KEY
        self.base_url = MIMO_BASE_URL.rstrip("/")
        self.model = MIMO_MODEL

    def generate(self, system_prompt: str, user_prompt: str,
                 temperature: float = 0.7, max_tokens: int = 500) -> str:
        """Send a chat completion request to MiMo."""
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            logger.error(f"MiMo API error: {e}")
            raise

    def generate_json(self, system_prompt: str, user_prompt: str,
                      temperature: float = 0.3) -> dict:
        """Generate and parse JSON response."""
        raw = self.generate(system_prompt, user_prompt, temperature=temperature)
        # Extract JSON from response (may be wrapped in markdown code block)
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0]
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0]
        return json.loads(raw.strip())
