# Predictor de Animalitos - La Granjita

Este proyecto es un motor estadístico en Python diseñado para analizar el historial de resultados de *Animalitos – La Granjita* y calcular probabilidades utilizando un modelo de cadenas de Márkov.

## 1. ¿Qué es este entorno y para qué sirve?

El sistema permite:

1. **Descargar el historial** de resultados desde Lotoven en un rango de fechas específico.
2. **Procesar los datos** para construir:
   * Frecuencia de aparición de cada animalito.
   * Un **modelo de transiciones** (quién suele salir después de quién).
3. **Calcular probabilidades**:
   * Probabilidad global de cada animalito.
   * Probabilidad condicional: `P(B | A)` (probables siguientes animalitos dado uno actual).
4. **Uso desde consola (CLI)** para consultas rápidas.

---

## 2. Estructura del proyecto

```text
predictor/
├── README.md
├── requirements.txt
├── .gitignore
└── src/
    ├── __init__.py
    ├── config.py
    ├── historial_client.py
    ├── model.py
    └── cli.py
```

### Descripción de archivos

* **`README.md`**: Documentación del proyecto.
* **`requirements.txt`**: Dependencias (`requests`, `beautifulsoup4`, `pandas`, `rich`).
* **`src/config.py`**: Variables de configuración (`BASE_URL`, `USER_AGENT`, `TIMEOUT`).
* **`src/historial_client.py`**: Módulo de conexión a `lotoven.com`, descarga y parseo de datos HTML.
* **`src/model.py`**: Lógica del modelo de Márkov. Calcula frecuencias, transiciones y probabilidades.
* **`src/cli.py`**: Interfaz de línea de comandos para interactuar con el sistema.

---

## 3. Funcionalidades

Con este entorno puedes:

1. **Analizar un rango de fechas** (ej. 2025-12-01 a 2025-12-07).
2. Generar un **Top de animalitos más frecuentes** en ese periodo.
3. Ver **qué animalitos suelen seguir a otro** concreto (Probabilidad Condicional).
4. Ajustar el rango para análisis semanales, mensuales, etc.

---

## 4. Instalación y Configuración

### 4.1. Crear entorno virtual

**Linux / Mac:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.venv\Scripts\activate
```

### 4.2. Instalar dependencias

Con el entorno activado:
```bash
pip install -r requirements.txt
```

---

## 5. Uso desde consola (CLI)

El comando base ejecuta el análisis para un rango de fechas.

### Análisis General
```bash
python -m src.cli --start YYYY-MM-DD --end YYYY-MM-DD
```

Ejemplo:
```bash
python -m src.cli --start 2025-12-01 --end 2025-12-07
```
Esto mostrará el top de animalitos más probables basado en el historial descargado.

### Predicción Condicional (¿Qué sale después de...?)
Para consultar las probabilidades de transición dado un animal específico (ej. Iguana):

```bash
python -m src.cli --start 2025-12-01 --end 2025-12-07 --after Iguana
```
Esto mostrará los animalitos que más frecuentemente han salido inmediatamente después de la "Iguana".

---

## 6. Configuración de Base de Datos (Neon PostgreSQL)

El sistema utiliza PostgreSQL para persistencia de datos. La configuración se maneja a través de **secrets**.

### 6.1. Configuración Local

Crea un archivo `.streamlit/secrets.toml` en la raíz del proyecto (este archivo está ignorado por git):

```toml
[postgres]
user = "neondb_owner"
password = "TU_PASSWORD_AQUI"
host = "ep-tu-endpoint.us-east-1.aws.neon.tech"
port = "5432"
database = "neondb"
sslmode = "require"
```

### 6.2. Configuración en Streamlit Cloud

Al desplegar, debes configurar los mismos secretos en el panel de administración de Streamlit Cloud:
1. Ve a **Settings** -> **Secrets**.
2. Pega el contenido del bloque `[postgres]` tal cual se muestra arriba.

---

## 7. Deploy en Streamlit Cloud

Para llevar la aplicación a producción:

1. **Repositorio**: Asegúrate de que tu código esté en GitHub.
2. **Secrets**: Verifica que `.streamlit/secrets.toml` **NO** esté en el repositorio (debe estar en `.gitignore`).
3. **Streamlit Cloud**:
   * Crea una nueva app conectada a tu repositorio.
   * Selecciona el archivo principal: `src/app.py`.
   * Antes de iniciar (o en Settings después), configura los **Secrets** como se indicó en el punto 6.2.
4. **Verificación**:
   * La aplicación se reiniciará automáticamente al guardar los secrets.
   * Verifica en los logs que aparezca: `✅ [DB] Conexión a PostgreSQL establecida correctamente.`

---

## 8. Flujo interno

1. **`HistorialClient.fetch_historial`**:
   * Construye la URL y descarga el HTML.
   * Parsea la tabla de resultados (días vs horas).
2. **`MarkovModel.from_historial`**:
   * Contabiliza frecuencias absolutas.
   * Identifica secuencias y cuenta transiciones `(A -> B)`.
3. **Cálculo de Probabilidades**:
   * **Global**: `Prob(A) = Frecuencia(A) / Total Sorteos`
   * **Condicional**: `Prob(B|A) = Transiciones(A->B) / Total Transiciones desde A`

---

## 9. Futuras Implementaciones

* **API REST (FastAPI)**: Para exponer los cálculos como servicio web.
* **Automatización**: Scripts para actualización diaria de datos.
