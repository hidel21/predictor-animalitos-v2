from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple
from collections import Counter

from .historial_client import HistorialData
from .constantes import ANIMALITOS, COLORES, SECTORES, DOCENAS, COLUMNAS

@dataclass
class GrupoStats:
    nombre: str
    total_numeros: int
    numeros_salidos: int
    porcentaje_cobertura: float
    numeros_activos: List[str]

class TableroAnalizer:
    @staticmethod
    def get_ultimos_resultados(data: HistorialData, n: int) -> List[str]:
        """Obtiene la lista plana de los últimos N resultados cronológicos."""
        sorteos_cronologicos = []
        for dia in data.dias:
            for hora in data.horas:
                key = (dia, hora)
                if key in data.tabla:
                    # Extraer solo el número del string "24 Iguana" -> "24"
                    # Asumimos que el formato es "NUM NOMBRE" o similar
                    # Pero en HistorialClient guardamos el string completo.
                    # Necesitamos normalizar.
                    full_str = data.tabla[key]
                    # Intentar extraer número. A veces viene "24 Iguana", a veces solo nombre.
                    # En constantes.py tenemos el mapa inverso si fuera necesario.
                    # Por ahora, buscaremos el key en ANIMALITOS que coincida con el valor
                    
                    # Estrategia robusta: buscar qué key de ANIMALITOS está contenida en el string
                    found_num = None
                    for k, v in ANIMALITOS.items():
                        if v in full_str: # "Iguana" in "24 Iguana"
                             # Cuidado con "Rana" y "Iguana" (ana). Mejor coincidencia exacta de nombre
                             # El scraper devuelve el texto de la celda.
                             # Asumiremos que el nombre del animal está en el texto.
                             pass
                    
                    # Simplificación: El scraper actual devuelve el texto de la celda.
                    # Vamos a hacer un match inverso con ANIMALITOS values
                    val_to_key = {v: k for k, v in ANIMALITOS.items()}
                    
                    # Limpiar texto (a veces trae numero)
                    # "24 Iguana" -> "Iguana"
                    # "0 Delfin" -> "Delfin"
                    parts = full_str.split()
                    nombre_limpio = parts[-1] if parts else ""
                    if len(parts) > 1 and parts[0].isdigit():
                         # Si viene "24 Iguana", parts[0] es "24"
                         found_num = parts[0]
                    elif nombre_limpio in val_to_key:
                        found_num = val_to_key[nombre_limpio]
                    else:
                        # Fallback: buscar en values
                        for k, v in ANIMALITOS.items():
                            if v.lower() == full_str.lower():
                                found_num = k
                                break
                    
                    if found_num:
                        sorteos_cronologicos.append(found_num)
        
        # Devolver los últimos N
        return sorteos_cronologicos[-n:]

    @staticmethod
    def analizar_grupo(nombre_grupo: str, numeros_grupo: List[str], ultimos_resultados: List[str]) -> GrupoStats:
        """Calcula estadísticas para un grupo específico."""
        set_ultimos = set(ultimos_resultados)
        activos = [num for num in numeros_grupo if num in set_ultimos]
        
        return GrupoStats(
            nombre=nombre_grupo,
            total_numeros=len(numeros_grupo),
            numeros_salidos=len(activos),
            porcentaje_cobertura=len(activos) / len(numeros_grupo) if numeros_grupo else 0.0,
            numeros_activos=activos
        )

    @staticmethod
    def analizar_todos(data: HistorialData, n: int) -> Dict[str, List[GrupoStats]]:
        """Analiza todos los tipos de grupos (Sectores, Docenas, Columnas)."""
        ultimos = TableroAnalizer.get_ultimos_resultados(data, n)
        
        stats = {
            "Sectores": [],
            "Docenas": [],
            "Columnas": []
        }
        
        for nombre, nums in SECTORES.items():
            stats["Sectores"].append(TableroAnalizer.analizar_grupo(nombre, nums, ultimos))
            
        for nombre, nums in DOCENAS.items():
            stats["Docenas"].append(TableroAnalizer.analizar_grupo(nombre, nums, ultimos))
            
        for nombre, nums in COLUMNAS.items():
            stats["Columnas"].append(TableroAnalizer.analizar_grupo(nombre, nums, ultimos))
            
        return stats
