
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.historial_client import HistorialClient
from src.constantes import ANIMALITOS
from datetime import date

def check_names():
    print("Descargando datos de hoy para verificar nombres...")
    client = HistorialClient()
    today = date.today().strftime("%Y-%m-%d")
    # Descargar hoy
    data = client.fetch_historial(today, today)
    
    print(f"\nResultados encontrados para {today}:")
    found_values = set(data.tabla.values())
    
    print(f"Valores únicos en data.tabla: {found_values}")
    
    print("\nComparando con ANIMALITOS (constantes):")
    constantes_values = set(ANIMALITOS.values())
    
    for val in found_values:
        # Intentar separar numero si viene "03 Ciempiés"
        parts = val.split()
        nombre_limpio = " ".join(parts[1:]) if len(parts) > 1 and parts[0].isdigit() else val
        
        if nombre_limpio in constantes_values:
            print(f"✅ '{val}' -> Coincide con '{nombre_limpio}'")
        else:
            print(f"❌ '{val}' -> NO coincide con ningún valor en ANIMALITOS")
            # Buscar parecidos
            for c in constantes_values:
                if nombre_limpio.lower() == c.lower():
                    print(f"   ⚠️ Pero se parece a '{c}' (diferencia de mayúsculas/tildes?)")
                elif nombre_limpio.replace("é", "e").replace("í", "i").replace("ó", "o").replace("á", "a") == c.replace("é", "e").replace("í", "i").replace("ó", "o").replace("á", "a"):
                     print(f"   ⚠️ Pero se parece a '{c}' (diferencia de tildes)")

if __name__ == "__main__":
    check_names()
