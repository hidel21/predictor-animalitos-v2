from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Dict
from enum import Enum
import logging
from collections import Counter

from .constantes import ANIMALITOS, SECTORES
from .historial_client import HistorialData
from .atrasos import AnalizadorAtrasos
from .model import MarkovModel
from .tablero import TableroAnalizer
from .patrones import GestorPatrones

logger = logging.getLogger(__name__)

class NivelAlerta(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    SUCCESS = "success"

@dataclass
class Alerta:
    nivel: NivelAlerta
    titulo: str
    mensaje: str
    categoria: str  # "Patrón", "Atraso", "Márkov", "Sector", "Racha"

class MotorAlertas:
    def __init__(self, data: HistorialData, gestor_patrones: GestorPatrones):
        self.data = data
        self.gestor_patrones = gestor_patrones
        
        # Umbrales configurables (hardcoded por ahora, podrían venir de config)
        self.UMBRAL_ATRASO_DIAS = 10
        self.UMBRAL_ATRASO_SORTEOS = 80
        self.UMBRAL_MARKOV_PROB = 0.25
        self.UMBRAL_SECTOR_COBERTURA = 40.0 # %
        self.UMBRAL_RACHA_VECES = 3
        self.UMBRAL_RACHA_SORTEOS = 15

    def generar_alertas(self) -> List[Alerta]:
        alertas = []
        if self.data.total_sorteos == 0:
            return alertas
            
        alertas.extend(self._check_patrones())
        alertas.extend(self._check_atrasos())
        alertas.extend(self._check_markov())
        alertas.extend(self._check_sectores())
        alertas.extend(self._check_rachas())
        
        # Ordenar por severidad: CRITICAL > WARNING > SUCCESS > INFO
        order = {
            NivelAlerta.CRITICAL: 0,
            NivelAlerta.WARNING: 1,
            NivelAlerta.SUCCESS: 2,
            NivelAlerta.INFO: 3
        }
        alertas.sort(key=lambda x: order[x.nivel])
        
        return alertas

    def _check_patrones(self) -> List[Alerta]:
        alertas = []
        # Obtener historial plano para patrones
        historial_plano = TableroAnalizer.get_ultimos_resultados(self.data, 1000)
        estados = self.gestor_patrones.analizar_patrones(historial_plano)
        
        for estado in estados:
            p = estado.patron
            if estado.es_completo:
                # Alerta de éxito: Patrón completado recientemente
                # Verificar si se completó JUSTO AHORA (último elemento del historial coincide con último del patrón)
                # La lógica de analizar_patrones ya verifica coincidencia al final del historial.
                alertas.append(Alerta(
                    nivel=NivelAlerta.SUCCESS,
                    titulo=f"Patrón Completado: {p.nombre}",
                    mensaje=f"La secuencia {p.str_secuencia} se ha completado.",
                    categoria="Patrón"
                ))
            elif estado.siguiente:
                # Patrón en progreso
                # Alertar si falta solo 1 (progreso alto) o si tiene varios aciertos
                falta_uno = (estado.aciertos == len(p.secuencia) - 1)
                if falta_uno:
                    nombre_sig = ANIMALITOS.get(estado.siguiente, "?")
                    alertas.append(Alerta(
                        nivel=NivelAlerta.WARNING,
                        titulo=f"Patrón a punto de completarse",
                        mensaje=f"Falta el **{estado.siguiente} - {nombre_sig}** para completar {p.nombre} ({estado.aciertos}/{len(p.secuencia)}).",
                        categoria="Patrón"
                    ))
                elif estado.progreso >= 0.5 and len(p.secuencia) > 3:
                     # Progreso significativo en patrones largos
                     alertas.append(Alerta(
                        nivel=NivelAlerta.INFO,
                        titulo=f"Patrón en progreso",
                        mensaje=f"{p.nombre} al {int(estado.progreso*100)}%. Siguiente: {estado.siguiente}.",
                        categoria="Patrón"
                    ))
        return alertas

    def _check_atrasos(self) -> List[Alerta]:
        alertas = []
        # Usar fecha fin del historial
        fecha_fin = self.data.dias[-1] if self.data.dias else "2099-12-31"
        atrasos = AnalizadorAtrasos.analizar(self.data, fecha_fin)
        
        for item in atrasos:
            if item.nunca_salio:
                continue # Ignoramos los que nunca salieron para alertas críticas, o los tratamos diferente
            
            es_critico_dias = item.dias_sin_salir >= self.UMBRAL_ATRASO_DIAS
            es_critico_sorteos = item.sorteos_sin_salir >= self.UMBRAL_ATRASO_SORTEOS
            
            if es_critico_dias or es_critico_sorteos:
                alertas.append(Alerta(
                    nivel=NivelAlerta.CRITICAL,
                    titulo=f"Atraso Crítico: {item.animal}",
                    mensaje=f"Lleva {item.dias_sin_salir} días y {item.sorteos_sin_salir} sorteos sin salir.",
                    categoria="Atraso"
                ))
        return alertas

    def _check_markov(self) -> List[Alerta]:
        alertas = []
        # Obtener último animal salido
        ultimos = TableroAnalizer.get_ultimos_resultados(self.data, 1)
        if not ultimos:
            return alertas
            
        ultimo_num = ultimos[-1]
        ultimo_nombre = ANIMALITOS.get(ultimo_num, "")
        
        if not ultimo_nombre:
            return alertas
            
        try:
            model = MarkovModel.from_historial(self.data, mode="sequential")
            probs = model.next_probs(ultimo_nombre)
            
            for sucesor, prob in probs.items():
                if prob >= self.UMBRAL_MARKOV_PROB:
                    alertas.append(Alerta(
                        nivel=NivelAlerta.WARNING, # Warning positivo (oportunidad)
                        titulo=f"Alta Probabilidad Márkov",
                        mensaje=f"Después de {ultimo_nombre}, el **{sucesor}** tiene un {prob*100:.1f}% de probabilidad.",
                        categoria="Márkov"
                    ))
        except Exception as e:
            logger.error(f"Error en alertas Markov: {e}")
            
        return alertas

    def _check_sectores(self) -> List[Alerta]:
        alertas = []
        # Analizar últimos 12 sorteos para inmediatez
        stats = TableroAnalizer.analizar_todos(self.data, 12)
        
        for s in stats["Sectores"]:
            if s.porcentaje_cobertura >= self.UMBRAL_SECTOR_COBERTURA:
                alertas.append(Alerta(
                    nivel=NivelAlerta.INFO,
                    titulo=f"Sector Activo: {s.nombre}",
                    mensaje=f"Concentra el {s.porcentaje_cobertura:.0f}% de los últimos 12 resultados.",
                    categoria="Sector"
                ))
        return alertas

    def _check_rachas(self) -> List[Alerta]:
        alertas = []
        # Últimos N sorteos
        ultimos = TableroAnalizer.get_ultimos_resultados(self.data, self.UMBRAL_RACHA_SORTEOS)
        if not ultimos:
            return alertas
            
        # Contar apariciones
        # ultimos es lista de strings numéricos "0", "24", etc.
        counts = Counter(ultimos)
        
        for num_str, count in counts.items():
            if count >= self.UMBRAL_RACHA_VECES:
                nombre = ANIMALITOS.get(num_str, "?")
                alertas.append(Alerta(
                    nivel=NivelAlerta.WARNING,
                    titulo=f"Racha Caliente: {num_str} - {nombre}",
                    mensaje=f"Ha salido {count} veces en los últimos {self.UMBRAL_RACHA_SORTEOS} sorteos.",
                    categoria="Racha"
                ))
        return alertas
