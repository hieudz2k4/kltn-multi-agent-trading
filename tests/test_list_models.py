"""Verification test: list available Gemini models and verify live API connectivity."""

import os
from pathlib import Path
from dotenv import load_dotenv
from google import genai
import pytest

# Load environment configuration from project root .env
ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def clean_model_id(raw_name: str) -> str:
    """Normalize full resource name to clean model identifier."""
    prefix = "publishers/google/models/"
    return raw_name[len(prefix):] if raw_name.startswith(prefix) else raw_name.replace("models/", "")


def fetch_gemini_models() -> list[str]:
    """Retrieve list of Gemini models accessible under current credentials."""
    client = genai.Client()
    models = list(client.models.list())
    gemini_models: list[str] = []

    for model in models:
        clean_id = clean_model_id(model.name)
        if "gemini" in clean_id.lower() and not clean_id.startswith("publishers/"):
            gemini_models.append(clean_id)

    return sorted(gemini_models)


def test_list_and_verify_available_models():
    """Verify accessible Gemini models and perform live connectivity test."""
    models = fetch_gemini_models()

    print("\n--- ACCESSIBLE GEMINI MODELS ON VERTEX AI / AI STUDIO ---")
    for model_id in models:
        print(f"- {model_id}")

    print(f"\nTotal Gemini models: {len(models)}")
    assert len(models) > 0, "No Gemini models found under current credentials"

    # Live smoke test with primary flash model
    primary_model = "gemini-2.5-flash"
    client = genai.Client()
    response = client.models.generate_content(
        model=primary_model,
        contents="Echo single word: READY",
    )
    assert response.text is not None and len(response.text.strip()) > 0
    print(f"[Smoke Test PASSED] Model '{primary_model}' responded: {response.text.strip()}")


if __name__ == "__main__":
    test_list_and_verify_available_models()
