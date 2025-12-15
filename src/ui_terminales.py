import streamlit as st
import pandas as pd
from datetime import datetime, date
from src.constantes import ANIMALITOS

def _format_num(key: str) -> str:
    """Formatea un key tipo '5' -> '05', '15' -> '15', '0' -> '0', '00' -> '00'."""
    if key == "00":
        return "00"
    if key == "0":
        return "0"
    try:
        n = int(key)
    except Exception:
        return str(key)
    return f"{n:02d}" if 0 <= n < 10 else str(n)


def _terminal_from_key(key: str) -> int | None:
    if key == "00":
        return 0
    try:
        return int(key) % 10
    except Exception:
        return None


def _extraer_numero_key_desde_valor(valor: str) -> str | None:
    """Extrae el key del número (incluye '00') desde un valor tipo '24 Iguana'."""
    if not valor:
        return None

    parts = str(valor).strip().split()
    if parts:
        token = parts[0]
        if token.isdigit():
            # Preserva '00'
            if token == "00":
                return "00"
            # Normaliza otros a su representación sin ceros a la izquierda
            try:
                return str(int(token))
            except Exception:
                return None

    # Fallback: buscar coincidencia por nombre oficial
    v_norm = str(valor)
    for k, nombre in ANIMALITOS.items():
        if v_norm.startswith(f"{k} ") or v_norm == k or nombre in v_norm:
            return k
    return None


