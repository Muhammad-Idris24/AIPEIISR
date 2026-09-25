"""Replaceable, non-authoritative development providers.

Provider selection is driven purely by environment variables. The deterministic
Mock providers are always the default fallback so test and development loops do
not depend on network or credentials.

Env variables:
    LLM_PROVIDER        = mock | ollama | huggingface | openrouter
    EMBEDDING_PROVIDER  = mock | ollama | huggingface
    OLLAMA_URL          = http://localhost:11434
    OLLAMA_LLM_MODEL    = llama3.2
    OLLAMA_EMB_MODEL    = nomic-embed-text
    HF_API_TOKEN        = hf_…      (for Hugging Face Inference Providers)
    HF_LLM_MODEL        = meta-llama/Llama-3.1-8B-Instruct
    HF_EMB_MODEL        = sentence-transformers/all-MiniLM-L6-v2
    OPENROUTER_API_KEY  = sk-or-…
    OPENROUTER_MODEL    = meta-llama/llama-3.1-8b-instruct
    AI_TIMEOUT_SECONDS  = 10
"""
from __future__ import annotations

import os
import json
import logging
from dataclasses import dataclass
from hashlib import sha256
from typing import Any, Protocol
from urllib import request, error as urlerror

log = logging.getLogger("aipieisr.providers")

_TIMEOUT = int(os.getenv("AI_TIMEOUT_SECONDS", "10"))


@dataclass
class Analysis:
    claim: str | None
    entities: list[str]
    uncertainty: str
    citations: list[str]


class LLMProvider(Protocol):
    name: str
    def analyze(self, text: str, reference: str) -> Analysis: ...


class EmbeddingProvider(Protocol):
    name: str
    dim: int
    def embed(self, text: str) -> list[float]: ...
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(t) for t in texts]


# ---------------------------------------------------------------------------
# Deterministic local fallbacks (always available)
# ---------------------------------------------------------------------------
class MockLLMProvider:
    name = "mock"
    def analyze(self, text: str, reference: str) -> Analysis:
        cleaned = " ".join(text.split())[:500]
        return Analysis(cleaned or None, [], "high", [reference] if reference else [])


class MockEmbeddingProvider:
    name = "mock"
    dim = 8
    def embed(self, text: str) -> list[float]:
        digest = sha256(text.encode()).digest()
        return [round(byte / 255, 4) for byte in digest[: self.dim]]


