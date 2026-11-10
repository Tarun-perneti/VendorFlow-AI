"""
llm.py — LLM client for VendorFlow AI

Handles all communication with the Google Gemini API.
Provides a clean interface and graceful fallback when the API is unavailable.

Why a separate file?
- Single place to manage API keys, model selection, and error handling.
- Easy to swap LLM providers in the future.
- The rest of the codebase just calls `llm.ask(prompt)` without worrying about API details.
"""

import os
import json
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def get_gemini_client():
    """
    Create and return a Gemini client.
    Returns None if the API key is not set.
    
    Checks two sources for the API key:
    1. Streamlit secrets (for Streamlit Cloud deployment)
    2. Environment variable / .env file (for local development)
    """
    api_key = os.getenv("GEMINI_API_KEY", "")

    # Also check Streamlit secrets (used on Streamlit Cloud)
    if not api_key or api_key == "your_gemini_api_key_here":
        try:
            import streamlit as st
            api_key = st.secrets.get("GEMINI_API_KEY", "")
        except Exception:
            pass

    if not api_key or api_key == "your_gemini_api_key_here":
        return None

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        return client
    except Exception as e:
        print(f"[LLM] Failed to create Gemini client: {e}")
        return None


def ask_llm(prompt: str, system_instruction: str = "") -> str | None:
    """
    Send a prompt to Gemini and return the text response.
    
    Returns None if:
    - API key is not configured
    - API call fails
    - Response is empty
    
    The caller should always have a fallback plan when this returns None.
    
    Args:
        prompt: The user/task prompt to send.
        system_instruction: Optional system instruction to guide the model's behavior.
    
    Returns:
        The model's text response, or None on failure.
    """
    client = get_gemini_client()
    if client is None:
        print("[LLM] No API key configured — skipping LLM call.")
        return None

    try:
        # Use gemini-2.0-flash: fast, cheap, good at structured extraction
        config = {}
        if system_instruction:
            config["system_instruction"] = system_instruction

        response = client.models.generate_content(
           model="gemini-3.8-flash",
            contents=prompt,
            config=config if config else None,
        )
        print("[LLM] Gemini API call successful")

        if response and response.text:
            return response.text.strip()
        return None

    except Exception as e:
        print(f"[LLM] API call failed: {e}")
        return None


def extract_json_from_llm(prompt: str, system_instruction: str = "") -> dict | None:
    """
    Send a prompt to the LLM and parse the response as JSON.
    
    Why? We often ask the LLM to return structured data (e.g., extracted
    document fields). This helper handles the common pattern of:
    1. Ask the LLM
    2. Strip markdown code fences if present
    3. Parse as JSON
    4. Return None on failure
    
    Returns:
        Parsed dict, or None on failure.
    """
    response = ask_llm(prompt, system_instruction)
    if response is None:
        return None

    try:
        # The LLM sometimes wraps JSON in ```json ... ``` code fences
        text = response.strip()
        if text.startswith("```"):
            # Remove the opening fence (```json or ```)
            first_newline = text.index("\n")
            text = text[first_newline + 1:]
        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())

    except (json.JSONDecodeError, ValueError) as e:
        print(f"[LLM] Failed to parse JSON from response: {e}")
        print(f"[LLM] Raw response was: {response[:500]}")
        return None
    if __name__ == "__main__":
        result = ask_llm("Reply with exactly: Gemini is working")
        print("Gemini test result:", result)
    

