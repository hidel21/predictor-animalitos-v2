from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional
import logging

from .constantes import ANIMALITOS, SECTORES, DOCENAS, COLUMNAS
from .historial_client import HistorialData
from .atrasos import AnalizadorAtrasos
from .model import MarkovModel
from .tablero import TableroAnalizer
from .patrones import GestorPatrones

logger = logging.getLogger(__name__)

@dataclass
class ScoreItem:
    numero: str
    nombre: str
    score_total: float
    
    # Componentes del score (para explicabilidad)
    score_frecuencia: float
    score_atraso: float
    score_markov: float
    score_sector: float
    score_patron: float
    
    # Detalles crudos
    frecuencia_real: int
    dias_sin_salir: int
    prob_markov: float
    sector_info: str
    patron_info: str

class Recomendador:
    def __init__(self, data: HistorialData, gestor_patrones: GestorPatrones):
        self.data = data
        self.gestor_patrones = gestor_patrones

    def calcular_scores(self, 
                        peso_frecuencia: float = 0.2,
                        peso_atraso: float = 0.3,
                        peso_markov: float = 0.3,
                        peso_sector: float = 0.1,
                        peso_patron: float = 0.1) -> List[ScoreItem]:
        
        scores = []
        
        # 1. Obtener datos base
        # Frecuencias
        from collections import Counter
        freq_counter = Counter(self.data.tabla.values())
        max_freq = max(freq_counter.values()) if freq_counter else 1
        
        # Atrasos
        # Necesitamos fecha fin, asumimos la última del historial o hoy
        if self.data.dias:
            fecha_fin = self.data.dias[-1]
        else:
            fecha_fin = "2099-12-31" # Fallback
            
        atrasos = AnalizadorAtrasos.analizar(self.data, fecha_fin)
        atrasos_map = {item.animal: item for item in atrasos}
        max_dias_atraso = max((item.dias_sin_salir for item in atrasos if not item.nunca_salio), default=1)
        
        # Markov
        # Necesitamos el último animal salido para predecir el siguiente
        ultimo_animal_nombre = ""
        # Obtener último resultado cronológico
        # Reutilizamos lógica de app.py o tablero.py para obtener último
        ultimos_n = TableroAnalizer.get_ultimos_resultados(self.data, 1)
        if ultimos_n:
            ultimo_numero = ultimos_n[-1]
            ultimo_animal_nombre = ANIMALITOS.get(ultimo_numero, "")
            
        markov_probs = {}
        if ultimo_animal_nombre:
            try:
                model = MarkovModel.from_historial(self.data, mode="sequential")
                markov_probs = model.next_probs(ultimo_animal_nombre)
            except Exception as e:
                logger.warning(f"Error calculando Markov: {e}")

        # Sectores
        # Analizamos últimos 24 sorteos para ver sectores calientes
        stats_tablero = TableroAnalizer.analizar_todos(self.data, 24)
        # Mapa de cobertura de sectores: NombreSector -> Cobertura
        sector_coverage = {s.nombre: s.porcentaje_cobertura for s in stats_tablero["Sectores"]}
        
        # Patrones
        # Obtener historial plano completo para patrones
        historial_plano = TableroAnalizer.get_ultimos_resultados(self.data, 1000) # Traer suficientes
        estados_patrones = self.gestor_patrones.analizar_patrones(historial_plano)
        
        # Mapa de bonus por patrón: Numero -> Bonus
        patron_bonus = {}
        patron_info_map = {}
        
        for estado in estados_patrones:
            if estado.siguiente:
                # Si es el siguiente esperado, dar bonus proporcional al progreso
                # Progreso 1.0 no debería pasar si hay siguiente (sería completo), pero por si acaso
                bonus = estado.progreso  # 0.5, 0.66, etc.
                
                # Acumular bonus si aparece en múltiples patrones? O tomar el máximo?
                # Tomamos el máximo para no disparar el score
                curr = patron_bonus.get(estado.siguiente, 0.0)
                if bonus > curr:
                    patron_bonus[estado.siguiente] = bonus
                    patron_info_map[estado.siguiente] = f"Siguiente en {estado.patron.nombre} ({int(estado.progreso*100)}%)"

        # Calcular score para cada animalito (0-36)
        for num_str, nombre in ANIMALITOS.items():
            # --- Frecuencia ---
            # Normalizar: freq / max_freq
            # Si queremos premiar frecuencia (calientes)
            f_raw = freq_counter.get(nombre, 0)
            s_freq = f_raw / max_freq if max_freq > 0 else 0
            
            # --- Atraso ---
            # Normalizar: dias / max_dias
            # Premiar atraso (fríos que pueden salir)
            a_item = atrasos_map.get(nombre)
            dias = a_item.dias_sin_salir if a_item and not a_item.nunca_salio else max_dias_atraso
            if a_item and a_item.nunca_salio:
                dias = max_dias_atraso * 1.2 # Bonus extra si nunca salió
            
            s_atraso = min(dias / max_dias_atraso, 1.0) if max_dias_atraso > 0 else 0
            
            # --- Markov ---
            # Probabilidad directa (ya está entre 0 y 1)
            prob_markov = markov_probs.get(nombre, 0.0)
            s_markov = prob_markov
            
            # --- Sector ---
            # Buscar a qué sector pertenece este número
            # SECTORES es Dict[str, List[int]] (Nombre -> Lista numeros)
            # num_str es string, SECTORES tiene ints
            num_int = int(num_str) if num_str.isdigit() else -1
            
            s_sector = 0.0
            sector_name_found = "N/A"
            
            for sec_name, nums in SECTORES.items():
                if num_int in nums:
                    # Encontramos el sector
                    cov = sector_coverage.get(sec_name, 0.0) # 0.0 a 1.0 (o 100.0?)
                    # TableroAnalizer devuelve porcentaje 0-100? Revisar tablero.py
                    # Revisando tablero.py: porcentaje_cobertura = (len(activos) / total) * 100
                    # Normalizamos a 0-1
                    s_sector = cov / 100.0
                    sector_name_found = f"{sec_name} ({cov:.0f}%)"
                    break
            
            # --- Patrón ---
            s_patron = patron_bonus.get(num_str, 0.0)
            p_info = patron_info_map.get(num_str, "Sin patrón activo")
            
            # --- Score Total ---
            total = (
                (s_freq * peso_frecuencia) +
                (s_atraso * peso_atraso) +
                (s_markov * peso_markov) +
                (s_sector * peso_sector) +
                (s_patron * peso_patron)
            )
            
            # Normalizar total a 0-100 para visualización amigable? O dejar 0-1
            # Dejemos 0-1 para cálculo, multiplicamos por 100 al mostrar
            
            scores.append(ScoreItem(
                numero=num_str,
                nombre=nombre,
                score_total=total,
                score_frecuencia=s_freq,
                score_atraso=s_atraso,
                score_markov=s_markov,
                score_sector=s_sector,
                score_patron=s_patron,
                frecuencia_real=f_raw,
                dias_sin_salir=dias,
                prob_markov=prob_markov,
                sector_info=sector_name_found,
                patron_info=p_info
            ))
            
        # Ordenar descendente
        scores.sort(key=lambda x: x.score_total, reverse=True)
        
        return scores