# ---------------------------------------------------------------------------
# Shared HTTP helper
# ---------------------------------------------------------------------------
def _post_json(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict | None:
    try:
        data = json.dumps(payload).encode()
        req = request.Request(url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        for k, v in (headers or {}).items():
            req.add_header(k, v)
        with request.urlopen(req, timeout=_TIMEOUT) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return json.loads(body)
    except (urlerror.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        log.warning("Provider request to %s failed: %s", url, exc)
        return None


# ---------------------------------------------------------------------------
# Ollama (local HTTP at OLLAMA_URL)
# ---------------------------------------------------------------------------
class OllamaLLMProvider:
    def __init__(self, model: str | None = None, url: str | None = None):
        self.url = (url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_LLM_MODEL", "llama3.2")
        self.name = f"ollama/{self.model}"
    def analyze(self, text: str, reference: str) -> Analysis:
        prompt = (
            "You are a non-authoritative analyst assistant. Respond ONLY with valid JSON "
            "containing {claim: string|null, entities: string[], uncertainty: low|medium|high, "
            "citations: string[]}. Do not invent sources. If unsure, set claim null, "
            "uncertainty high, entities [], citations [].\n\n"
            f"Reference context: {reference or '(none)'}\n\nText:\n{text[:4000]}\n"
        )
        resp = _post_json(
            f"{self.url}/api/generate",
            {"model": self.model, "prompt": prompt, "stream": False, "format": "json",
             "options": {"temperature": 0.0}},
        )
        if resp and isinstance(resp.get("response"), str):
            try:
                data = json.loads(resp["response"])
                return Analysis(
                    claim=data.get("claim"),
                    entities=list(data.get("entities") or [])[:50],
                    uncertainty=(data.get("uncertainty") or "high").lower()[:16],
                    citations=list(data.get("citations") or [])[:20],
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return Analysis(None, [], "high", [])


class OllamaEmbeddingProvider:
    def __init__(self, model: str | None = None, url: str | None = None):
        self.url = (url or os.getenv("OLLAMA_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or os.getenv("OLLAMA_EMB_MODEL", "nomic-embed-text")
        self.name = f"ollama/{self.model}"
        self.dim = 0  # populated lazily after first call
    def embed(self, text: str) -> list[float]:
        resp = _post_json(
            f"{self.url}/api/embeddings",
            {"model": self.model, "prompt": text[:8000]},
        )
        vec = resp and resp.get("embedding")
        if isinstance(vec, list) and vec:
            self.dim = self.dim or len(vec)
            return [float(x) for x in vec]
        return MockEmbeddingProvider().embed(text)


# ---------------------------------------------------------------------------
# Hugging Face Inference Providers (HF_API_TOKEN required)
# ---------------------------------------------------------------------------
class HuggingFaceLLMProvider:
    def __init__(self, model: str | None = None, token: str | None = None):
        self.token = token or os.getenv("HF_API_TOKEN", "")
        self.model = model or os.getenv("HF_LLM_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
        self.api_url = "https://router.huggingface.co/hf-inference/models"
        self.name = f"hf/{self.model}"
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}
    def analyze(self, text: str, reference: str) -> Analysis:
        if not self.token:
            return MockLLMProvider().analyze(text, reference)
        messages = [
            {"role": "system",
             "content": "Return ONLY valid JSON with keys: claim (string|null), "
                        "entities (string[]), uncertainty (low|medium|high), citations (string[]). "
                        "Be conservative. Do not hallucinate sources. If uncertain, return "
                        "{claim:null,entities:[],uncertainty:high,citations:[]}."},
            {"role": "user",
             "content": f"Reference context: {reference or '(none)'}\n\nText to analyze:\n{text[:3500]}"},
        ]
        resp = _post_json(
            f"{self.api_url}/{self.model}/v1/chat/completions",
            {"model": self.model, "messages": messages, "max_tokens": 300, "temperature": 0.0,
             "response_format": {"type": "json_object"}},
            self._headers(),
        )
        content = (resp and resp.get("choices") or [{}])[0].get("message", {}).get("content") if resp else None
        if content:
            try:
                data = json.loads(content)
                return Analysis(
                    claim=data.get("claim"),
                    entities=list(data.get("entities") or [])[:50],
                    uncertainty=(data.get("uncertainty") or "high").lower()[:16],
                    citations=list(data.get("citations") or [])[:20],
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return Analysis(None, [], "high", [])


class HuggingFaceEmbeddingProvider:
    def __init__(self, model: str | None = None, token: str | None = None):
        self.token = token or os.getenv("HF_API_TOKEN", "")
        self.model = model or os.getenv("HF_EMB_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
        self.api_url = "https://router.huggingface.co/hf-inference/models"
        self.name = f"hf/{self.model}"
        self.dim = 0
    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}
    def embed(self, text: str) -> list[float]:
        if not self.token:
            return MockEmbeddingProvider().embed(text)
        resp = _post_json(
            f"{self.api_url}/{self.model}/v1/embeddings",
            {"model": self.model, "input": [text[:8000]]},
            self._headers(),
        )
        data = (resp and resp.get("data") or [{}])[0].get("embedding") if resp else None
        if isinstance(data, list) and data:
            self.dim = self.dim or len(data)
            return [float(x) for x in data]
        return MockEmbeddingProvider().embed(text)
    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not self.token:
            return [MockEmbeddingProvider().embed(t) for t in texts]
        chunks = [t[:8000] for t in texts]
        resp = _post_json(
            f"{self.api_url}/{self.model}/v1/embeddings",
            {"model": self.model, "input": chunks},
            self._headers(),
        )
        if resp and isinstance(resp.get("data"), list):
            rows = {it.get("index", i): it.get("embedding") for i, it in enumerate(resp["data"])}
            out = []
            for i, orig in enumerate(texts):
                vec = rows.get(i)
                if isinstance(vec, list) and vec:
                    self.dim = self.dim or len(vec)
                    out.append([float(x) for x in vec])
                else:
                    out.append(MockEmbeddingProvider().embed(orig))
            return out
        return [MockEmbeddingProvider().embed(t) for t in texts]


# ---------------------------------------------------------------------------
# OpenRouter (generic hosted LLM router — OPENROUTER_API_KEY required)
# ---------------------------------------------------------------------------
class OpenRouterLLMProvider:
    def __init__(self, model: str | None = None, key: str | None = None):
        self.key = key or os.getenv("OPENROUTER_API_KEY", "")
        self.model = model or os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.1-8b-instruct")
        self.name = f"openrouter/{self.model}"
    def analyze(self, text: str, reference: str) -> Analysis:
        if not self.key:
            return MockLLMProvider().analyze(text, reference)
        messages = [
            {"role": "system", "content": "Respond ONLY as valid JSON: {claim:string|null, entities:string[], uncertainty:low|medium|high, citations:string[]}. Be conservative."},
            {"role": "user", "content": f"Reference: {reference or '(none)'}\n\nText:\n{text[:3500]}"},
        ]
        resp = _post_json(
            "https://openrouter.ai/api/v1/chat/completions",
            {"model": self.model, "messages": messages, "max_tokens": 300, "temperature": 0.0,
             "response_format": {"type": "json_object"}},
            {"Authorization": f"Bearer {self.key}", "HTTP-Referer": "https://aipieisr.local", "X-Title": "AIPEIISR"},
        )
        content = (resp and resp.get("choices") or [{}])[0].get("message", {}).get("content") if resp else None
        if content:
            try:
                data = json.loads(content)
                return Analysis(
                    claim=data.get("claim"),
                    entities=list(data.get("entities") or [])[:50],
                    uncertainty=(data.get("uncertainty") or "high").lower()[:16],
                    citations=list(data.get("citations") or [])[:20],
                )
            except (json.JSONDecodeError, TypeError):
                pass
        return Analysis(None, [], "high", [])


# ---------------------------------------------------------------------------
# Factories
# ---------------------------------------------------------------------------
def get_llm_provider(kind: str | None = None) -> LLMProvider:
    k = (kind or os.getenv("LLM_PROVIDER", "mock") or "").lower().strip()
    try:
        if k == "ollama": return OllamaLLMProvider()
        if k == "huggingface" or k == "hf": return HuggingFaceLLMProvider()
        if k == "openrouter": return OpenRouterLLMProvider()
    except Exception as exc:
        log.warning("Falling back to MockLLMProvider (%s): %s", k, exc)
    return MockLLMProvider()


def get_embedding_provider(kind: str | None = None) -> EmbeddingProvider:
    k = (kind or os.getenv("EMBEDDING_PROVIDER", "mock") or "").lower().strip()
    try:
        if k == "ollama": return OllamaEmbeddingProvider()
        if k == "huggingface" or k == "hf": return HuggingFaceEmbeddingProvider()
    except Exception as exc:
        log.warning("Falling back to MockEmbeddingProvider (%s): %s", k, exc)
    return MockEmbeddingProvider()
