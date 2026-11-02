##############################################
# Lillié - Interfaz web (Streamlit)          #
# Reutiliza el agente de consola sin cambios #
##############################################

import os
import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from zoneinfo import ZoneInfo

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

# Identificador único por CONVERSACIÓN (se renueva al dar "Nueva conversación")
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
# Título de la conversación actual (se arma con el primer mensaje del usuario)
if "titulo_chat" not in st.session_state:
    st.session_state.titulo_chat = None


def guardar_en_supabase(role, content):
    """Guarda un mensaje en la tabla 'conversaciones', con usuario y título del chat."""
    if supabase is None:
        return
    try:
        supabase.table("conversaciones").insert({
            "session_id": st.session_state.session_id,
            "usuario": st.session_state.get("usuario") or None,
            "titulo": st.session_state.get("titulo_chat"),
            "role": role,
            "content": content,
        }).execute()
    except Exception as e:
        # Mostramos el error en pantalla para poder diagnosticarlo
        st.toast(f"No se pudo guardar en Supabase: {e}")
        print(f"No se pudo guardar en Supabase: {e}")


def cargar_memoria(usuario, session_actual):
    """Trae las conversaciones ANTERIORES de este usuario (de otras sesiones)
    y las devuelve como texto, para dárselas a Lillié como memoria."""
    if supabase is None or not usuario:
        return ""
    try:
        resp = (supabase.table("conversaciones")
                .select("role, content, created_at, session_id")
                .eq("usuario", usuario)
                .neq("session_id", session_actual)   # solo sesiones pasadas
                .order("created_at", desc=True)
                .limit(30)                            # solo lo reciente (por los tokens)
                .execute())
        filas = resp.data or []
    except Exception as e:
        print(f"No se pudo cargar la memoria: {e}")
        return ""

    if not filas:
        return ""

    filas = list(reversed(filas))  # de más antiguo a más reciente
    lineas = []
    for f in filas:
        fecha = (f.get("created_at") or "")[:10]   # solo la parte AAAA-MM-DD
        quien = "Usuario" if f.get("role") == "user" else "Lillié"
        texto = (f.get("content") or "")[:250]     # recortamos para no gastar tokens
        lineas.append(f"[{fecha}] {quien}: {texto}")
    return "\n".join(lineas)


def listar_conversaciones(usuario, limite=15):
    """Devuelve las conversaciones recientes del usuario como lista de
    {session_id, titulo, fecha}, la más reciente primero."""
    if supabase is None or not usuario:
        return []
    try:
        resp = (supabase.table("conversaciones")
                .select("session_id, titulo, created_at")
                .eq("usuario", usuario)
                .order("created_at", desc=True)
                .limit(400)   # traemos varias filas y agrupamos por conversación
                .execute())
        filas = resp.data or []
    except Exception as e:
        print(f"No se pudo listar conversaciones: {e}")
        return []

    convs = []
    vistos = set()
    for f in filas:
        sid = f.get("session_id")
        if not sid or sid in vistos:
            continue
        vistos.add(sid)
        titulo_completo = (f.get("titulo") or "Conversación").strip()
        convs.append({
            "session_id": sid,
            "titulo": titulo_completo[:40],          # corto, para mostrar en la lista
            "titulo_completo": titulo_completo,       # completo, para el tooltip
            "fecha": (f.get("created_at") or "")[:10],
        })
        if len(convs) >= limite:
            break
    return convs


def cargar_conversacion(session_id):
    """Trae todos los mensajes de una conversación (por su session_id), en orden."""
    if supabase is None:
        return []
    try:
        resp = (supabase.table("conversaciones")
                .select("role, content, created_at")
                .eq("session_id", session_id)
                .order("created_at", desc=False)   # del más antiguo al más nuevo
                .execute())
        filas = resp.data or []
    except Exception as e:
        print(f"No se pudo cargar la conversación: {e}")
        return []
    return [{"role": f.get("role"), "content": f.get("content") or ""} for f in filas]


