"""
backend/services/gemini_svc.py — Optional Gemini LLM Enhancement

This module is ONLY imported when GEMINI_API_KEY is set in .env.
The core application functions identically without it.
"""

import logging
from backend.core.config import get_settings

log = logging.getLogger("sfeid.gemini")
cfg = get_settings()

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(api_key=cfg.gemini_api_key)
    return _client


def enhance_chat_response(user_message: str, rule_response: str, ctx: dict) -> str:
    """
    Enhance a rule-based chat response with Gemini.
    Uses the rule response as a base — Gemini makes it more natural.
    """
    client = _get_client()

    facility_name = "SFEID College of Engineering"
    live          = ctx.get("live", {})
    score         = ctx.get("score", "N/A")

    system_prompt = (
        f"You are SFEID Assistant, the AI facility manager for {facility_name}. "
        f"Current sustainability score: {score}/100. "
        f"You have been given a rule-based answer. Improve its language to be concise, "
        f"professional, and helpful. Keep all facts exactly as provided. "
        f"Do not add information not present in the rule answer. "
        f"Respond in 3–5 sentences maximum."
    )

    prompt = (
        f"Admin asked: {user_message}\n\n"
        f"Rule-based answer: {rule_response}\n\n"
        f"Improve the response language while keeping all facts exactly the same."
    )

    try:
        interaction = client.interactions.create(
            model="gemini-3.8-flash",
            system_instruction=system_prompt,
            input=prompt,
            store=False,   # no storage needed for chat
        )
        return interaction.output_text or rule_response
    except Exception as exc:
        log.warning(f"Gemini API call failed: {exc}")
        return rule_response


def generate_llm_recommendations(facility_snapshot: dict) -> list[dict]:
    """
    Generate AI recommendations using Gemini.
    Only called when GEMINI_API_KEY is set.
    """
    client = _get_client()

    prompt = (
        f"You are a sustainability consultant for an engineering college in India. "
        f"Based on this facility data snapshot, provide 3 specific, actionable recommendations "
        f"to improve energy efficiency, air quality, or water conservation. "
        f"Format as JSON array: [{{'title':..., 'description':..., 'category':..., 'action_items':[...]}}]\n\n"
        f"Data: {facility_snapshot}"
    )

    try:
        from google.genai import types
        interaction = client.interactions.create(
            model="gemini-3.8-flash",
            input=prompt,
            generation_config=types.GenerationConfig(
                response_mime_type="application/json"
            ),
            store=False,
        )
        import json
        return json.loads(interaction.output_text or "[]")
    except Exception as exc:
        log.warning(f"Gemini recommendations failed: {exc}")
        return []
