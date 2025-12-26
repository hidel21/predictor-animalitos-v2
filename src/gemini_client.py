
import os
import streamlit as st
from google import genai
from google.genai import types
import json

class GeminiClient:
    def __init__(self):
        # Intentar cargar desde secrets de Streamlit
        try:
            self.api_key = st.secrets["GEMINI_API_KEY"]
        except Exception:
            # Fallback a variable de entorno
            self.api_key = os.getenv("GEMINI_API_KEY")
            
        if not self.api_key:
            raise ValueError("No se encontró la API Key de Gemini. Configúrala en .streamlit/secrets.toml como GEMINI_API_KEY")
            
        self.client = genai.Client(api_key=self.api_key)

    def get_analysis(self, system_prompt: str, user_context: dict) -> str:
        """
        Envía una solicitud a la API de Gemini con retry automático si hay error de cuota.
        """
        import time
        import re
        full_prompt = f"{system_prompt}\n\nContexto de datos:\n{json.dumps(user_context, indent=2)}"
        delays = [2, 4, 8, 16, 32]
        last_error = None
        for delay in delays:
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash-exp",
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.7,
                        max_output_tokens=1500
                    )
                )
                return response.text
            except Exception as e:
                last_error = str(e)
                # Detectar error de cuota 429 y sugerencia de retry
                if "429" in last_error or "RESOURCE_EXHAUSTED" in last_error:
                    print(f"[Gemini] Cuota excedida o rate limit. Reintentando en {delay}s...")
                    # Buscar sugerencia de tiempo de espera en el mensaje
                    retry_match = re.search(r'retry in (\d+)', last_error)
                    if retry_match:
                        wait_time = int(retry_match.group(1))
                        time.sleep(wait_time)
                    else:
                        time.sleep(delay)
                else:
                    print(f"Error llamando a Gemini: {e}")
                    break
        # Si falla tras reintentos, devolver el último error
        print(f"Error llamando a Gemini tras reintentos: {last_error}")
        return f"Error: {last_error}"
