from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime

from .historial_client import HistorialData
from .constantes import ANIMALITOS

@dataclass
class AtrasoInfo:
    animal: str
    ultima_fecha: Optional[str]
    dias_sin_salir: int
    sorteos_sin_salir: int
    nunca_salio: bool

class AnalizadorAtrasos:
    @staticmethod
    def analizar(data: HistorialData, fecha_fin: str) -> List[AtrasoInfo]:
        """
        Calcula los atrasos para todos los animalitos.
        
        Args:
            data: Datos del historial.
            fecha_fin: Fecha de referencia para calcular días de atraso (YYYY-MM-DD).
        """
        # 1. Aplanar el historial cronológicamente
        # Lista de tuplas (fecha, hora, animal)
        sorteos_cronologicos = []
        for dia in data.dias:
            for hora in data.horas:
                key = (dia, hora)
                if key in data.tabla:
                    sorteos_cronologicos.append({
                        "fecha": dia,
                        "hora": hora,
                        "animal": data.tabla[key]
                    })
        
        total_sorteos = len(sorteos_cronologicos)
        fecha_ref = datetime.strptime(fecha_fin, "%Y-%m-%d")
        
        resultados = []
        
        # 2. Calcular métricas para cada animalito (0-36)
        for num, nombre in ANIMALITOS.items():
            # Buscar última aparición
            ultima_aparicion_idx = -1
            ultima_fecha_str = None
            
            # Recorrer de atrás hacia adelante para encontrar el último
            for i in range(total_sorteos - 1, -1, -1):
                if sorteos_cronologicos[i]["animal"] == nombre:
                    ultima_aparicion_idx = i
                    ultima_fecha_str = sorteos_cronologicos[i]["fecha"]
                    break
            
            if ultima_aparicion_idx != -1:
                # Salió al menos una vez
                dias_sin_salir = (fecha_ref - datetime.strptime(ultima_fecha_str, "%Y-%m-%d")).days
                sorteos_sin_salir = total_sorteos - 1 - ultima_aparicion_idx
                nunca_salio = False
            else:
                # Nunca salió en el rango
                dias_sin_salir = -1 # Indicador especial
                sorteos_sin_salir = total_sorteos
                nunca_salio = True
                
            resultados.append(AtrasoInfo(
                animal=f"{num} - {nombre}",
                ultima_fecha=ultima_fecha_str,
                dias_sin_salir=dias_sin_salir,
                sorteos_sin_salir=sorteos_sin_salir,
                nunca_salio=nunca_salio
            ))
            
        # Ordenar: Primero los que nunca salieron (por sorteos sin salir desc), luego por sorteos sin salir desc
        return sorted(resultados, key=lambda x: x.sorteos_sin_salir, reverse=True)
