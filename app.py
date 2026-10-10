##############################################
# Lillié - Interfaz web (Streamlit)          #
# Reutiliza el agente de consola sin cambios #
##############################################

import os
import streamlit as st
import pandas as pd

# --------------------------------------------------------------------------- #
# 1) Llaves: en Streamlit Cloud vienen de st.secrets; en local, del .env.
#    Las copiamos a las variables de entorno ANTES de importar el agente,
#    porque el agente crea el cliente de Groq y lee HDR_API_KEY desde os.environ.
# --------------------------------------------------------------------------- #
for _key in ("GROQ_API_KEY", "HDR_API_KEY", "SUPABASE_URL", "SUPABASE_KEY"):
    try:
        if _key in st.secrets:
            os.environ[_key] = str(st.secrets[_key])
    except Exception:
        pass  # No hay secrets configurados (por ejemplo, corriendo en local con .env)

# Ahora si importamos el agente. Gracias al 'if __name__ == "__main__"' del
# archivo del agente, esta importacion NO lanza el bucle de consola.
from basic_agent_basic_memory_intermediate_tools import client, process_response

# Importamos las herramientas para poder llamarlas DIRECTAMENTE sobre los datos
# de un CSV, sin pasar por el modelo (asi evitamos el limite de tokens con datos grandes).
from intermediate_tools import IntermediateTools
tools_directo = IntermediateTools()

# --------------------------------------------------------------------------- #
# 1b) Supabase: base de datos en la nube para guardar el historial de conversaciones.
#     Si no hay credenciales, la app funciona igual pero sin guardar (no se rompe).
# --------------------------------------------------------------------------- #
import uuid

_SB_URL = os.environ.get("SUPABASE_URL")
_SB_KEY = os.environ.get("SUPABASE_KEY")
supabase = None
_SB_STATUS = ""  # para el diagnóstico visible en la barra lateral
if not _SB_URL or not _SB_KEY:
    _SB_STATUS = "Sin credenciales (revisa el .env)"
else:
    try:
        from supabase import create_client
        supabase = create_client(_SB_URL, _SB_KEY)
        _SB_STATUS = "Conectada"
    except Exception as e:
        _SB_STATUS = f"Error al conectar: {e}"
        supabase = None

# Un identificador unico por sesion, para agrupar los mensajes de una misma conversacion
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())


def guardar_en_supabase(role, content):
    """Guarda un mensaje en la tabla 'conversaciones'."""
    if supabase is None:
        return
    try:
        supabase.table("conversaciones").insert({
            "session_id": st.session_state.session_id,
            "role": role,
            "content": content,
        }).execute()
    except Exception as e:
        # Mostramos el error en pantalla para poder diagnosticarlo
        st.toast(f"No se pudo guardar en Supabase: {e}")
        print(f"No se pudo guardar en Supabase: {e}")

# --------------------------------------------------------------------------- #
# 2) Configuracion de la pagina
# --------------------------------------------------------------------------- #
import os as _os
_LOGO = "logo.png" if _os.path.exists("logo.png") else None
# El logo también se usa como avatar de Lillié en el chat (None si no hay logo.png)
AVATAR_LILLIE = _LOGO
AVATAR_USUARIO = "estrella.png" if _os.path.exists("estrella.png") else "⭐"  # avatar del usuario

st.set_page_config(
    page_title="Lillié",
    page_icon=_LOGO if _LOGO else ":material/insights:",
    layout="wide",
)

