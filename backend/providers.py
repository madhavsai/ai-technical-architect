"""LLM provider abstraction - Gemini (default, free tier) or local Ollama,
switchable per-request. Pattern and fixes below are lifted directly from
`ideas/ui project/Live Visual Tutor/prototype/backend/llm.py`, already
verified working on this machine.
"""

import json
import os

# Must run before importing google.genai or ollama - both construct an httpx
# client that reads SSL_CERT_FILE if it's set at all, even to a broken path.
# This machine's conda activation scripts set SSL_CERT_FILE to a path that
# doesn't exist, which crashes client construction with a raw
# "FileNotFoundError" unrelated to API keys or Ollama itself.
import certifi  # noqa: E402

_cert_file = os.environ.get("SSL_CERT_FILE")
if _cert_file and not os.path.exists(_cert_file):
    os.environ["SSL_CERT_FILE"] = certifi.where()

from google import genai  # noqa: E402
from google.genai import types  # noqa: E402
from google.genai.errors import ClientError  # noqa: E402
import ollama  # noqa: E402

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")

# This machine has OLLAMA_HOST=0.0.0.0 set globally (a bind address, for other
# tools that need Ollama reachable on the network). Ollama's Python package
# reads that same var for its *client* default and tries to connect to
# 0.0.0.0, which fails - always pass an explicit host instead.
OLLAMA_HOST = os.environ.get("OLLAMA_LOCAL_HOST", "http://127.0.0.1:11434")
# "qwen3-coder:30b" itself isn't pulled under that literal tag on this machine -
# only a 16k-context variant built FROM it is (same naming convention as this
# machine's gemma4-8k/gemma4-16k variants). Checked live against a running
# Ollama server rather than assumed - override via OLLAMA_MODEL if that changes.
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3-coder-16k:latest")

_PLACEHOLDER_KEY = "your-api-key-here"
_gemini_client: "genai.Client | None" = None


def _get_gemini_client() -> "genai.Client":
    global _gemini_client
    if _gemini_client is None:
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or api_key == _PLACEHOLDER_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Paste a free key from "
                "https://aistudio.google.com/apikey into backend/.env, or use "
                "the ollama provider instead."
            )
        _gemini_client = genai.Client(api_key=api_key)
    return _gemini_client


def _get_ollama_client() -> ollama.Client:
    return ollama.Client(host=OLLAMA_HOST)


def gemini_available() -> bool:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    return bool(key) and key != _PLACEHOLDER_KEY


def ollama_available() -> bool:
    try:
        tags = _get_ollama_client().list()
        names = [m.model for m in tags.models]
        base = OLLAMA_MODEL.split(":")[0]
        return any(n.split(":")[0] == base for n in names)
    except Exception:
        return False


MAX_JSON_RETRIES = int(os.environ.get("MAX_JSON_RETRIES", "2"))


def generate_json(system_prompt: str, user_prompt: str, schema: dict, provider: str) -> dict:
    """Run a schema-constrained generation call against the given provider,
    retrying on a JSON parse failure. Grammar-constrained decoding still
    occasionally produces invalid JSON (truncation against the model's output
    budget, an escaping slip) - especially on a local model working through
    the larger schemas added after the 2026-09-16 audit pass (the merged
    architecture + a changelog, in particular). A fresh attempt is cheap
    relative to a failed pipeline run and usually succeeds; the error message
    is only ever seen if every attempt fails the same way.
    """
    call = _gemini_generate_json if provider == "gemini" else _ollama_generate_json
    if provider not in ("gemini", "ollama"):
        raise ValueError(f"unknown provider: {provider}")

    last_error: Exception | None = None
    for attempt in range(MAX_JSON_RETRIES + 1):
        raw_text = call(system_prompt, user_prompt, schema)
        try:
            if not raw_text:
                raise json.JSONDecodeError("empty response", raw_text or "", 0)
            return json.loads(raw_text)
        except json.JSONDecodeError as e:
            last_error = e
            snippet = (raw_text or "")[:200].replace("\n", "\\n")
            print(
                f"[providers] {provider} produced invalid JSON on attempt "
                f"{attempt + 1}/{MAX_JSON_RETRIES + 1}: {e}. First 200 chars: {snippet!r}"
            )
    raise RuntimeError(
        f"{provider} produced invalid JSON {MAX_JSON_RETRIES + 1} times in a row "
        f"for the same call - last error: {last_error}"
    )


def _gemini_generate_json(system_prompt: str, user_prompt: str, schema: dict) -> str:
    try:
        response = _get_gemini_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.4,
            ),
        )
    except ClientError as e:
        raise RuntimeError(f"Gemini request failed: {e}") from e
    return response.text


def _ollama_generate_json(system_prompt: str, user_prompt: str, schema: dict) -> str:
    try:
        response = _get_ollama_client().chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            format=schema,  # grammar-constrained structured output, not just prompted JSON
            options={
                "temperature": 0.4,
                # Explicit and generous - the schemas grew substantially in the
                # 2026-09-16 audit pass (changelog, ids, extra fields), and an
                # implicit/low default output budget is a real truncation risk
                # on the largest calls (revise, the merged review schemas).
                "num_predict": 8192,
            },
        )
    except Exception as e:
        raise RuntimeError(
            f"Ollama request failed ({e}). Is it running? Start with: ollama serve "
            f"- and make sure {OLLAMA_MODEL} is pulled."
        ) from e
    return response["message"]["content"]
