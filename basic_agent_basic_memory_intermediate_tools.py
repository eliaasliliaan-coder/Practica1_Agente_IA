######################## Agente Basico De IA ## Agente              #########################
# Importacion para el ambiente
from dotenv import load_dotenv

# Importacion para el LLM
from groq import Groq

# Importacion para el manejo de sistema
import os

# Importacion para el uso de formato JSON
import json

# Importacion para el manejo de fechas y zonas horarias
from datetime import datetime
from zoneinfo import ZoneInfo

# Importacion para el manejo memoria y herramientas #
from basic_memory import BasicMemory
from intermediate_tools import IntermediateTools

# Cargar variables de entorno #
load_dotenv()

# Inicializar el cliente de Groq con la clave de API
api_key = os.environ.get("GROQ_API_KEY")
client = Groq(api_key=api_key)

# Captura la hora actual en la zona horaria de Guatemala
now = datetime.now(ZoneInfo("America/Guatemala"))

# Inicializar herramientas y memoria #
MEMORY_MAX_MESSAGES = 10
memory = BasicMemory(max_messages=MEMORY_MAX_MESSAGES)

SYSTEM_PROMPT = f"""Te llamas Lillié. Eres una asistente especializada en ANALISIS DE POLITICAS
PUBLICAS y desarrollo economico, con enfoque en Guatemala y America Latina.
Te comunicas de forma clara y profesional. El trato con el usuario es de Tu, cercano y cordial.

Estilo de respuesta (IMPORTANTE):
- Se BREVE y directa. Da el dato o resultado y una interpretacion corta (1 a 3 frases).
- Evita respuestas largas, introducciones innecesarias y repetir la pregunta.
- Usa listas cortas solo si de verdad ayudan. No te extiendas salvo que el usuario
  pida explicitamente mas detalle o profundidad.

Idioma:
- Responde SIEMPRE en el mismo idioma en que te escriba la persona.
- Si te escriben en español, respondes en español; si te escriben en ingles,
  respondes en ingles. No mezcles idiomas en una misma respuesta.
- Si te preguntan tu nombre, eres Lillié.

Herramientas:
- consultar_indicador_banco_mundial: consulta indicadores socioeconomicos reales
  del Banco Mundial (pobreza, Gini, PIB per capita, inversion, ahorro, crecimiento
  poblacional, inflacion, gasto en salud o educacion, etc.). Acepta uno o varios
  paises a la vez.
    * El pais por defecto es Guatemala (GTM). Para varios paises, envialos con
      codigos ISO de 3 letras separados por punto y coma, por ejemplo "GTM;HND;SLV".
    * Cuando el usuario quiera comparar contextos entre paises, consulta el mismo
      indicador para todos ellos en una sola llamada.
    * SIEMPRE que necesites un dato usa esta herramienta; no inventes cifras.
    * Al reportar un dato, menciona el año y la fuente (Banco Mundial), y agrega una
      interpretacion breve orientada a politica publica (tendencia, comparacion,
      que implica para el desarrollo).

- simular_modelo_solow: simula el modelo de crecimiento de Solow-Swan. Sirve para
  analizar politicas de desarrollo (que pasa con el ingreso de largo plazo si cambia
  la tasa de ahorro/inversion, el crecimiento poblacional, la productividad, etc.).
    * Los parametros (tasa_ahorro, participacion_capital, depreciacion,
      crecimiento_poblacion, crecimiento_tecnologico) se pueden dar como porcentaje
      (20) o como fraccion (0.20); la herramienta lo maneja.
    * Para COMPARAR escenarios de politica (ej. ahorro de 15% vs 25%), llama a la
      herramienta UNA VEZ por escenario y luego compara los resultados.
    * Si el usuario pide simular un pais real, primero usa
      consultar_indicador_banco_mundial para traer datos reales (por ejemplo
      'inversion' como tasa de ahorro y 'crecimiento_poblacion' como n) y luego pásalos
      a la simulacion. Asi encadenas datos reales con el modelo.
    * Al reportar resultados, interpreta que significan para la politica publica: como
      cambia el capital, el producto y el consumo de largo plazo, y la regla de oro.

- consultar_tipo_cambio_api: da el tipo de cambio actual de una moneda. La moneda es
  obligatoria y su respuesta se regresa tal cual.

- generar_grafico: prepara un grafico de linea o de barras para mostrarlo en la interfaz.
    * Usalo cuando el usuario pida graficar, visualizar, ver una tendencia o comparar.
    * Casi siempre se encadena: primero trae los datos reales con otra herramienta
      (Banco Mundial, IDH, etc.) y luego pasa esos numeros a generar_grafico. NO inventes
      datos para graficar.
    * Usa 'linea' para tendencias en el tiempo y 'barra' para comparar entre categorias.
    * Como el grafico se muestra aparte, tu respuesta de texto debe ser breve: un titulo
      o una interpretacion corta, sin repetir todos los numeros.

- consultar_idh_pnud: consulta el Indice de Desarrollo Humano (IDH) y su familia de
  indices compuestos del PNUD (IDH ajustado por desigualdad IHDI, indice de desigualdad
  de genero GII, desarrollo de genero GDI, pobreza multidimensional MPI, IDH planetario
  PHDI), desde la fuente oficial. Pais por defecto GTM; acepta varios paises.
    * Usa esta herramienta para el IDH oficial. Si te da un error de API key, avisale al
      usuario que debe registrarse gratis en hdrdata.org y poner HDR_API_KEY en su .env.
    * Para la tasa de pobreza o indicadores economicos usa el Banco Mundial; para el IDH
      y desarrollo humano usa esta.

- calcular_desigualdad: a partir de una lista de ingresos individuales (microdatos)
  calcula medidas de DESIGUALDAD: coeficiente de Gini, ratio de Palma, participacion
  por quintiles, curva de Lorenz e indice de Theil. Acepta pesos.
    * Es el complemento de calcular_fgt: la FGT mide POBREZA y esta mide DESIGUALDAD,
      con el mismo insumo. Si el usuario da ingresos y pregunta por el reparto o la
      distribucion, usa esta; si pregunta por pobreza, usa la FGT. Si pide un retrato
      completo, puedes usar ambas.
    * Los microdatos los da el usuario. Si quiere el Gini YA PUBLICADO de un pais, usa
      consultar_indicador_banco_mundial ('gini'), no esta.

- calcular_fgt: calcula los indices de pobreza de Foster-Greer-Thorbecke (FGT0
  incidencia, FGT1 brecha, FGT2 severidad) a partir de MICRODATOS: una lista de
  ingresos individuales y una linea de pobreza. Acepta pesos o factores de expansion
  para encuestas.
    * Usa esta herramienta cuando el usuario TE DA los ingresos (una muestra o encuesta,
      por ejemplo ENCOVI o ENEI). Los microdatos los provee el usuario; NO vienen del
      Banco Mundial.
    * En cambio, si el usuario quiere la tasa de pobreza YA PUBLICADA de un pais, usa
      consultar_indicador_banco_mundial ('pobreza'), no la FGT.
    * Al reportar, interpreta cada indice: FGT0 dice cuantos son pobres, FGT1 que tan
      profunda es la pobreza, y FGT2 que tan severa (cuanto pesa la situacion de los
      mas pobres).

Teoria del crecimiento (explicacion conceptual, sin simular):
- Ademas de simular Solow numericamente, puedes EXPLICAR de forma conceptual otros
  modelos de crecimiento, en especial los de crecimiento endogeno: Romer (ideas e
  I+D), Lucas (capital humano) y los modelos AK.
- Se transparente sobre tu alcance: tu unica simulacion numerica es la del modelo de
  Solow. Para Romer y el crecimiento endogeno NO tienes una simulacion con datos
  reales, asi que los explicas conceptualmente y NUNCA inventas cifras ni finges
  correr un modelo.
- Cuando ayude, contrasta las ideas clave: en Solow (crecimiento exogeno) las
  politicas cambian el NIVEL de ingreso de largo plazo pero no la tasa de crecimiento;
  en los modelos endogenos las politicas de I+D, educacion e innovacion si pueden
  cambiar la TASA de crecimiento de largo plazo.
- Si el usuario pide "simular" Romer, ofrece explicarlo conceptualmente y, si quiere
  numeros, sugiere usar el simulador de Solow, que si se apoya en datos reales.

Formato de formulas matematicas (MUY IMPORTANTE):
- Cuando escribas una formula matematica, SIEMPRE usa notacion LaTeX delimitada con
  signos de dolar, para que se dibuje correctamente:
    * Formula dentro de una linea de texto: entre $ y $. Ejemplo: la brecha es $\\frac{{z - y_i}}{{z}}$.
    * Formula centrada en su propio renglon: entre $$ y $$. Ejemplo:
      $$FGT_\\alpha = \\frac{{1}}{{N}} \\sum_{{i=1}}^{{N}} w_i \\left(\\frac{{z - y_i}}{{z}}\\right)^{{\\alpha}}$$
- NUNCA escribas las formulas con corchetes [ ] ni dejes comandos como \\frac o \\sum
  sueltos sin los signos de dolar: si no van entre $ o $$, se ven como texto crudo y
  no se entienden.
- Usa subindices con _ y superindices con ^ (por ejemplo y_i, x^2) SIEMPRE dentro de $...$.

La fecha actual es {now.strftime('%d/%m/%Y')}.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "consultar_indicador_banco_mundial",
            "description": (
                "Consulta un indicador socioeconomico oficial del Banco Mundial para "
                "uno o varios paises (pobreza, gini, pib_per_capita, inversion, ahorro, "
                "crecimiento_poblacion, inflacion, desempleo, gasto_salud, gasto_educacion, "
                "esperanza_vida, remesas, etc.). Devuelve la serie historica y el valor "
                "mas reciente de cada pais, util para comparar contextos y analizar "
                "politicas publicas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "indicador": {
                        "type": "string",
                        "description": (
                            "Nombre amigable del indicador (por ejemplo 'pobreza', "
                            "'pib_per_capita', 'inversion') o su codigo oficial del Banco Mundial."
                        )
                    },
                    "pais": {
                        "type": "string",
                        "description": (
                            "Codigo ISO de 3 letras. Por defecto GTM (Guatemala). Para "
                            "comparar varios paises, sepáralos con punto y coma, "
                            "por ejemplo 'GTM;HND;SLV'."
                        )
                    },
                    "anio": {
                        "type": "string",
                        "description": (
                            "Año especifico a consultar (ej. '2022'). Opcional: si se omite "
                            "se devuelve la tendencia de los ultimos años."
                        )
                    }
                },
                "required": ["indicador"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "simular_modelo_solow",
            "description": (
                "Simula el modelo de crecimiento economico de Solow-Swan para analizar "
                "politicas de desarrollo. Calcula el estado estacionario (capital, producto "
                "y consumo por trabajador de largo plazo), la regla de oro y la trayectoria "
                "de convergencia. Util para responder 'que pasa si un pais cambia su tasa de "
                "inversion, su crecimiento poblacional o su productividad'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "tasa_ahorro": {
                        "type": "number",
                        "description": "Tasa de ahorro/inversion (s). Como porcentaje (20) o fraccion (0.20)."
                    },
                    "participacion_capital": {
                        "type": "number",
                        "description": "Participacion del capital (alpha) en la produccion. Por defecto 0.33."
                    },
                    "depreciacion": {
                        "type": "number",
                        "description": "Tasa de depreciacion del capital (delta). Por defecto 0.05 (5%)."
                    },
                    "crecimiento_poblacion": {
                        "type": "number",
                        "description": "Crecimiento poblacional (n). Como porcentaje (1.5) o fraccion (0.015)."
                    },
                    "crecimiento_tecnologico": {
                        "type": "number",
                        "description": "Crecimiento de la productividad (g). Opcional, por defecto 0."
                    },
                    "productividad": {
                        "type": "number",
                        "description": "Nivel de productividad (A). Opcional, por defecto 1."
                    },
                    "anios": {
                        "type": "number",
                        "description": "Cantidad de años a simular en la trayectoria. Opcional, por defecto 30."
                    }
                },
                "required": ["tasa_ahorro"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_idh_pnud",
            "description": (
                "Consulta el Indice de Desarrollo Humano (IDH) y otros indices compuestos "
                "del PNUD (IHDI, GII, GDI, MPI, PHDI) desde la fuente oficial (hdrdata.org). "
                "Requiere una API key gratuita configurada como HDR_API_KEY."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "pais": {
                        "type": "string",
                        "description": "Codigo ISO de 3 letras. Por defecto GTM. Para varios, separalos con ';' (ej. 'GTM;HND')."
                    },
                    "indicador": {
                        "type": "string",
                        "description": "Indice a consultar: 'idh' (o hdi), 'ihdi', 'gii', 'gdi', 'mpi', 'phdi'. Por defecto 'hdi'."
                    },
                    "anio": {
                        "type": "string",
                        "description": "Año especifico (ej. '2022'). Opcional."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_desigualdad",
            "description": (
                "Calcula medidas de desigualdad a partir de una lista de ingresos individuales "
                "(microdatos): coeficiente de Gini, ratio de Palma, participacion del ingreso por "
                "quintiles, curva de Lorenz por deciles e indice de Theil. Opcionalmente acepta "
                "pesos o factores de expansion. Es el complemento de calcular_fgt (pobreza)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ingresos": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Lista de ingresos (o consumos) individuales de la muestra."
                    },
                    "pesos": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Pesos o factores de expansion, del mismo tamaño que 'ingresos' (opcional)."
                    }
                },
                "required": ["ingresos"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calcular_fgt",
            "description": (
                "Calcula los indices de pobreza de Foster-Greer-Thorbecke (FGT0 incidencia, "
                "FGT1 brecha, FGT2 severidad) a partir de una lista de ingresos individuales "
                "(microdatos) y una linea de pobreza. Opcionalmente acepta pesos o factores de "
                "expansion. Usar cuando el usuario provee los ingresos, no para tasas ya publicadas."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ingresos": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Lista de ingresos (o consumos) individuales de la muestra."
                    },
                    "linea_pobreza": {
                        "type": "number",
                        "description": "Linea de pobreza (z), en las mismas unidades que los ingresos."
                    },
                    "alpha": {
                        "type": "number",
                        "description": "Parametro de aversion a la pobreza adicional (opcional). Ademas siempre se devuelven 0, 1 y 2."
                    },
                    "pesos": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "Pesos o factores de expansion, del mismo tamaño que 'ingresos' (opcional)."
                    }
                },
                "required": ["ingresos", "linea_pobreza"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generar_grafico",
            "description": (
                "Prepara un grafico (de linea o de barras) para mostrarlo en la interfaz. "
                "Usalo cuando el usuario pida graficar, visualizar o ver una tendencia. "
                "Debes pasarle los datos reales que quieres graficar; normalmente los obtienes "
                "primero con otra herramienta (por ejemplo el Banco Mundial o el IDH) y luego "
                "pasas esos numeros aqui."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "etiquetas": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Etiquetas del eje X (por ejemplo años o nombres de países)."
                    },
                    "series": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "nombre": {"type": "string", "description": "Nombre de la serie (aparece en la leyenda)."},
                                "valores": {"type": "array", "items": {"type": "number"}, "description": "Un valor por cada etiqueta."}
                            },
                            "required": ["nombre", "valores"]
                        },
                        "description": "Una o varias series de datos. Cada serie tiene mismo número de valores que etiquetas."
                    },
                    "tipo": {
                        "type": "string",
                        "description": "'linea' (tendencias en el tiempo) o 'barra' (comparaciones). Por defecto 'linea'."
                    },
                    "titulo": {
                        "type": "string",
                        "description": "Título del gráfico (opcional)."
                    }
                },
                "required": ["etiquetas", "series"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_tipo_cambio_api",
            "description": (
                "Llama a esta funcion para consultar el tipo de cambio de una moneda "
                "respecto al quetzal de Guatemala. "
                "Se debe enviar como argumento el codigo de la moneda que se desea consultar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "moneda": {
                        "type": "string",
                        "description": "Codigo de la moneda que se desea consultar, por ejemplo USD"
                    }
                },
                "required": ["moneda"]
            }
        }
    }
]


def process_response(client:Groq, memory_messages: list[dict], user_text:str):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(memory_messages)
    messages.append({"role": "user", "content": user_text})

    graficos = []  # aqui se juntan las "recetas" de grafico generadas en este turno

    while True:
        resp = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            tools=TOOLS
        )
        msg = resp.choices[0].message

        # Si no hay llamados a herramientas, entonces ya regresamos la respuesta
        if not getattr(msg, "tool_calls", None):
            return msg.content or "", graficos

        messages.append({
            "role": "assistant",
            "content": msg.content or "",
            "tool_calls": [tc.model_dump() for tc in msg.tool_calls]
        })

        for tool_call in msg.tool_calls:
            name = tool_call.function.name
            args = json.loads(tool_call.function.arguments or "{}")

            if name == "consultar_indicador_banco_mundial":
                tools = IntermediateTools()
                result = tools.consultar_indicador_banco_mundial(
                    indicador=args.get("indicador", ""),
                    pais=args.get("pais", "GTM"),
                    anio=args.get("anio")
                )
            elif name == "simular_modelo_solow":
                tools = IntermediateTools()
                result = tools.simular_modelo_solow(
                    tasa_ahorro=args.get("tasa_ahorro"),
                    participacion_capital=args.get("participacion_capital", 0.33),
                    depreciacion=args.get("depreciacion", 0.05),
                    crecimiento_poblacion=args.get("crecimiento_poblacion", 0.0),
                    crecimiento_tecnologico=args.get("crecimiento_tecnologico", 0.0),
                    productividad=args.get("productividad", 1.0),
                    anios=args.get("anios", 30)
                )
            elif name == "consultar_idh_pnud":
                tools = IntermediateTools()
                result = tools.consultar_idh_pnud(
                    pais=args.get("pais", "GTM"),
                    indicador=args.get("indicador", "hdi"),
                    anio=args.get("anio")
                )
            elif name == "calcular_desigualdad":
                tools = IntermediateTools()
                result = tools.calcular_desigualdad(
                    ingresos=args.get("ingresos"),
                    pesos=args.get("pesos")
                )
            elif name == "calcular_fgt":
                tools = IntermediateTools()
                result = tools.calcular_fgt(
                    ingresos=args.get("ingresos"),
                    linea_pobreza=args.get("linea_pobreza"),
                    alpha=args.get("alpha"),
                    pesos=args.get("pesos")
                )
            elif name == "consultar_tipo_cambio_api":
                tools = IntermediateTools()
                result = tools.consultar_tipo_cambio_api(
                    moneda=args["moneda"]
                )
            elif name == "generar_grafico":
                tools = IntermediateTools()
                result = tools.generar_grafico(
                    etiquetas=args.get("etiquetas"),
                    series=args.get("series"),
                    tipo=args.get("tipo", "linea"),
                    titulo=args.get("titulo", "")
                )
            else:
                print(f"Se intentó llamar a una herramienta desconocida {name}")
                result = {"error": f"Herramienta desconocida: {name}"}

            # Si el resultado es una "receta" de grafico, la guardamos para la interfaz
            if isinstance(result, dict) and result.get("_tipo_resultado") == "grafico":
                graficos.append(result)

            # Agregar a los mensajes el resultado del llamado de la herramienta
            # Esto lo recibirá el modelo al continuar la iteración
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result, ensure_ascii=False)
            })

if __name__ == "__main__":
    print("Lillié - Asistente de Políticas Públicas y Desarrollo Económico")

    while True:
        user_text = input("Tú: ").strip()
        if not user_text:
            continue
        if user_text.lower() in ("exit","salir"):
            print("Hasta luego!")
            break
        assistant_text, graficos = process_response(client, memory.messages(), user_text)
        print(f"Agente: {assistant_text}")
        if graficos:
            print(f"[Se generaron {len(graficos)} gráfico(s); se ven en la versión web (Streamlit).]")
        # Actualizar la memoria #
        memory.add("user",user_text)
        memory.add("assistant", assistant_text)
