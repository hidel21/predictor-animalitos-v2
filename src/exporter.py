import pandas as pd
import io
from typing import List, Dict, Any, Union

class Exporter:
    """
    Clase encargada de transformar datos en formatos descargables (CSV, Excel).
    """

    @staticmethod
    def to_csv(data: Union[List[Dict[str, Any]], pd.DataFrame]) -> bytes:
        """
        Convierte una lista de diccionarios o un DataFrame a CSV (bytes).
        """
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data
            
        return df.to_csv(index=False).encode('utf-8')

    @staticmethod
    def to_excel(data: Union[List[Dict[str, Any]], pd.DataFrame], sheet_name: str = "Datos") -> bytes:
        """
        Convierte una lista de diccionarios o un DataFrame a Excel .xlsx (bytes).
        Requiere 'openpyxl' instalado.
        """
        if isinstance(data, list):
            df = pd.DataFrame(data)
        else:
            df = data
            
        output = io.BytesIO()
        # Usamos 'openpyxl' como motor por defecto para xlsx
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
        except ModuleNotFoundError:
            # Fallback si no está openpyxl, aunque debería estar.
            # Si falla, retornamos None o lanzamos error que se maneje arriba.
            raise ModuleNotFoundError("El módulo 'openpyxl' es necesario para exportar a Excel.")
            
        return output.getvalue()

    @staticmethod
    def create_full_report_excel(report_data: Dict[str, List[Dict[str, Any]]]) -> bytes:
        """
        Crea un archivo Excel con múltiples hojas.
        report_data: Diccionario donde la clave es el nombre de la hoja y el valor es la lista de datos.
        """
        output = io.BytesIO()
        try:
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                for sheet_name, data in report_data.items():
                    if data:
                        df = pd.DataFrame(data)
                        # Limpiar nombre de hoja para Excel (max 31 chars, sin caracteres especiales prohibidos)
                        safe_name = sheet_name.replace(":", "").replace("/", "-")[:31]
                        df.to_excel(writer, index=False, sheet_name=safe_name)
                    else:
                        # Crear hoja vacía con mensaje si no hay datos
                        pd.DataFrame({"Info": ["Sin datos"]}).to_excel(writer, index=False, sheet_name=sheet_name[:31])
        except ModuleNotFoundError:
             raise ModuleNotFoundError("El módulo 'openpyxl' es necesario para exportar a Excel.")

        return output.getvalue()
