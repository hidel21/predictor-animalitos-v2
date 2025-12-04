import csv
import os
from datetime import datetime
from typing import List, Optional

class PredictionLogger:
    """
    Registra las predicciones realizadas por el bot para su posterior análisis y reentrenamiento.
    """
    def __init__(self, log_file: str = "prediction_log.csv"):
        self.log_file = log_file
        self._ensure_header()

    def _ensure_header(self):
        if not os.path.exists(self.log_file):
            with open(self.log_file, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", 
                    "fecha_sorteo", 
                    "hora_sorteo", 
                    "top_1", 
                    "top_3", 
                    "resultado_real", 
                    "acierto_top1", 
                    "acierto_top3"
                ])

    def log_prediction(self, fecha_sorteo: str, hora_sorteo: str, top_n: List[str], resultado_real: Optional[str] = None):
        """
        Registra una predicción.
        top_n: Lista de números predichos (ej. ['01', '36', '00'])
        """
        timestamp = datetime.now().isoformat()
        top_1 = top_n[0] if len(top_n) > 0 else ""
        top_3 = "|".join(top_n[:3])
        
        acierto_top1 = 0
        acierto_top3 = 0
        
        if resultado_real:
            # Extraer número del resultado real (ej "24 Iguana" -> "24")
            real_num = resultado_real.split()[0] if resultado_real[0].isdigit() else resultado_real
            
            if top_1 == real_num:
                acierto_top1 = 1
            if real_num in top_n[:3]:
                acierto_top3 = 1
        
        with open(self.log_file, mode='a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                timestamp,
                fecha_sorteo,
                hora_sorteo,
                top_1,
                top_3,
                resultado_real if resultado_real else "",
                acierto_top1,
                acierto_top3
            ])

    def get_recent_logs(self, n: int = 10) -> List[dict]:
        """Devuelve los últimos N registros."""
        if not os.path.exists(self.log_file):
            return []
            
        rows = []
        try:
            with open(self.log_file, mode='r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
        except Exception:
            return []
            
        return rows[-n:]
