"""Provider-isolated LLM reasoning with per-run accounting and strict JSON output."""
from __future__ import annotations
import json, re
from dataclasses import dataclass
from typing import Any
import httpx
from ..core.settings import settings

@dataclass
class LLMStats:
    calls:int=0; input_tokens:int=0; output_tokens:int=0; failures:int=0

class LLMProvider:
    def __init__(self): self.stats=LLMStats()
    async def complete_json(self, system:str, user:str, schema_hint:dict[str,Any])->dict[str,Any]: raise NotImplementedError

class DisabledProvider(LLMProvider):
    async def complete_json(self, system, user, schema_hint): return {}

class OpenAICompatibleProvider(LLMProvider):
    """Uses the OpenAI-compatible chat endpoint so the project can run against
    OpenAI or an internal gateway. Repository access is never delegated to it."""
    async def complete_json(self, system, user, schema_hint):
        if not settings.llm_api_key: raise RuntimeError("LLM_API_KEY is required")
        url=settings.llm_base_url.rstrip()+"/chat/completions"
        payload={"model":settings.llm_model,"messages":[{"role":"system","content":system},{"role":"user","content":user}],"temperature":0.1,"response_format":{"type":"json_object"}}
        headers={"Authorization":f"Bearer {settings.llm_api_key}","Content-Type":"application/json"}
        try:
            async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
                r=await client.post(url,headers=headers,json=payload); r.raise_for_status(); body=r.json()
            usage=body.get("usage",{}) or {}; self.stats.calls+=1
            self.stats.input_tokens+=int(usage.get("prompt_tokens",usage.get("input_tokens",0)) or 0)
            self.stats.output_tokens+=int(usage.get("completion_tokens",usage.get("output_tokens",0)) or 0)
            content=body["choices"][0]["message"]["content"]
            if isinstance(content,list): content="".join(x.get("text","") for x in content if isinstance(x,dict))
            return extract_json(content)
        except Exception:
            self.stats.failures+=1; raise

def extract_json(content:str)->dict[str,Any]:
    try:return json.loads(content.strip())
    except json.JSONDecodeError:
        m=re.search(r"\{.*\}",content,re.S)
        if not m: raise ValueError("LLM returned no JSON object")
        return json.loads(m.group(0))

def get_provider()->LLMProvider:
    return OpenAICompatibleProvider() if settings.llm_provider in {"openai","openai_compatible"} else DisabledProvider()