def _parse_hora_to_minutes(hora_str: str) -> int | None:
    """Convierte '10:00 AM'/'22:00' a minutos para ordenar. Retorna None si no se puede parsear."""
    if not hora_str:
        return None
    s = str(hora_str).strip()
    for fmt in ("%I:%M %p", "%H:%M", "%H:%M:%S"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.hour * 60 + dt.minute
        except Exception:
            continue
    return None


def _siblings_for_terminal(terminal: int) -> list[str]:
    """Devuelve los números 'hermanos' (como keys) que comparten terminal."""
    if terminal == 0:
        base = ["00", "0", "10", "20", "30"]
        return [k for k in base if k in ANIMALITOS]

    candidates: list[str] = []
    for n in (terminal, 10 + terminal, 20 + terminal, 30 + terminal):
        if n <= 36:
            k = str(n)
            if k in ANIMALITOS:
                candidates.append(k)
    return candidates


def _to_historial_df(data) -> pd.DataFrame:
    """Convierte HistorialData (app) o DataFrame en un DataFrame con columnas fecha/hora/numero_key/terminal."""
    if isinstance(data, pd.DataFrame):
        df = data.copy()
        # Intentar normalizar si viene con 'numero' como int
        if "numero_key" not in df.columns and "numero" in df.columns:
            df["numero_key"] = df["numero"].apply(lambda x: "00" if str(x) == "00" else str(int(x)) if str(x).isdigit() else None)
        if "terminal" not in df.columns and "numero_key" in df.columns:
            df["terminal"] = df["numero_key"].apply(_terminal_from_key)
        return df

    # HistorialData: tiene .tabla {(fecha, hora): '24 Iguana'}
    if hasattr(data, "tabla") and isinstance(getattr(data, "tabla"), dict):
        rows: list[dict] = []
        for (fecha, hora), valor in data.tabla.items():
            key = _extraer_numero_key_desde_valor(valor)
            if key is None:
                continue
            term = _terminal_from_key(key)
            if term is None:
                continue
            rows.append({"fecha": fecha, "hora": hora, "numero_key": key, "terminal": term})
        return pd.DataFrame(rows)

    return pd.DataFrame([])


def render_terminales_tab(data):
    """
    Renderiza la pestaña de Análisis por Terminales Diarios (HU-039).
    Permite visualizar cronológicamente los sorteos filtrados por terminal,
    resaltando el número ganador dentro de su familia de terminales.
    """
    st.header("🧩 Análisis por Terminales Diarios")

    historial_df = _to_historial_df(data)
    
    if historial_df.empty:
        st.warning("No hay datos históricos disponibles.")
        return

    # Normalizaciones mínimas
    if "numero_key" not in historial_df.columns and "numero" in historial_df.columns:
        historial_df["numero_key"] = historial_df["numero"].apply(lambda x: "00" if str(x) == "00" else str(int(x)) if str(x).isdigit() else None)
    if "terminal" not in historial_df.columns and "numero_key" in historial_df.columns:
        historial_df["terminal"] = historial_df["numero_key"].apply(_terminal_from_key)

    # --- Controles Superiores ---
    # Rango de fechas global (dentro de la pestaña)
    df_work = historial_df.copy()
    df_work["fecha_dt"] = pd.to_datetime(df_work["fecha"], errors="coerce")
    df_work = df_work.dropna(subset=["fecha_dt"])

    if df_work.empty:
        st.warning("No hay fechas válidas en el historial.")
        return

    min_d = df_work["fecha_dt"].min().date()
    max_d = df_work["fecha_dt"].max().date()

    c_range1, c_range2, c_range3, c_range4 = st.columns([1, 1, 1, 2])
    with c_range1:
        fecha_inicio = st.date_input("Desde", value=min_d, min_value=min_d, max_value=max_d, key="term_fecha_inicio")
    with c_range2:
        fecha_fin = st.date_input("Hasta", value=max_d, min_value=min_d, max_value=max_d, key="term_fecha_fin")

    if isinstance(fecha_inicio, date) and isinstance(fecha_fin, date) and fecha_inicio > fecha_fin:
        st.error("El rango de fechas es inválido (Desde > Hasta).")
        return

    with c_range3:
        terminal = st.selectbox("Terminal", options=list(range(10)), index=0, key="term_digit")
    with c_range4:
        mostrar_todo_el_dia = st.toggle(
            "Mostrar todo el día (1er → último sorteo)",
            value=False,
            help="Si está activo, verás todas las horas del día en el rango, aunque no corresponda al terminal seleccionado."
        )

    # Familia / número exacto
    siblings_keys = _siblings_for_terminal(int(terminal))
    siblings_opts = ["(Cualquiera)"] + siblings_keys
    exact_key = st.selectbox(
        "Número exacto (opcional)",
        options=siblings_opts,
        index=0,
        format_func=lambda k: k if k == "(Cualquiera)" else f"{_format_num(k)} - {ANIMALITOS.get(k, '')}",
        help="Si eliges un número, se muestran solo las filas donde salió ese número dentro del rango."
    )

    # Filtro de días de la semana (opcional)
    dias_semana = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    dias_seleccionados = st.multiselect(
        "Días de la semana",
        options=dias_semana,
        default=dias_semana,
        key="term_dias_semana",
    )

    st.markdown("---")

    # --- Procesamiento de Datos ---
    df_filtered = df_work.copy()
    
    # Mapeo de días
    dias_map = {0: "Lunes", 1: "Martes", 2: "Miércoles", 3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo"}
    df_filtered['dia_nombre'] = df_filtered['fecha_dt'].dt.dayofweek.map(dias_map)
    
    # 1) Filtrar por rango de fechas
    df_filtered = df_filtered[(df_filtered['fecha_dt'].dt.date >= fecha_inicio) & (df_filtered['fecha_dt'].dt.date <= fecha_fin)]

    # 2) Filtrar por días de la semana
    if dias_seleccionados:
        df_filtered = df_filtered[df_filtered['dia_nombre'].isin(dias_seleccionados)]

    # 3) Filtrar por terminal (si no está activado el modo "todo el día")
    if not mostrar_todo_el_dia:
        df_filtered = df_filtered[df_filtered['terminal'] == int(terminal)]

    # 4) Filtrar por número exacto (opcional)
    if exact_key != "(Cualquiera)":
        df_filtered = df_filtered[df_filtered['numero_key'] == exact_key]

    # Preparar orden por hora real
    df_filtered['hora_min'] = df_filtered['hora'].apply(_parse_hora_to_minutes)

    # --- Resumen global del rango (antes del detalle por día) ---
    # Nota: este resumen se calcula sobre el rango + días de semana, sin depender de mostrar_todo_el_dia.
    df_rango = df_work.copy()
    df_rango = df_rango[(df_rango['fecha_dt'].dt.date >= fecha_inicio) & (df_rango['fecha_dt'].dt.date <= fecha_fin)]
    df_rango['dia_nombre'] = df_rango['fecha_dt'].dt.dayofweek.map(dias_map)
    if dias_seleccionados:
        df_rango = df_rango[df_rango['dia_nombre'].isin(dias_seleccionados)]

    with st.expander("📊 Resumen global del rango", expanded=False):
        c1, c2 = st.columns([1, 1])

        with c1:
            term_counts = df_rango['terminal'].value_counts().sort_index()
            df_term_counts = (
                term_counts.rename_axis('terminal')
                .reset_index(name='sorteos')
                .sort_values('terminal')
            )
            st.caption("Sorteos por terminal (en el rango)")
            st.dataframe(df_term_counts, width="stretch", height=260)

        with c2:
            df_sel = df_rango[df_rango['terminal'] == int(terminal)]
            if df_sel.empty:
                st.caption(f"Distribución de números (terminal {terminal})")
                st.info("No hay sorteos para ese terminal en el rango.")
            else:
                num_counts = df_sel['numero_key'].value_counts()
                df_num_counts = (
                    num_counts.rename_axis('numero')
                    .reset_index(name='veces')
                )
                df_num_counts['numero_fmt'] = df_num_counts['numero'].apply(_format_num)
                df_num_counts['animal'] = df_num_counts['numero'].map(lambda k: ANIMALITOS.get(k, ""))
                df_num_counts = df_num_counts[['numero_fmt', 'animal', 'veces']]
                st.caption(f"Distribución de números (terminal {terminal})")
                st.dataframe(df_num_counts, width="stretch", height=260)

    # --- Visualización ---
    
    if df_filtered.empty:
        st.info("No se encontraron sorteos con los filtros seleccionados.")
        return

    # Agrupar por fecha
    # Como ordenamos por fecha DESC, los grupos saldrán en ese orden (si sort=False en groupby o iterando unique)
    # Fechas en orden ascendente para ver del primer día al último (global)
    fechas_unicas = sorted(df_filtered['fecha_dt'].dt.date.unique())

    st.markdown(f"### 📅 Resultados ({len(df_filtered)} sorteos encontrados)")

    for fecha_val in fechas_unicas:
        grupo = df_filtered[df_filtered['fecha_dt'].dt.date == fecha_val]
        
        if grupo.empty:
            continue
            
        dia_str = grupo.iloc[0]['dia_nombre']
        fecha_str = pd.to_datetime(fecha_val).strftime('%d/%m/%Y')
        
        # Encabezado del día
        st.markdown(f"#### {dia_str} {fecha_str}")
        
        # Orden dentro del día: del primer sorteo al último
        grupo_sorted = grupo.sort_values(by=['hora_min', 'hora'], ascending=[True, True])

        rows_html = ""
        siblings_keys = _siblings_for_terminal(int(terminal))

        for _, row in grupo_sorted.iterrows():
            hora = row['hora']
            ganador_key = str(row.get('numero_key', ''))

            # Construir HTML de la fila
            siblings_html: list[str] = []
            for sib_key in siblings_keys:
                sib_disp = _format_num(sib_key)
                if sib_key == ganador_key:
                    style = (
                        "background-color: #FFC107; "
                        "color: #000; "
                        "padding: 2px 8px; "
                        "border-radius: 4px; "
                        "font-weight: bold; "
                        "border: 2px solid #FFA000; "
                        "box-shadow: 0 0 5px rgba(255, 193, 7, 0.5);"
                    )
                    siblings_html.append(f"<span style='{style}'>{sib_disp}</span>")
                else:
                    style = "color: #666; padding: 2px 4px;"
                    siblings_html.append(f"<span style='{style}'>{sib_disp}</span>")

            siblings_str = " <span style='color:#444'>-</span> ".join(siblings_html)

            # Si se muestra todo el día, puede que el ganador no pertenezca al terminal seleccionado.
            # En ese caso mostramos una 'chapita' con el número real para no perder contexto.
            ganador_badge = ""
            if mostrar_todo_el_dia and (ganador_key not in siblings_keys):
                g_disp = _format_num(ganador_key)
                g_name = ANIMALITOS.get(ganador_key, "")
                g_title = f"{g_disp} - {g_name}" if g_name else g_disp
                ganador_badge = (
                    f"<span title=\"{g_title}\" style=\""
                    "background-color: rgba(255,255,255,0.06); "
                    "color: rgba(255,255,255,0.85); "
                    "padding: 2px 8px; "
                    "border-radius: 999px; "
                    "border: 1px solid rgba(255,255,255,0.14); "
                    "margin-left: 10px;"
                    "\">"
                    f"Real: {g_disp}"
                    "</span>"
                )

            row_style = (
                "display: flex; "
                "align-items: center; "
                "margin-bottom: 6px; "
                "font-family: 'Courier New', monospace; "
                "font-size: 1.1em; "
                "background-color: #1E1E1E; "
                "padding: 8px; "
                "border-radius: 6px; "
                "border-left: 4px solid #333;"
            )

            rows_html += (
                f"<div style=\"{row_style}\">"
                f"<span style=\"min-width: 100px; color: #EEE; font-weight: bold;\">{hora}</span>"
                f"{ganador_badge}"
                f"<span style=\"color: #555; margin: 0 15px;\">|</span>"
                f"<span>{siblings_str}</span>"
                f"</div>"
            )
        
        st.markdown(rows_html, unsafe_allow_html=True)
        # Separador sutil entre días
        st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)
