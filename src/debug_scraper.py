
import logging
import sys
import os

# from historial_client import HistorialClient
# from constantes import ANIMALITOS
from .historial_client import HistorialClient
from .constantes import ANIMALITOS

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_scraper():
    client = HistorialClient()
    url = "https://lotoven.com/animalito/lagranjita/resultados/"
    print(f"Fetching {url}...")
    
    try:
        data = client.fetch_resultados_envivo(url)
        print("\n--- Results Found ---")
        for (date, time), animal in data.tabla.items():
            print(f"{date} {time}: {animal}")
            
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_scraper()
