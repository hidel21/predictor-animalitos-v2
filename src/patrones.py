from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Set, Tuple
import re
import os

@dataclass
class Patron:
    id: int
    descripcion_original: str
    secuencia: List[str]
    prioritario: bool
    origen: str = "Usuario" # "Usuario" o "IA"
    
    @property
    def str_secuencia(self) -> str:
        return "-".join(self.secuencia)

@dataclass
class EstadoPatronDiario:
    patron: Patron
    aciertos_hoy: int
    numeros_acertados: Set[str]
    ultimo_acierto: Optional[str] # Número
    hora_ultimo_acierto: Optional[str]
    progreso: float

    def actualizar(self, numero: str, hora: str):
        if numero in self.patron.secuencia:
            if numero not in self.numeros_acertados:
                self.numeros_acertados.add(numero)
                self.aciertos_hoy = len(self.numeros_acertados)
                self.progreso = (self.aciertos_hoy / len(self.patron.secuencia)) * 100
            
            # Actualizamos el último acierto
            self.ultimo_acierto = numero
            self.hora_ultimo_acierto = hora

class GestorPatrones:
    def __init__(self, archivo_patrones: str = "data/patrones_v2.txt"):
        self.archivo_patrones = archivo_patrones
        self.patrones: List[Patron] = []
        self.estados_diarios: Dict[int, EstadoPatronDiario] = {}
        self._cargar_patrones()

    def _parsear_linea(self, linea: str, idx: int) -> Optional[Patron]:
        linea = linea.strip()
        if not linea:
            return None
            
        # Detectar prioridad
        prioritario = "🎉" in linea or "✅" in linea
        
        # Reemplazar todo lo que no sea dígito con espacio
        # Esto maneja emojis, guiones, puntos, etc. como separadores
        clean_line = re.sub(r'[^0-9]', ' ', linea)
        
        # Extraer tokens
        tokens = clean_line.split()
        numeros = []
        
        for token in tokens:
            # token ya es solo dígitos
            if token == "00" or (token.isdigit() and 0 <= int(token) <= 36):
                if token == "00":
                    numeros.append("00")
                else:
                    numeros.append(str(int(token)))
        
        if not numeros:
            return None
            
        return Patron(
            id=idx,
            descripcion_original=linea,
            secuencia=numeros,
            prioritario=prioritario
        )

    def _cargar_patrones(self):
        if not os.path.exists(self.archivo_patrones):
            os.makedirs(os.path.dirname(self.archivo_patrones), exist_ok=True)
            # Crear archivo con ejemplos si no existe
            with open(self.archivo_patrones, "w", encoding="utf-8") as f:
                f.write("01/04/06/31/ 🎉\n")
                f.write("0-32✅01-26✅-29-24✅12-03-21-33-15-17-34✅20\n")
                f.write("09 25 24 21 10 0 00\n")
        
        with open(self.archivo_patrones, "r", encoding="utf-8") as f:
            for idx, linea in enumerate(f):
                patron = self._parsear_linea(linea, idx)
                if patron:
                    self.patrones.append(patron)

    def agregar_patron_ia(self, secuencia: List[str], descripcion: str) -> Patron:
        """Agrega un patrón generado por IA a la lista en memoria."""
        # Usar un ID alto para diferenciar visualmente si se necesita
        idx = len(self.patrones) + 1000 
        patron = Patron(
            id=idx,
            descripcion_original=descripcion,
            secuencia=secuencia,
            prioritario=True,
            origen="IA"
        )
        self.patrones.append(patron)
        return patron

    def procesar_dia(self, resultados_dia: List[Tuple[str, str]]) -> List[EstadoPatronDiario]:
        """
        Procesa todos los resultados del día y devuelve el estado de los patrones activos.
        resultados_dia: Lista de tuplas (hora, numero)
        """
        self.estados_diarios = {} # Reset diario
        
        for hora, numero in resultados_dia:
            for patron in self.patrones:
                if numero in patron.secuencia:
                    if patron.id not in self.estados_diarios:
                        self.estados_diarios[patron.id] = EstadoPatronDiario(
                            patron=patron,
                            aciertos_hoy=0,
                            numeros_acertados=set(),
                            ultimo_acierto=None,
                            hora_ultimo_acierto=None,
                            progreso=0.0
                        )
                    
                    self.estados_diarios[patron.id].actualizar(numero, hora)
        
        activos = list(self.estados_diarios.values())
        # Ordenar: Prioritarios primero, luego por progreso descendente
        activos.sort(key=lambda x: (not x.patron.prioritario, -x.progreso))
        return activos

    def get_features_numero(self, numero: str) -> Dict[str, float]:
        """
        Calcula features relacionadas con patrones para un número específico.
        """
        en_patron_activo = 0
        cantidad_patrones = 0
        max_progreso = 0.0
        es_prioritario = 0
        
        for estado in self.estados_diarios.values():
            if numero in estado.patron.secuencia:
                en_patron_activo = 1
                cantidad_patrones += 1
                if estado.progreso > max_progreso:
                    max_progreso = estado.progreso
                if estado.patron.prioritario:
                    es_prioritario = 1
                    
        return {
            "en_patron_activo": float(en_patron_activo),
            "cantidad_patrones_que_lo_contienen": float(cantidad_patrones),
            "max_progreso_patron_que_lo_contiene": max_progreso,
            "es_de_patron_prioritario": float(es_prioritario)
        }