def generar_titulo(mensaje):
    """Pide a Lillié un título corto (3-5 palabras) que resuma el tema del chat."""
    try:
        r = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content":
                 "Devuelve SOLO un título corto de 3 a 5 palabras, en español, que resuma "
                 "el tema del mensaje. Sin comillas, sin punto final, sin explicaciones."},
                {"role": "user", "content": mensaje},
            ],
            max_tokens=20,
            temperature=0.3,
        )
        titulo = (r.choices[0].message.content or "").strip().strip('"').replace("\n", " ").strip()
        if titulo:
            return titulo[:45]
    except Exception as e:
        print(f"No se pudo generar título: {e}")
    return mensaje.strip()[:40]  # respaldo: el pedacito del mensaje


def fecha_de_hoy():
    """Fecha y hora actual en Guatemala, en español, calculada en cada recarga."""
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
             "agosto", "septiembre", "octubre", "noviembre", "diciembre"]
    d = datetime.now(ZoneInfo("America/Guatemala"))
    hora = d.strftime("%I:%M %p").lstrip("0")  # ej. 8:05 PM
    return f"{dias[d.weekday()]} {d.day} de {meses[d.month - 1]} de {d.year}, a las {hora}"

# --------------------------------------------------------------------------- #
# 2) Configuracion de la pagina
# --------------------------------------------------------------------------- #
import os as _os
import base64 as _base64
_LOGO = "logo.png" if _os.path.exists("logo.png") else None


def _fondo_css():
    """Si existe fondo.jpg en la carpeta, lo usa como fondo con una capa oscura
    encima (para que el texto se lea bien). Si no, deja fondo negro."""
    if _os.path.exists("fondo.jpg"):
        with open("fondo.jpg", "rb") as f:
            b64 = _base64.b64encode(f.read()).decode()
        return (
            ".stApp {"
            "  background: linear-gradient(rgba(9,11,16,0.80), rgba(9,11,16,0.88)),"
            f"              url('data:image/jpeg;base64,{b64}');"
            "  background-size: cover;"
            "  background-position: center;"
            "  background-attachment: fixed;"
            "}"
        )
    return ".stApp { background: #0D1117; }"
# El logo también se usa como avatar de Lillié en el chat (None si no hay logo.png)
# Avatar de Lillié: solo el isotipo (sin el texto); si no está, usa el logo completo
AVATAR_LILLIE = "isotipo.png" if _os.path.exists("isotipo.png") else _LOGO
def _avatar_usuario():
    """Dibuja un círculo azul oscuro con la inicial del nombre (o None si no hay nombre)."""
    nombre = st.session_state.get("usuario")
    if not (nombre and nombre.strip()):
        return None
    inicial = nombre.strip()[0].upper()
    try:
        from PIL import Image, ImageDraw, ImageFont
        import io
        S = 128
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse([0, 0, S - 1, S - 1], fill=(30, 58, 138, 255))  # azul oscuro #1E3A8A

        # Buscar una fuente que sí exista (Windows, Linux o la que haya)
        font = None
        for nombre_fuente in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf",
                              "DejaVuSans.ttf", "segoeui.ttf"):
            try:
                font = ImageFont.truetype(nombre_fuente, 92)   # letra grande
                break
            except Exception:
                continue
        if font is None:
            try:
                font = ImageFont.load_default(size=92)
            except Exception:
                font = ImageFont.load_default()

        caja = d.textbbox((0, 0), inicial, font=font)
        w, h = caja[2] - caja[0], caja[3] - caja[1]
        d.text(((S - w) / 2 - caja[0], (S - h) / 2 - caja[1]), inicial,
               fill=(255, 255, 255, 255), font=font)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None  # si algo falla, simplemente no mostramos avatar

st.set_page_config(
    page_title="Lillié",
    page_icon=_LOGO if _LOGO else ":material/insights:",
    layout="wide",
)

# Fondo con degradado morado (de morado profundo arriba a casi negro abajo)
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&family=Playfair+Display:wght@600;700&display=swap');

