from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import time

import requests
from bs4 import BeautifulSoup
import unicodedata

from .config import BASE_URL, USER_AGENT, TIMEOUT
from .exceptions import ConnectionError, ScrapingError
from .constantes import ANIMALITOS

logger = logging.getLogger(__name__)

def normalize_str(s: str) -> str:
    """Elimina tildes y pasa a mayúsculas para comparación."""
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn').upper()

# Crear mapa de normalización al cargar el módulo
# "CIEMPIES" -> "Ciempiés", "DELFIN" -> "Delfín"
NORMALIZED_MAP = {}
for nombre_oficial in ANIMALITOS.values():
    key = normalize_str(nombre_oficial)
    NORMALIZED_MAP[key] = nombre_oficial



@dataclass
class HistorialData:
    dias: List[str]
    horas: List[str]
    tabla: Dict[Tuple[str, str], str]  # (fecha, hora) -> animal

    @property
    def total_sorteos(self) -> int:
        return len(self.tabla)

    @property
    def dias_con_datos(self) -> int:
        return len(self.dias)

    def merge(self, other: HistorialData) -> int:
        """
        Fusiona otro HistorialData en este.
        Retorna la cantidad de nuevos registros agregados a la tabla.
        """
        nuevos = 0
        
        # Actualizar días
        for d in other.dias:
            if d not in self.dias:
                self.dias.append(d)
        self.dias.sort()
        
        # Actualizar horas
        for h in other.horas:
            if h not in self.horas:
                self.horas.append(h)
        
        # Actualizar tabla
        for key, value in other.tabla.items():
            if key not in self.tabla:
                self.tabla[key] = value
                nuevos += 1
            elif self.tabla[key] != value:
                # Si el valor cambió (corrección), lo actualizamos
                self.tabla[key] = value
                # No contamos como nuevo registro, pero sí actualización
        
        return nuevos


