ANIMALITOS = {
    "0": "Delfín",
    "00": "Ballena",
    "1": "Carnero",
    "2": "Toro",
    "3": "Ciempiés",
    "4": "Alacrán",
    "5": "León",
    "6": "Rana",
    "7": "Perico",
    "8": "Ratón",
    "9": "Aguila",
    "10": "Tigre",
    "11": "Gato",
    "12": "Caballo",
    "13": "Mono",
    "14": "Paloma",
    "15": "Zorro",
    "16": "Oso",
    "17": "Pavo",
    "18": "Burro",
    "19": "Chivo",
    "20": "Cochino",
    "21": "Gallo",
    "22": "Camello",
    "23": "Cebra",
    "24": "Iguana",
    "25": "Gallina",
    "26": "Vaca",
    "27": "Perro",
    "28": "Zamuro",
    "29": "Elefante",
    "30": "Caimán",
    "31": "Lapa",
    "32": "Ardilla",
    "33": "Pescado",
    "34": "Venado",
    "35": "Jirafa",
    "36": "Culebra",
}

# Definición de Colores (Ruleta Americana Estándar adaptada a 0-36)
# 0 y 00 son Verdes
# El resto alternan Rojo/Negro según patrón estándar
COLORES = {
    "0": "green", "00": "green",
    "1": "red", "2": "black", "3": "red", "4": "black", "5": "red", "6": "black",
    "7": "red", "8": "black", "9": "red", "10": "black", "11": "black", "12": "red",
    "13": "black", "14": "red", "15": "black", "16": "red", "17": "black", "18": "red",
    "19": "red", "20": "black", "21": "red", "22": "black", "23": "red", "24": "black",
    "25": "red", "26": "black", "27": "red", "28": "black", "29": "black", "30": "red",
    "31": "black", "32": "red", "33": "black", "34": "red", "35": "black", "36": "red"
}

# Definición de Sectores (Ejemplo: Agrupación numérica simple para La Granjita)
# Se pueden ajustar según estrategia específica
SECTORES = {
    "Sector A (0-6)": ["0", "00", "1", "2", "3", "4", "5", "6"],
    "Sector B (7-12)": ["7", "8", "9", "10", "11", "12"],
    "Sector C (13-18)": ["13", "14", "15", "16", "17", "18"],
    "Sector D (19-24)": ["19", "20", "21", "22", "23", "24"],
    "Sector E (25-30)": ["25", "26", "27", "28", "29", "30"],
    "Sector F (31-36)": ["31", "32", "33", "34", "35", "36"]
}

DOCENAS = {
    "1ª Docena (1-12)": [str(i) for i in range(1, 13)],
    "2ª Docena (13-24)": [str(i) for i in range(13, 25)],
    "3ª Docena (25-36)": [str(i) for i in range(25, 37)]
}

COLUMNAS = {
    "Columna 1": [str(i) for i in range(1, 37, 3)], # 1, 4, 7...
    "Columna 2": [str(i) for i in range(2, 37, 3)], # 2, 5, 8...
    "Columna 3": [str(i) for i in range(3, 37, 3)]  # 3, 6, 9...
}
