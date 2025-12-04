import requests
from bs4 import BeautifulSoup

url = "https://lotoven.com/animalito/lagranjita/historial/2025-12-01/2025-12-03/"
headers = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
}

try:
    print(f"Fetching {url}...")
    resp = requests.get(url, headers=headers, timeout=20)
    print(f"Status: {resp.status_code}")
    
    soup = BeautifulSoup(resp.text, "html.parser")
    table = soup.find("table")
    
    if table:
        header_row = table.find("tr")
        if header_row:
            header_cells = header_row.find_all(["th", "td"])
            headers_text = [c.get_text(strip=True) for c in header_cells]
            print("Headers found:", headers_text)
            
            # Print first row of data
            rows = table.find_all("tr")
            if len(rows) > 1:
                first_data_row = rows[1].find_all("td")
                print("First row data:", [c.get_text(strip=True) for c in first_data_row])
        else:
            print("Table found but no rows.")
    else:
        print("No table found.")
        # Print part of body to see what's there
        print(soup.body.get_text()[:500])

except Exception as e:
    print(f"Error: {e}")