class HistorialClient:
    """Cliente para extraer el historial de La Granjita desde lotoven.com."""

    def __init__(self, base_url: str = BASE_URL) -> None:
        self.base_url = base_url

    def fetch_historial(self, start_date: str, end_date: str) -> HistorialData:
        """
        Descarga y parsea el historial entre start_date y end_date.
        Maneja la paginación semanal de Lotoven.
        Formato fechas: 'YYYY-MM-DD'.
        """
        all_dias: List[str] = []
        all_horas: List[str] = []
        all_tabla: Dict[Tuple[str, str], str] = {}
        
        current_start = start_date
        # Aumentamos el límite de iteraciones para permitir rangos largos (ej. 1 año = ~52 semanas)
        max_iterations = 150 
        iteration = 0
        
        while current_start <= end_date and iteration < max_iterations:
            # Pausa para evitar bloqueo por rate-limiting
            time.sleep(1.0)
            
            iteration += 1
            url = self.base_url.format(start=current_start, end=end_date)
            headers = {"User-Agent": USER_AGENT}

            logger.info("Descargando historial (iteración %d): %s", iteration, url)
            try:
                resp = requests.get(url, headers=headers, timeout=TIMEOUT)
                resp.raise_for_status()
            except requests.RequestException as e:
                raise ConnectionError(f"Error al conectar con Lotoven: {e}") from e

            try:
                soup = BeautifulSoup(resp.text, "html.parser")

                # Buscar la tabla principal por el texto 'Horario'
                table = soup.find("table")
                if table is None:
                    logger.warning("No se encontró tabla para fecha %s", current_start)
                    break

                header_row = table.find("tr")
                if not header_row:
                    logger.warning("Tabla sin filas para fecha %s", current_start)
                    break
                    
                header_cells = header_row.find_all(["th", "td"])
                headers_text = [c.get_text(strip=True) for c in header_cells]

                if not headers_text or headers_text[0] != "Horario":
                    # Si la estructura cambia, lanzamos error o intentamos seguir?
                    # Mejor lanzar error para alertar
                    raise ScrapingError("Formato de cabecera inesperado en la tabla.")

                page_dias = headers_text[1:]
                if not page_dias:
                    break

                # Procesar filas
                for row in table.find_all("tr")[1:]:
                    cols = row.find_all("td")
                    if not cols:
                        continue

                    hora = cols[0].get_text(strip=True)
                    if not hora:
                        continue
                    
                    if hora not in all_horas:
                        all_horas.append(hora)

                    for i, dia in enumerate(page_dias, start=1):
                        if i >= len(cols):
                            continue
                        animal_raw = cols[i].get_text(strip=True)
                        if animal_raw:
                            # Normalizar nombre
                            # El scraper trae ej: "03 Ciempies" o solo "Ciempies"?
                            # Según debug trae "Ciempies" (sin número) o con número?
                            # El debug mostró: 'Ciempies', 'Delfin'. Parece que trae solo el nombre o nombre limpio.
                            # Pero en app.py vi lógica de split().
                            # Asumamos que puede venir sucio.
                            
                            # Intentar separar si viene con número "03 Ciempies"
                            parts = animal_raw.split()
                            if len(parts) > 1 and parts[0].isdigit():
                                nombre_sucio = " ".join(parts[1:])
                            else:
                                nombre_sucio = animal_raw
                                
                            # Buscar en mapa normalizado
                            key_sucio = normalize_str(nombre_sucio)
                            nombre_oficial = NORMALIZED_MAP.get(key_sucio, animal_raw) # Fallback al original si no encuentra
                            
                            all_tabla[(dia, hora)] = nombre_oficial
                            if dia not in all_dias:
                                all_dias.append(dia)
                
                # Calcular siguiente fecha de inicio
                last_fetched_date = page_dias[-1]
                
                if last_fetched_date >= end_date:
                    break
                
                last_date_obj = datetime.strptime(last_fetched_date, "%Y-%m-%d").date()
                next_date_obj = last_date_obj + timedelta(days=1)
                next_start = next_date_obj.strftime("%Y-%m-%d")
                
                if next_start <= current_start:
                    logger.warning("El sitio devolvió fechas anteriores a las solicitadas. Deteniendo paginación.")
                    break
                    
                current_start = next_start

            except Exception as e:
                if isinstance(e, ScrapingError):
                    raise
                raise ScrapingError(f"Error al procesar el HTML: {e}") from e

        if iteration >= max_iterations:
            logger.warning("Se alcanzó el límite de iteraciones (%d). El historial puede estar incompleto.", max_iterations)

        # Ordenar días
        all_dias.sort()
        
        return HistorialData(dias=all_dias, horas=all_horas, tabla=all_tabla)

    def fetch_resultados_envivo(self, url: str) -> HistorialData:
        """
        Scrapea la página de resultados en vivo (ej. /resultados/) para obtener los datos del día actual.
        Útil cuando la página de historial tiene retraso.
        """
        import re
        import unicodedata
        
        def normalize(text):
            return ''.join(c for c in unicodedata.normalize('NFD', text) if unicodedata.category(c) != 'Mn').upper()
        
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = requests.get(url, headers=headers, timeout=TIMEOUT)
            resp.raise_for_status()
        except requests.RequestException as e:
            raise ConnectionError(f"Error al conectar con Resultados: {e}") from e
            
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Fecha de hoy
        today_str = datetime.now().strftime("%Y-%m-%d")
        
        all_tabla = {}
        all_horas = []
        
        # Regex para hora: 08:00 AM, 12:00 PM
        # Acepta espacios opcionales: 08:00AM o 08:00 AM
        time_pattern = re.compile(r"(\d{1,2}:\d{2}\s*[AP]M)")
        
        # Buscar todos los elementos que contienen texto de hora
        candidates = soup.find_all(string=time_pattern)
        
        for text_node in candidates:
            match = time_pattern.search(text_node)
            if not match:
                continue
                
            hora_str = match.group(1)
            
            # Normalizar hora
            try:
                # Eliminar espacios internos para parsear y luego re-formatear
                clean_h = hora_str.replace(" ", "").upper()
                # Insertar espacio antes de AM/PM si falta
                if "AM" in clean_h: clean_h = clean_h.replace("AM", " AM")
                if "PM" in clean_h: clean_h = clean_h.replace("PM", " PM")
                
                dt = datetime.strptime(clean_h, "%I:%M %p")
                hora_fmt = dt.strftime("%I:%M %p")
            except:
                hora_fmt = hora_str # Fallback
            
            # Buscar el animalito en el contexto cercano (padre o abuelo)
            container = text_node.parent
            found_animal = None
            
            # Intentamos buscar en el contenedor (hasta 4 niveles arriba)
            for _ in range(4):
                if not container: break
                
                container_text = container.get_text(" ", strip=True).upper()
                container_norm = normalize(container_text)
                
                # Buscar coincidencias con nuestros ANIMALITOS
                for num, nombre in ANIMALITOS.items():
                    # Buscamos "Num Nombre" (ej "7 PERICO")
                    target = f"{num} {normalize(nombre)}"
                    
                    # Verificación robusta: que el target esté en el texto
                    if target in container_norm:
                        found_animal = nombre
                        break
                    
                    # Fallback: Si el texto es solo "PERICO" (sin numero)
                    # Pero esto es peligroso si hay texto descriptivo.
                    # El screenshot muestra "7 Perico", así que la búsqueda con número debería funcionar.
                    
                if found_animal:
                    break
                
                container = container.parent
            
            if found_animal:
                if hora_fmt not in all_horas:
                    all_horas.append(hora_fmt)
                # Sobrescribir si ya existe (asumimos que el último encontrado es válido o son duplicados)
                all_tabla[(today_str, hora_fmt)] = found_animal
                
        return HistorialData(dias=[today_str], horas=sorted(all_horas), tabla=all_tabla)
