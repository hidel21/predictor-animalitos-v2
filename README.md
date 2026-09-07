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

## 9. Cómo se predice y qué ventaja real tiene

### 9.1. El patrón que sí existe: el efecto refractario

Contra lo que sugiere la intuición del jugador, el historial **no** premia a los
animalitos "calientes". Ocurre lo contrario: en casi todas las loterías analizadas
un animalito que acaba de salir tarda en volver, como si se repartiera *sin
reposición*. Medido sobre el historial completo de 2025:

| Lotería | Repite en el sorteo siguiente | Esperado por azar | z |
|---|---|---|---|
| Selva Plus | 0.00 % | 2.63 % | −6.5 |
| Lotto Rey | 0.13 % | 2.63 % | −6.2 |
| Lotto Activo RD | 0.45 % | 2.63 % | −5.4 |
| La Granjita | 0.76 % | 2.63 % | −4.6 |
| Lotto Activo | 0.76 % | 2.63 % | −4.6 |
| Lotto Activo Rep. Dominicana | 2.60 % | 2.63 % | −0.2 |

El efecto no se limita al sorteo siguiente ni se reinicia a medianoche: decae a lo
largo de unos 12 sorteos y luego rebota por encima del azar. **Lotto Activo
República Dominicana es la excepción**: ahí no hay señal alguna.

En cambio, el reparto a largo plazo de cada animalito es indistinguible del azar
(chi² con p entre 0.35 y 0.9997 en las seis loterías). Por eso los modelos basados
en frecuencia, atrasos por días o Márkov puntúan **peor** que apostar al azar.

### 9.2. El modelo `Refractario`

`src/temporal_features.py` estima, por máxima verosimilitud condicional y solo con
sorteos ya ocurridos, cuánto pesa cada animalito según los sorteos que lleva sin
salir. Los pesos se reajustan cada 32 sorteos y se encogen hacia "sin efecto", de
modo que **cada lotería aprende su propio perfil**:

```text
sorteos sin salir:   1     2-3   4-6   7-12  13-24 25-36  37+
La Granjita:        0.28  0.37  0.87  0.87  1.10  1.06  1.00
Lotto Rey:          0.11  0.33  0.63  0.82  1.47  1.20  1.00
Selva Plus:         0.05  0.34  0.59  0.86  1.22  1.03  1.00
Lotto Activo RDom:  0.99  0.99  1.04  1.02  1.00  1.07  1.00   <- sin señal
```

La probabilidad parte de la uniforme, no de la frecuencia histórica, precisamente
porque esa frecuencia es ruido.

### 9.3. Cómo se decide si un modelo se usa

`MLPredictor.train()` divide el historial en tres tramos consecutivos (60 % / 20 %
/ 20 %):

1. El primero pone en marcha los modelos incrementales y entrena los árboles.
2. En el segundo compite cada estrategia contra la referencia (uniforme o
   frecuencia). Se acepta solo si su **ventaja en log-verosimilitud** tiene el
   límite inferior del intervalo diario al 95 % por encima de cero y gana en al
   menos 2 de 3 bloques. Se decide con log-verosimilitud y no con el acierto Top 3
   porque el acierto es binario y su ruido tapa cualquier mejora real.
3. El tercero **no interviene en ninguna decisión** y sirve solo para medir.

Si ninguna estrategia pasa el filtro se usa la referencia, y la interfaz avisa de
que las predicciones no baten al azar.

### 9.4. Resultado en el tramo final (que no eligió nada)

| Lotería | Estrategia | Top 1 | Top 3 | Top 5 | Log-loss |
|---|---|---|---|---|---|
| La Granjita | Refractario | 3.2 % *(azar 2.1 %)* | **9.1 %** *(5.6 %)* | 16.8 % *(10.6 %)* | 3.611 *(3.638)* |
| Lotto Activo | Refractario | 3.0 % *(3.2 %)* | 9.4 % *(8.9 %)* | 13.9 % *(12.4 %)* | 3.616 *(3.638)* |
| Selva Plus | Refractario | 3.2 % *(3.0 %)* | 8.9 % *(8.6 %)* | 15.3 % *(13.3 %)* | 3.596 *(3.638)* |
| Lotto Rey | Refractario | 4.1 % *(1.5 %)* | **15.6 %** *(8.0 %)* | 20.4 % *(13.0 %)* | 3.575 *(3.638)* |
| Lotto Activo RD | Refractario | 5.3 % *(2.1 %)* | **13.3 %** *(7.1 %)* | 20.7 % *(13.6 %)* | 3.582 *(3.638)* |
| Lotto Activo Rep. Dom. | *(ninguna)* | — | — | — | — |

El log-loss mejora en las cinco loterías donde se despliega, que es la medida
honesta: son probabilidades mejor calibradas, no una racha afortunada. En la sexta
el sistema se abstiene por sí solo.

**Esto sigue siendo un juego de azar.** La ventaja es real y medible pero pequeña:
acertar 1 de cada 8 en Top 3 en lugar de 1 de cada 13. No convierte el juego en
rentable ni predice ningún sorteo concreto.

### 9.5. Catálogos de animalitos

`constantes.ANIMALITOS` define los 38 animalitos de La Granjita. **Guácharo Activo
usa un catálogo distinto de 77 animales** (Pereza, Pulpo, Panda, Avispa…). El
entrenamiento se detiene con un mensaje explícito si más del 2 % de los resultados
no está en el catálogo, en lugar de descartarlos en silencio y romper la secuencia
de sorteos.

---

## 10. Futuras Implementaciones

* **API REST (FastAPI)**: Para exponer los cálculos como servicio web.
* **Automatización**: Scripts para actualización diaria de datos.