/* Barra lateral semitransparente (deja ver un poco el fondo) */
section[data-testid="stSidebar"] > div {
    background: rgba(9, 11, 15, 0.70);
}
/* Quitar la barra negra de arriba: encabezado transparente */
[data-testid="stHeader"] {
    background: transparent;
}
/* Contenido centrado con ancho máximo (márgenes a los lados) */
.stMainBlockContainer, [data-testid="stMainBlockContainer"] {
    max-width: 1200px;
    margin-left: auto;
    margin-right: auto;
}
/* Fuente serif (Lora) en todo el texto */
html, body, .stApp, .stApp p, .stApp li, .stApp label,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
.stButton button, .stApp input, .stApp textarea,
[data-testid="stMarkdownContainer"] {
    font-family: 'Lora', Georgia, serif !important;
}
/* El saludo grande con una serif más decorativa */
.saludo-lillie {
    font-family: 'Playfair Display', serif !important;
    font-size: 2.1rem;
    font-weight: 700;
    line-height: 1.15;
    margin: 0.2rem 0 0.4rem 0;
}
/* Botones redondeados con acento violeta */
.stButton button {
    border-radius: 10px;
    font-weight: 600;
}
.stButton button:hover {
    border-color: #2F80ED;
    color: #2F80ED;
}
/* Tarjetas de opciones: borde blanco y más compactas */
div[data-testid="stVerticalBlockBorderWrapper"] {
    border: 1px solid rgba(255, 255, 255, 0.75) !important;
    border-radius: 12px;
}
/* Botón dentro de las tarjetas: más pequeño */
div[data-testid="stVerticalBlockBorderWrapper"] .stButton button {
    padding: 0.15rem 0.6rem;
    min-height: 0;
}
/* Conversaciones recientes: enlaces pequeños, sin borde ni fondo */
[class*="st-key-conv_"] button {
    border: none !important;
    background: transparent !important;
    box-shadow: none !important;
    justify-content: flex-start !important;
    text-align: left !important;
    padding: 1px 6px !important;
    min-height: 0 !important;
    font-size: 0.72rem !important;
    font-weight: 400 !important;
    color: #9aa4b2 !important;
}
[class*="st-key-conv_"] button:hover {
    color: #E6EDF3 !important;
    background: rgba(255, 255, 255, 0.06) !important;
}
</style>
""", unsafe_allow_html=True)

# Fondo de la app (imagen con capa oscura si existe fondo.jpg; si no, negro)
st.markdown(f"<style>{_fondo_css()}</style>", unsafe_allow_html=True)

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

    # Navegación entre las dos vistas de la app
    vista = st.radio("Menú", ["Asistente", "Tablero"], label_visibility="collapsed")

    # Identidad ligera: activa la memoria personal del usuario
    st.text_input("Tu nombre o código (activa tu memoria)", key="usuario",
                  placeholder="ej. Lilian")

    if st.button("Nueva conversación", use_container_width=True):
        st.session_state.session_id = str(uuid.uuid4())  # chat nuevo = id nuevo
        st.session_state.messages = []
        st.session_state.titulo_chat = None
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

    # --- Conversaciones recientes (abajo, como enlaces pequeños) ---
    _usuario_actual = st.session_state.get("usuario")
    if _usuario_actual:
        convs = listar_conversaciones(_usuario_actual, limite=15)
        if convs:
            st.markdown("---")
            st.caption("Conversaciones recientes")
            for c in convs:
                etiqueta = c["titulo"] or "Conversación"
                if c["session_id"] == st.session_state.session_id:
                    etiqueta = "• " + etiqueta  # marca la conversación abierta
                if st.button(etiqueta, key=f"conv_{c['session_id']}",
                             use_container_width=True):
                    st.session_state.session_id = c["session_id"]
                    st.session_state.titulo_chat = c["titulo_completo"]
                    st.session_state.messages = cargar_conversacion(c["session_id"])
                    st.rerun()

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

# =========================================================================== #
# VISTA 1: ASISTENTE (el chat de siempre)
# =========================================================================== #
def vista_asistente():
    # Mostrar los mensajes previos (con sus gráficos si los tienen)
    for m in st.session_state.messages:
        avatar = AVATAR_LILLIE if m["role"] == "assistant" else _avatar_usuario()
        with st.chat_message(m["role"], avatar=avatar):
            st.markdown(m["content"])
            for g in m.get("graficos", []):
                dibujar_grafico(g)

    # Pantalla de bienvenida con tarjetas (solo cuando la conversación está vacía)
    if not st.session_state.messages:
        hora = datetime.now(ZoneInfo("America/Guatemala")).hour
        if hora < 12:
            saludo = "Buenos días"
        elif hora < 19:
            saludo = "Buenas tardes"
        else:
            saludo = "Buenas noches"
        nombre = st.session_state.get("usuario")
        titulo_saludo = f"{saludo}, {nombre}. Soy Lillié" if nombre else f"{saludo}, soy Lillié"
        st.markdown(f'<div class="saludo-lillie">{titulo_saludo}</div>', unsafe_allow_html=True)
        st.caption("Tu asistente de análisis de políticas públicas y desarrollo económico. "
                   "Consulto datos reales, simulo modelos de crecimiento, mido pobreza y "
                   "desigualdad, y genero gráficos.")
        st.markdown("#### ¿Qué quieres analizar hoy?")

        tarjetas = [
            ("Comparar países", "PIB per cápita de Guatemala, Honduras y El Salvador",
             "Compara el PIB per cápita de Guatemala, Honduras y El Salvador"),
            ("Consultar el IDH", "Índice de Desarrollo Humano de Guatemala",
             "¿Cuál es el IDH de Guatemala?"),
            ("Simular crecimiento", "Qué pasa si sube la inversión del 15% al 25%",
             "Simula qué pasa con el ingreso de largo plazo si Guatemala sube su tasa de "
             "inversión del 15% al 25%"),
            ("Graficar", "La evolución de la pobreza en Guatemala",
             "Grafica la evolución de la pobreza en Guatemala"),
            ("Medir pobreza y desigualdad", "FGT y Gini de una muestra de ingresos",
             "Con estos ingresos [800, 1200, 1500, 2000, 3500, 8000] y una línea de pobreza "
             "de 1500, calcula la pobreza (FGT) y la desigualdad (Gini) e interprétalas"),
            ("Explicar teoría", "El modelo de Romer frente a Solow",
             "Explícame el modelo de Romer y en qué se diferencia de Solow"),
        ]
        cols = st.columns(2)
        for i, (titulo, desc, texto) in enumerate(tarjetas):
            with cols[i % 2]:
                with st.container(border=True):
                    st.markdown(f"**{titulo}**")
                    st.caption(desc)
                    if st.button("Analizar", key=f"tarjeta_{i}", use_container_width=True):
                        st.session_state.pending_prompt = texto
                        st.rerun()

    # El prompt puede venir del cuadro de chat, o de un botón (tarjetas / CSV)
    prompt = st.chat_input("Escribe un mensaje para Lillié...")
    if not prompt and st.session_state.get("pending_prompt"):
        prompt = st.session_state.pop("pending_prompt")

    if prompt:
        # Historial ANTES de este mensaje (ultimos 10 turnos), solo role y content
        historia = [
            {"role": m["role"], "content": m["content"]}
            for m in st.session_state.messages[-10:]
        ]

        # Cargar la memoria del usuario UNA vez por nombre (de sesiones anteriores)
        usuario = st.session_state.get("usuario")
        if usuario and st.session_state.get("_memoria_para") != usuario:
            st.session_state.memoria_usuario = cargar_memoria(usuario, st.session_state.session_id)
            st.session_state._memoria_para = usuario

        # Contexto: nombre del usuario + fecha de hoy + memoria anterior
        contexto = f"La fecha de hoy es {fecha_de_hoy()} (zona horaria de Guatemala). " \
                   f"Si en tus instrucciones aparece otra fecha, esta es la correcta."
        if usuario:
            contexto += f" El usuario con el que hablas se llama {usuario}; " \
                        f"si te pregunta su nombre, respóndele que es {usuario}."
        memoria = st.session_state.get("memoria_usuario", "") if usuario else ""
        if memoria:
            contexto += ("\n\nTIENES MEMORIA de conversaciones anteriores con este usuario "
                         f"({usuario}). Úsala para recordar lo que hablaron en días previos si "
                         "te preguntan (por ejemplo '¿qué hicimos ayer?'). Conversaciones "
                         "anteriores, con su fecha:\n" + memoria)

        historia = [{"role": "system", "content": contexto}] + historia

        # Si es el primer mensaje del chat, su texto se vuelve el título
        if not st.session_state.get("titulo_chat"):
            st.session_state.titulo_chat = generar_titulo(prompt)

        # Guardar y mostrar el mensaje del usuario
        st.session_state.messages.append({"role": "user", "content": prompt})
        guardar_en_supabase("user", prompt)
        with st.chat_message("user", avatar=_avatar_usuario()):
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

        # Guardar la respuesta y sus gráficos
        st.session_state.messages.append({
            "role": "assistant",
            "content": respuesta,
            "graficos": graficos,
        })
        guardar_en_supabase("assistant", respuesta)


# =========================================================================== #
# VISTA 2: TABLERO comparativo de políticas públicas
# =========================================================================== #
# Países de Latinoamérica (nombre visible -> código ISO de 3 letras).
# Se usan todos para el mapa; el usuario elige un subconjunto para el gráfico de líneas.
PAISES_TABLERO = {
    "Guatemala": "GTM", "Honduras": "HND", "El Salvador": "SLV", "Nicaragua": "NIC",
    "Costa Rica": "CRI", "Panamá": "PAN", "Belice": "BLZ", "México": "MEX",
    "Rep. Dominicana": "DOM", "Cuba": "CUB", "Haití": "HTI",
    "Colombia": "COL", "Venezuela": "VEN", "Ecuador": "ECU", "Perú": "PER",
    "Bolivia": "BOL", "Brasil": "BRA", "Paraguay": "PRY", "Uruguay": "URY",
    "Argentina": "ARG", "Chile": "CHL",
}
# Indicadores: etiqueta -> (clave de la herramienta, fuente)
INDICADORES_TABLERO = {
    "PIB per cápita": ("pib_per_capita", "bm"),
    "Crecimiento del PIB": ("crecimiento_pib", "bm"),
    "Pobreza": ("pobreza", "bm"),
    "Desigualdad (Gini)": ("gini", "bm"),
    "Inflación": ("inflacion", "bm"),
    "Desempleo": ("desempleo", "bm"),
    "Gasto en educación": ("gasto_educacion", "bm"),
    "Gasto en salud": ("gasto_salud", "bm"),
    "Esperanza de vida": ("esperanza_vida", "bm"),
    "IDH": ("hdi", "pnud"),
}


def _series_banco_mundial(resultado):
    """Convierte la respuesta del Banco Mundial en {pais: {anio: valor}}."""
    if "error" in resultado:
        return {}, resultado.get("indicador", ""), resultado["error"]
    series = {}
    for pais, info in resultado.get("paises", {}).items():
        series[pais] = {int(d["anio"]): d["valor"] for d in info.get("serie", [])}
    return series, resultado.get("indicador", ""), None


def _series_pnud(resultado):
    """Convierte la respuesta del PNUD (IDH) en {pais: {anio: valor}} de forma tolerante."""
    if "error" in resultado:
        return {}, "Índice de Desarrollo Humano", resultado["error"]
    series = {}
    for fila in resultado.get("datos", []):
        if not isinstance(fila, dict):
            continue
        pais = fila.get("country") or fila.get("countryName") or fila.get("Country")
        anio = fila.get("year") or fila.get("Year")
        valor = fila.get("value") if fila.get("value") is not None else fila.get("Value")
        if pais is None or anio is None or valor is None:
            continue
        try:
            series.setdefault(str(pais), {})[int(anio)] = float(valor)
        except (TypeError, ValueError):
            continue
    return series, "Índice de Desarrollo Humano (PNUD)", None


def _traer_series(clave, fuente, codigos):
    """Pide los datos a la herramienta correcta y devuelve (series, nombre, error)."""
    if fuente == "bm":
        r = tools_directo.consultar_indicador_banco_mundial(clave, pais=codigos)
        return _series_banco_mundial(r)
    r = tools_directo.consultar_idh_pnud(pais=codigos, indicador=clave)
    return _series_pnud(r)


@st.cache_data(ttl=3600, show_spinner=False)
def _traer_series_cache(clave, fuente, codigos):
    """Versión cacheada: evita volver a llamar a la API por la misma consulta."""
    return _traer_series(clave, fuente, codigos)


def vista_tablero():
    st.markdown('<div class="saludo-lillie">Tablero comparativo</div>', unsafe_allow_html=True)
    st.caption("Datos reales del Banco Mundial y el PNUD. El mapa muestra toda Latinoamérica "
               "según el indicador; elige países para ver su evolución en líneas.")

    col_i, col_p = st.columns([1, 2])
    with col_i:
        sel_ind = st.selectbox("Indicador", list(INDICADORES_TABLERO.keys()))
    with col_p:
        sel_paises = st.multiselect("Países para el gráfico de líneas",
                                    list(PAISES_TABLERO.keys()),
                                    default=["Guatemala", "Honduras", "El Salvador"])

    clave, fuente = INDICADORES_TABLERO[sel_ind]

    # =================== MAPA (siempre visible, solo depende del indicador) =============
    with st.spinner("Cargando mapa..."):
        series_todos, nombre_ind, error = _traer_series_cache(
            clave, fuente, ";".join(PAISES_TABLERO.values()))

    st.markdown(f"**{nombre_ind or sel_ind} — mapa de Latinoamérica**")
    if error:
        st.error(error)
    elif not series_todos:
        st.info("No hay datos de mapa para este indicador.")
    else:
        filas = []
        for pais, serie_anios in series_todos.items():
            if not serie_anios:
                continue
            anio = max(serie_anios.keys())
            nombre_limpio = str(pais).split(",")[0].strip()  # "Venezuela, RB" -> "Venezuela"
            filas.append({"pais": nombre_limpio, "valor": serie_anios[anio], "anio": anio})
        df_mapa = pd.DataFrame(filas).dropna(subset=["valor"])

        if not df_mapa.empty:
            fig = px.choropleth(
                df_mapa, locations="pais", locationmode="country names",
                color="valor", hover_name="pais",
                hover_data={"pais": False, "valor": True, "anio": True},
                # Escala azul -> celeste (tecnológica, resalta)
                color_continuous_scale=["#0b2550", "#1E6FFF", "#19C6FF", "#8EEBFF"],
            )
            # Base oscura azulada tipo satelital, con fronteras tenues
            fig.update_geos(
                fitbounds="locations", visible=True,
                showland=True, landcolor="#0e1a33",
                showocean=True, oceancolor="#070d1a",
                showlakes=True, lakecolor="#070d1a",
                showcountries=True, countrycolor="rgba(255,255,255,0.18)",
                showcoastlines=False, bgcolor="rgba(0,0,0,0)",
            )
            fig.update_traces(marker_line_color="rgba(255,255,255,0.3)", marker_line_width=0.4)
            fig.update_layout(margin=dict(l=0, r=0, t=0, b=0),
                              paper_bgcolor="rgba(0,0,0,0)",
                              font_color="#E6EDF3",
                              coloraxis_colorbar_title="",
                              height=460)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No se pudo dibujar el mapa de este indicador.")

    # =================== LÍNEAS (independiente, según países elegidos) ==================
    st.markdown("---")
    if sel_paises:
        codigos_sel = ";".join(PAISES_TABLERO[p] for p in sel_paises)
        series_sel, _, err2 = _traer_series_cache(clave, fuente, codigos_sel)
        if err2:
            st.error(err2)
        elif series_sel:
            st.markdown("**Evolución en el tiempo:**")
            df_lineas = pd.DataFrame(series_sel).sort_index()
            st.line_chart(df_lineas)
            recientes = {}
            for pais in df_lineas.columns:
                s = df_lineas[pais].dropna()
                recientes[pais] = round(s.iloc[-1], 3) if not s.empty else None
            st.markdown("**Valor más reciente:**")
            st.dataframe(pd.DataFrame({"Valor más reciente": recientes}),
                         use_container_width=True)
        else:
            st.info("Los países elegidos no tienen datos para este indicador.")
    else:
        st.info("Elige países arriba para ver la evolución en el tiempo.")


# =========================================================================== #
# Despacho: mostrar la vista elegida en el menú
# =========================================================================== #
# Si hay un prompt pendiente (tarjetas o CSV), nos aseguramos de estar en el chat
if st.session_state.get("pending_prompt"):
    vista = "Asistente"

if vista == "Tablero":
    vista_tablero()
else:
    vista_asistente()