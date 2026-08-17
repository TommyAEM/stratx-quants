"""
StratX Production LLM Client with Glass Box Telemetry & Institutional Reasoning (llm_client.py)
Implements:
1. Glass Box Telemetry: Streams the agent's raw cognitive thinking process (reasoning_content)
   and formatted cognitive output before extracting and validating JSON.
2. Full context token budget (max_tokens: 4096) so deep thinking does not truncate output.
3. Schema validation with automatic self-correcting retry loop.
Zero external dependency: Built using standard library urllib.request.
"""

import os
import re
import json
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

class StratXLLMClient:
    NANOGPT_BASE_URL = "https://nano-gpt.com/api/v1"
    NANOGPT_MODEL = "deepseek/deepseek-v4-pro-0813:thinking"
    NANOGPT_KEY = "sk-nano-0e6f9dde-f938-492c-ba18-750091258b4a"

    def __init__(self):
        pass

    def extract_json(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        
        md_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
        if md_match:
            candidate = md_match.group(1).strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if start_obj != -1 and end_obj != -1 and end_obj > start_obj:
            candidate = text[start_obj:end_obj + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        start_arr = text.find("[")
        end_arr = text.rfind("]")
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            candidate = text[start_arr:end_arr + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from LLM response:\n{text[:300]}...")

    def call_llm(
        self,
        messages: List[Dict[str, str]],
        role_tier: str = "PRO",
        role_name: str = "QUANT_AGENT",
        max_tokens: int = 4096,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        url = f"{self.NANOGPT_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.NANOGPT_KEY}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.NANOGPT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": False
        }

        data_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data_bytes, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=90) as response:
                res_body = response.read().decode("utf-8")
                res_json = json.loads(res_body)
                
                choice = res_json["choices"][0]["message"]
                content = choice.get("content", "")
                reasoning = choice.get("reasoning", choice.get("reasoning_content", ""))
                
                return {
                    "content": content,
                    "reasoning_content": reasoning,
                    "usage": res_json.get("usage", {})
                }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"LLM API HTTP {e.code} Error: {err_msg}")
        except Exception as e:
            raise RuntimeError(f"LLM API Connection Error: {str(e)}")

    def call_with_schema_retry(
        self,
        messages: List[Dict[str, str]],
        required_keys: List[str],
        role_tier: str = "PRO",
        role_name: str = "QUANT_AGENT",
        max_retries: int = 3
    ) -> Dict[str, Any]:
        current_messages = list(messages)
        
        for attempt in range(1, max_retries + 1):
            try:
                res = self.call_llm(current_messages, role_tier=role_tier, role_name=role_name, max_tokens=4096)
                parsed = self.extract_json(res["content"])
                
                if isinstance(parsed, dict):
                    missing = [k for k in required_keys if k not in parsed]
                    if missing:
                        raise ValueError(f"Schema violation: missing required keys: {missing}")
                
                return {
                    "status": "SUCCESS",
                    "data": parsed,
                    "reasoning": res.get("reasoning_content"),
                    "attempts": attempt
                }
            except Exception as e:
                if attempt == max_retries:
                    raise RuntimeError(f"LLM failed schema validation after {max_retries} attempts: {e}")
                
                current_messages.append({"role": "assistant", "content": res.get("content", "") if 'res' in locals() else ""})
                current_messages.append({
                    "role": "user",
                    "content": f"ERROR: Your previous response failed schema validation:\n{str(e)}\nYou must output ONLY a valid JSON object matching all required keys: {required_keys}. Do not include conversational text."
                })
                time.sleep(1.0)
