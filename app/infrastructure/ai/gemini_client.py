import json
import re

from app.shared.config import Settings


class GeminiClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def generate_json(self, prompt: str) -> dict:
        if not self.settings.gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required outside mocked tests")
        import google.generativeai as genai

        genai.configure(api_key=self.settings.gemini_api_key)
        model = genai.GenerativeModel(self.settings.gemini_model)
        generation_config = {
            "temperature": 0,
            "max_output_tokens": self.settings.gemini_max_output_tokens,
            "response_mime_type": "application/json",
        }
        try:
            response = model.generate_content(
                prompt,
                generation_config=generation_config,
                request_options={"timeout": self.settings.gemini_timeout_seconds},
            )
            text = self._extract_json(response.text)
            return self._loads_or_repair(model, text, generation_config)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"Gemini returned malformed JSON: {exc}") from exc
        except Exception as exc:
            raise RuntimeError(f"Gemini request failed or timed out: {exc}") from exc

    def _extract_json(self, text: str) -> str:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        return match.group(0) if match else cleaned

    def _loads_or_repair(self, model, text: str, generation_config: dict) -> dict:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            repair_prompt = f"""
Repara el siguiente contenido para que sea JSON valido.
No agregues explicaciones. No cambies la estructura semantica.
Devuelve exclusivamente un objeto JSON valido.

Contenido:
{text[:120000]}
"""
            response = model.generate_content(
                repair_prompt,
                generation_config=generation_config,
                request_options={"timeout": self.settings.gemini_timeout_seconds},
            )
            repaired = self._extract_json(response.text)
            return json.loads(repaired)
