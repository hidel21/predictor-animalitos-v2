
import os
import streamlit as st
from openai import OpenAI
import json

class AIClient:
    def __init__(self):
        # Intentar cargar desde secrets de Streamlit
        try:
            self.api_key = st.secrets["OPENAI_API_KEY"]
        except Exception:
            # Fallback a variable de entorno o hardcoded (no recomendado pero útil para dev local sin secrets.toml)
            self.api_key = os.getenv("OPENAI_API_KEY")
            
        if not self.api_key:
            raise ValueError("No se encontró la API Key de OpenAI. Configúrala en .streamlit/secrets.toml")
            
        # Intentar cargar base_url opcional (útil para proxies o endpoints alternativos)
        self.base_url = None
        try:
            self.base_url = st.secrets.get("OPENAI_BASE_URL")
        except Exception:
            self.base_url = os.getenv("OPENAI_BASE_URL")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    def get_analysis(self, system_prompt: str, user_context: dict) -> str:
        """
        Envía una solicitud a la API de OpenAI.
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", # Usamos un modelo eficiente y capaz
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_context, indent=2)}
                ],
                temperature=0.7,
                max_tokens=1500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"Error llamando a OpenAI: {e}")
            return f"Error: {str(e)}"
