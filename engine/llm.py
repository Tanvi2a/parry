"""The ONLY file that talks to an LLM. One door, guarded:
- provider behind an env switch (gemini | fake -- fake is for offline
  tests and may never produce shipped results)
- every uncached call retried with backoff
- caching itself lives in contradictions.py (keyed by case + prompt
  version), so a full re-run costs zero API calls
"""
import json
import os
import time

from dotenv import load_dotenv

from engine import config


class LLMError(RuntimeError):
    pass


def llm_cfg():
    cfg = config.load()
    llm = cfg.get("llm") or {}
    return dict(model=llm.get("mining_model", "gemini-3.5-flash"),
                sleep_s=float(llm.get("sleep_s", 5)))


class GeminiProvider:
    def __init__(self, model):
        load_dotenv()
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise LLMError("GEMINI_API_KEY missing -- check your .env")
        from google import genai
        self.client = genai.Client(api_key=key)
        self.model = model
        self.calls = 0

    def complete(self, prompt):
        last = None
        for attempt in range(4):
            try:
                r = self.client.models.generate_content(
                    model=self.model, contents=prompt,
                    config={"response_mime_type": "application/json"})
                self.calls += 1
                return r.text
            except Exception as e:      # 429s, transient network, etc.
                last = e
                if "PerDay" in str(e):  # daily quota: retrying is futile
                    raise LLMError(f"DAILY quota exhausted for {self.model}: "
                                   f"switch mining_model in parry.yaml or "
                                   f"wait for reset. {e}")
                time.sleep(30 * (attempt + 1))   # respect rate windows
        raise LLMError(f"gemini failed after 4 attempts: {last}")


class FakeProvider:
    """Deterministic keyword heuristic. Exists so the pipeline, cache and
    verifier are testable offline. NEVER a source of shipped results."""
    KEYWORDS = ["aa gaya", "received", "got my", "return", "exchange",
                "when will my", "expedite", "tracking"]

    def __init__(self, model="fake"):
        self.model = model
        self.calls = 0

    def complete(self, prompt):
        self.calls += 1
        payload = json.loads(prompt.split("TRANSCRIPT_JSON:")[1])
        ex = []
        for m in payload["messages"]:
            if (m["sender"] == "customer"
                    and any(k in m["text"].lower() for k in self.KEYWORDS)):
                ex.append(dict(quote=m["text"], source="customer",
                               ts=m["ts"], type="knowledge_of_order",
                               explanation="fake-provider heuristic"))
        return json.dumps({"exhibits": ex[:2]})


def get_provider():
    c = llm_cfg()
    if os.environ.get("PARRY_LLM_PROVIDER", "gemini") == "fake":
        c["sleep_s"] = 0
        return FakeProvider(), c
    return GeminiProvider(c["model"]), c