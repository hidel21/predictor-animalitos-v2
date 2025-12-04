from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
import json
import os

@dataclass
class Patron:
    secuencia: List[str]
    nombre: str = "Personalizado"
    
    @property
    def str_secuencia(self) -> str:
        return "-".join(self.secuencia)

@dataclass
class EstadoPatron:
    patron: Patron
    aciertos: int
    siguiente: Optional[str]
    progreso: float
    es_completo: bool

class GestorPatrones:
    def __init__(self):
        self.patrones: List[Patron] = []
        self._cargar_patrones_iniciales()

    def _cargar_patrones_iniciales(self):
        raw_patterns = [
            "0-00-21-19-24-02-36",
            "0-25-24-21-10-00-09",
            "0-00-27-09-03-05-06",
            "0-18-16",
            "0-29-32-26-24-34-07-15-12",
            "00-27-05-03-09",
            "01-06-31-04",
            "01-14",
            "01-26-20",
            "01-30-26-08-20",
            "01-26-33-34-20-09",
            "01-09-20-02",
            "02-21-25-36-15-13-28-17-35",
            "02-01-09-20",
            "02-15-36-31-30",
            "02-14-10-00-0",
            "02-35-17-35",
            "02-07-03",
            "03-09-30-05-22",
            "03-15-23-0",
            "03-12-24-15-12-17-32-29-21-26-0",
            "04-01-075",
            "04-01-31-06",
            "04-11-31",
            "04-26-12-08-06-20",
            "04-16-33",
            "05-07-01",
            "05-03-27-09",
            "06-01-04-31",
            "06-22-10-14",
            "06-18-16-22-33",
            "07-05-04-01",
            "07-15-34-12-29-26-0-32",
            "08-19-29",
            "08-06-35-33-19-23",
            "09-22-30-01-25-27",
            "09-15-31-01-04-06",
            "10-25-24-21-0-00",
            "10-22-14-06",
            "11-32-04-01-06-31",
            "11-22-00-33",
            "11-28-14-0",
            "12-26-04-08-15",
            "12-16-28-14",
            "12-24-29-0-29-32-26",
            "13-34-21-06-08",
            "13-17-36-28",
            "14-22-10-06",
            "14-11-28-0",
            "14-02-10-0-00",
            "15-17-33-24-26-29",
            "15-17-12-07-34-29-26-32",
            "15-31-36-30-09-08-07-02",
            "15-03-23-0",
            "16-18-22-06",
            "16-28-12-22",
            "17-15-12-33-29-26-0-32",
            "17-13-36-28",
            "17-02-35-15-23",
            "18-16-22-06-33-10",
            "19-08-06-24-35-23-33",
            "19-08-35-23-33-24",
            "20-01-26-33-32",
            "21-0-01-29-32-12-24",
            "21-19-24-02-0",
            "21-34-13-06-01-04",
            "21-25-10-24-0-00",
            "22-14-10-06",
            "22-16-18-06-33",
            "22-00-33-11",
            "23-0-15-03-34",
            "23-17-02",
            "23-35-19-33-06-08",
            "24-25-21-10-0-00",
            "24-19-0-00-02",
            "25-24-10-21-0-00",
            "25-09-10-24",
            "26-20-33-01",
            "26-32-0-29-24-34-15-12-01-23",
            "26-04-08-15-01-20",
            "26-32-29-01-0-12-24",
            "27-05-00-03-09-01-06-25",
            "28-16-12-13",
            "28-14-11-0-00-35",
            "28-13-22",
            "28-13",
            "29-33-24-15-26",
            "29-0-32-26-34-07-12-15-17",
            "30-08-19-01-05-11-26",
            "30-15-31-36-09-08-07-34",
            "30-22-09-36-31",
            "31-01-06-04-20",
            "31-11-36-30-08",
            "31-15-08-07-12-09-30",
            "32-26-0-00-29-23-34-07-17-15-12",
            "32-11-04-06-05-01-07",
            "32-23-35",
            "32-12-24-03-07-15-12-17-34-29-28-21-26",
            "33-21-06-01-23-35-34-08",
            "33-10-18-06",
            "33-04-16",
            "33-11-22-00-14",
            "33-15-17",
            "33-24-26-29-15",
            "34-06-13-21",
            "34-32-23-07-15-17-29-26-33",
            "35-02-17-32",
            "35-00-28-14-09",
            "35-23-17-02-33-00-08-19-06",
            "36-30-31-09-15-02",
            "36-17-13-28-30-31",
            "36-01-25-21-09"
        ]
        
        for p_str in raw_patterns:
            # Limpieza básica de caracteres extraños que venían en el input
            clean_str = p_str.replace("+", "-").replace("/", "-").replace("=", "-").replace(".", "").strip()
            # Eliminar guiones dobles
            while "--" in clean_str:
                clean_str = clean_str.replace("--", "-")
            if clean_str.endswith("-"):
                clean_str = clean_str[:-1]
                
            self.agregar_patron(clean_str, f"Patrón {clean_str[:10]}...")

    def agregar_patron(self, secuencia_str: str, nombre: str = "Personalizado"):
        """
        Agrega un patrón desde un string tipo '01-06-04' o '1 6 4'.
        """
        # Normalizar separadores
        if "-" in secuencia_str:
            parts = secuencia_str.split("-")
        else:
            parts = secuencia_str.split()
            
        # Limpiar y validar
        clean_parts = []
        for p in parts:
            p = p.strip()
            if p.isdigit():
                # Quitar ceros a la izquierda para consistencia con el resto de la app (si se usa así)
                # O mantenerlos si ANIMALITOS usa strings como "0", "00".
                # En constantes.py las keys son strings: "0", "00", "1", "2"...
                # Si el usuario escribe "01", debería ser "1".
                if p == "00":
                    clean_parts.append("00")
                else:
                    clean_parts.append(str(int(p))) 
        
        if clean_parts:
            self.patrones.append(Patron(clean_parts, nombre))

    def eliminar_patron(self, index: int):
        if 0 <= index < len(self.patrones):
            self.patrones.pop(index)

    def analizar_patrones(self, historial_reciente: List[str]) -> List[EstadoPatron]:
        """
        Analiza qué patrones están activos basándose en el historial reciente.
        historial_reciente: Lista de números (strings) ordenados cronológicamente [..., antepenultimo, penultimo, ultimo]
        """
        resultados = []
        
        for patron in self.patrones:
            seq = patron.secuencia
            n = len(seq)
            match_len = 0
            
            # Buscar la coincidencia más larga del prefijo del patrón con el sufijo del historial
            # Probamos longitudes desde n-1 hasta 1 (si n coincide es completo, pero buscamos "siguiente")
            # Si el patrón ya se completó justo ahora, match_len = n.
            
            # Limite de búsqueda: min(len(historial), len(patron))
            limit = min(len(historial_reciente), n)
            
            for k in range(limit, 0, -1):
                # Sufijo del historial de longitud k
                suffix = historial_reciente[-k:]
                # Prefijo del patrón de longitud k
                prefix = seq[:k]
                
                if suffix == prefix:
                    match_len = k
                    break
            
            es_completo = (match_len == n)
            siguiente = seq[match_len] if match_len < n else None
            progreso = match_len / n
            
            resultados.append(EstadoPatron(
                patron=patron,
                aciertos=match_len,
                siguiente=siguiente,
                progreso=progreso,
                es_completo=es_completo
            ))
            
        # Ordenar por progreso descendente
        resultados.sort(key=lambda x: x.progreso, reverse=True)
        return resultados