# --------------------------------------------------------------------------- #
# 3) Barra lateral
# --------------------------------------------------------------------------- #
with st.sidebar:
    # Logo centrado (usa logo.png si esta en la carpeta del proyecto)
    if _LOGO:
        izq, centro, der = st.columns([1, 3, 1])
        with centro:
            st.image(_LOGO, use_container_width=True)
    st.caption("Asistente de Políticas Públicas y Desarrollo Económico")

    if st.button("Limpiar conversación", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("#### Herramientas")
    st.markdown(
        "✸ **Banco Mundial** — indicadores de muchos países  \n"
        "✸ **Modelo de Solow** — simulación de crecimiento  \n"
        "✸ **FGT** — medición de pobreza  \n"
        "✸ **Desigualdad** — Gini, Palma, Theil  \n"
        "✸ **IDH** — Desarrollo humano (PNUD)  \n"
        "✸ **Tipo de cambio** — divisas  \n"
        "✸ **Gráficos** — líneas y barras"
    )
    st.markdown("---")
    st.caption("Bilingüe · español o inglés")

# --------------------------------------------------------------------------- #
# 4) Función para dibujar un gráfico a partir de la "receta" que da el agente
# --------------------------------------------------------------------------- #
def dibujar_grafico(g):
    try:
        etiquetas = g.get("etiquetas", [])
        series = g.get("series", [])
        datos = {s["nombre"]: s["valores"] for s in series}
        df = pd.DataFrame(datos, index=etiquetas)
        if g.get("titulo"):
            st.caption(g["titulo"])
        if g.get("tipo") == "barra":
            st.bar_chart(df)
        else:
            st.line_chart(df)
    except Exception as e:
        st.warning(f"No se pudo dibujar el gráfico: {e}")


# --------------------------------------------------------------------------- #
# 5) Panel para analizar un CSV propio (usa las herramientas DIRECTAMENTE)
# --------------------------------------------------------------------------- #
def mostrar_resultado_csv(res):
    fgt = res["fgt"]
    des = res["des"]
    st.caption(f"{res['n']} observaciones · línea de pobreza {res['linea']:g}")

    # Índices de pobreza (FGT) — apilados para caber en la barra lateral
    if "error" in fgt:
        st.warning(f"Pobreza (FGT): {fgt['error']}")
    else:
        idx = fgt["indices_fgt"]
        st.markdown("**Pobreza (FGT)**")
        st.metric("FGT0 · Incidencia", idx["FGT0_incidencia"])
        st.metric("FGT1 · Brecha", idx["FGT1_brecha"])
        st.metric("FGT2 · Severidad", idx["FGT2_severidad"])

    # Desigualdad
    if "error" in des:
        st.warning(f"Desigualdad: {des['error']}")
    else:
        st.markdown("**Desigualdad**")
        st.metric("Gini", des["gini"])
        palma = des["palma"]["ratio"]
        st.metric("Palma", palma if palma is not None else "N/D")
        st.metric("Theil", des["theil"] if des["theil"] is not None else "N/D")
        # Gráfico de participación por quintil (etiquetas cortas para el ancho angosto)
        q = des["participacion_por_quintil_pct"]
        dfq = pd.DataFrame({"% del ingreso": q}, index=["Q1", "Q2", "Q3", "Q4", "Q5"])
        st.caption("Ingreso por quintil (%) — Q1 más pobre, Q5 más rico")
        st.bar_chart(dfq)


def panel_csv(tools):
    with st.expander("Analiza tu propia base de datos (CSV) — pobreza y desigualdad"):
        st.caption("Sube una encuesta con una columna de ingresos (por ejemplo ENCOVI o ENEI). "
                   "El cálculo se hace directamente sobre tus datos, sin límites de tokens.")

        archivo = st.file_uploader("Archivo CSV", type=["csv"])
        if archivo is None:
            return

        # Leer el CSV (detecta el separador solo; intenta UTF-8 y luego Latin-1)
        try:
            df = pd.read_csv(archivo, sep=None, engine="python")
        except Exception:
            archivo.seek(0)
            try:
                df = pd.read_csv(archivo, sep=None, engine="python", encoding="latin-1")
            except Exception as e:
                st.error(f"No se pudo leer el CSV: {e}")
                return

        st.caption(f"{len(df)} filas leídas. Vista previa:")
        st.dataframe(df.head())

        columnas = list(df.columns)
        col_ing = st.selectbox("Columna de ingresos", columnas)
        col_peso = st.selectbox("Columna de pesos / factor de expansión (opcional)",
                                ["(ninguna)"] + columnas)
        linea = st.number_input("Línea de pobreza", min_value=0.0, value=1000.0, step=100.0)

        if st.button("Calcular pobreza y desigualdad"):
            ingresos_serie = pd.to_numeric(df[col_ing], errors="coerce")
            if col_peso != "(ninguna)":
                pesos_serie = pd.to_numeric(df[col_peso], errors="coerce")
                mask = ingresos_serie.notna() & pesos_serie.notna()
                ingresos = ingresos_serie[mask].tolist()
                pesos = pesos_serie[mask].tolist()
            else:
                ingresos = ingresos_serie.dropna().tolist()
                pesos = None

            if len(ingresos) == 0:
                st.error("La columna de ingresos no tiene valores numéricos válidos.")
                return

            st.session_state.csv_result = {
                "fgt": tools.calcular_fgt(ingresos, linea, pesos=pesos),
                "des": tools.calcular_desigualdad(ingresos, pesos=pesos),
                "n": len(ingresos),
                "linea": linea,
            }

        # Mostrar el último resultado calculado (persiste entre recargas)
        if "csv_result" in st.session_state:
            mostrar_resultado_csv(st.session_state.csv_result)
            if st.button("Pedir conclusiones a Lillié"):
                st.session_state.pending_prompt = resumen_csv_para_chat(st.session_state.csv_result)
                st.rerun()


def resumen_csv_para_chat(res):
    """Arma un resumen CHICO (solo los índices) para mandarlo al chat sin saturar tokens."""
    fgt = res["fgt"]
    des = res["des"]
    partes = [f"Analicé una encuesta de {res['n']} observaciones con línea de pobreza {res['linea']:g}."]
    if "error" not in fgt:
        idx = fgt["indices_fgt"]
        partes.append(
            f"Índices FGT: incidencia FGT0={idx['FGT0_incidencia']}, "
            f"brecha FGT1={idx['FGT1_brecha']}, severidad FGT2={idx['FGT2_severidad']}."
        )
    if "error" not in des:
        partes.append(
            f"Desigualdad: Gini={des['gini']}, Palma={des['palma']['ratio']}, Theil={des['theil']}. "
            f"Participación del ingreso por quintil (%, del más pobre al más rico): "
            f"{des['participacion_por_quintil_pct']}."
        )
    partes.append(
        "Con base en estos resultados, dame conclusiones e implicaciones de política pública. "
        "No necesitas calcular nada de nuevo; solo interpreta estos números."
    )
    return " ".join(partes)


with st.sidebar:
    st.markdown("---")
    panel_csv(tools_directo)
    # Estado de la base de datos (diagnóstico)
    st.markdown("---")
    st.caption(f"Base de datos: {_SB_STATUS}")
    # Crédito al pie de la barra lateral
    st.caption("Lilian Elías · Data Analytics · Héctor Galeros")

# --------------------------------------------------------------------------- #
# 6) Historial de la conversacion (memoria de la sesion)
# --------------------------------------------------------------------------- #
if "messages" not in st.session_state:
    st.session_state.messages = []

# Mostrar los mensajes previos (con sus gráficos si los tienen)
for m in st.session_state.messages:
    avatar = AVATAR_LILLIE if m["role"] == "assistant" else AVATAR_USUARIO
    with st.chat_message(m["role"], avatar=avatar):
        st.markdown(m["content"])
        for g in m.get("graficos", []):
            dibujar_grafico(g)

# --------------------------------------------------------------------------- #
# 7) Entrada del usuario y respuesta del agente
# --------------------------------------------------------------------------- #
# El prompt puede venir del cuadro de chat, o del botón "Pedir conclusiones"
prompt = st.chat_input("Escribe un mensaje para Lillié...")
if not prompt and st.session_state.get("pending_prompt"):
    prompt = st.session_state.pop("pending_prompt")

if prompt:

    # Historial ANTES de este mensaje (ultimos 10 turnos para no crecer sin limite).
    # Enviamos SOLO 'role' y 'content' al modelo: el campo 'graficos' es para la
    # pantalla, y la API de Groq rechaza campos que no reconoce.
    historia = [
        {"role": m["role"], "content": m["content"]}
        for m in st.session_state.messages[-10:]
    ]

    # Guardar y mostrar el mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    guardar_en_supabase("user", prompt)
    with st.chat_message("user", avatar=AVATAR_USUARIO):
        st.markdown(prompt)

    # Generar y mostrar la respuesta del agente
    with st.chat_message("assistant", avatar=AVATAR_LILLIE):
        with st.spinner("Pensando..."):
            try:
                respuesta, graficos = process_response(client, historia, prompt)
            except Exception as e:
                respuesta, graficos = f"Ocurrió un error al procesar tu mensaje: {e}", []
        st.markdown(respuesta)
        for g in graficos:
            dibujar_grafico(g)

    # Guardar la respuesta y sus gráficos para que se conserven en el historial
    st.session_state.messages.append({
        "role": "assistant",
        "content": respuesta,
        "graficos": graficos,
    })
    guardar_en_supabase("assistant", respuesta)

