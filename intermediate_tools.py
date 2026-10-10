######################## Agente Basico De IA ## Herramientas        ########################
# Importacion para el manejo de sistema
import os
import requests

# Importaciones agregadas para la herramienta del Banco Mundial
import unicodedata
from datetime import datetime

# Importacion para calculos de desigualdad (logaritmo del indice de Theil)
import math


class IntermediateTools:

    def __init__(self):
        # ------------------------------------------------------------------ #
        # Catalogo de indicadores del Banco Mundial (World Development
        # Indicators). La llave es un nombre "amigable" en espanol; el valor
        # es el codigo oficial. Para agregar mas, solo se agrega una linea.
        # ------------------------------------------------------------------ #
        self.INDICADORES = {
            # --- Crecimiento y desarrollo ---
            "pib_per_capita": "NY.GDP.PCAP.CD",          # PIB per capita (USD corrientes)
            "pib_per_capita_ppa": "NY.GDP.PCAP.PP.CD",   # PIB per capita (USD PPA)
            "crecimiento_pib": "NY.GDP.MKTP.KD.ZG",      # Crecimiento anual del PIB (%)
            "crecimiento_pib_per_capita": "NY.GDP.PCAP.KD.ZG",  # Crecimiento PIB per capita (%)
            "inversion": "NE.GDI.TOTL.ZS",               # Formacion bruta de capital (% del PIB)
            "ahorro": "NY.GNS.ICTR.ZS",                  # Ahorro bruto (% del PIB)
            "crecimiento_poblacion": "SP.POP.GROW",      # Crecimiento poblacional (% anual)
            "poblacion": "SP.POP.TOTL",                  # Poblacion total 

            # --- Pobreza y desigualdad ---
            "pobreza": "SI.POV.NAHC",                    # Pobreza segun linea nacional (%)
            "pobreza_extrema": "SI.POV.DDAY",            # Pobreza extrema, 2.15 USD/dia (%)
            "gini": "SI.POV.GINI",                       # Indice de Gini 

            # --- Precios y empleo ---
            "inflacion": "FP.CPI.TOTL.ZG",               # Inflacion, precios al consumidor (% anual)
            "desempleo": "SL.UEM.TOTL.ZS",               # Desempleo (% de la fuerza laboral) 

            # --- Capital humano ---
            "esperanza_vida": "SP.DYN.LE00.IN",          # Esperanza de vida al nacer (anios)
            "mortalidad_infantil": "SP.DYN.IMRT.IN",     # Mortalidad infantil (por 1000)
            "alfabetizacion": "SE.ADT.LITR.ZS",          # Tasa de alfabetizacion adultos (%)
            "gasto_educacion": "SE.XPD.TOTL.GD.ZS",      # Gasto publico en educacion (% del PIB)
            "gasto_salud": "SH.XPD.CHEX.GD.ZS",          # Gasto en salud (% del PIB) 

            # --- Fiscal y otros ---
            "recaudacion_tributaria": "GC.TAX.TOTL.GD.ZS",  # Ingresos tributarios (% del PIB)
            "remesas": "BX.TRF.PWKR.CD.DT",              # Remesas personales recibidas (USD)
            "acceso_electricidad": "EG.ELC.ACCS.ZS",     # Acceso a electricidad (% poblacion)
        }

        # ------------------------------------------------------------------ #
        # Indices compuestos del PNUD (Human Development Report Office).
        # Nombre amigable -> codigo del indicador en la API de hdrdata.org.
        # Nota: verifica los codigos exactos en el endpoint de metadatos:
        # https://hdrdata.org/api/Metadata/Indicators?apikey=TU_LLAVE
        # ------------------------------------------------------------------ #
        self.INDICES_PNUD = {
            "idh": "hdi", "hdi": "hdi",
            "idh_desigualdad": "ihdi", "ihdi": "ihdi",
            "desigualdad_genero": "gii", "gii": "gii",
            "desarrollo_genero": "gdi", "gdi": "gdi",
            "pobreza_multidimensional": "mpi", "mpi": "mpi",
            "idh_planetario": "phdi", "phdi": "phdi",
        }

    # ---------------------------------------------------------------------- #
    # Utilidades internas para el Banco Mundial
    # ---------------------------------------------------------------------- #
    def _normalizar(self, texto: str) -> str:
        """Minusculas, sin acentos y con guiones bajos, para comparar sin errores."""
        texto = texto.strip().lower().replace(" ", "_")
        texto = unicodedata.normalize("NFKD", texto)
        return "".join(c for c in texto if not unicodedata.combining(c))

    def _resolver_indicador(self, indicador: str):
        """Convierte un nombre amigable o un codigo oficial en el codigo del Banco Mundial."""
        clave = self._normalizar(indicador)
        if clave in self.INDICADORES:
            return self.INDICADORES[clave]
        # Si ya viene un codigo oficial (contiene punto), se acepta tal cual
        if "." in indicador:
            return indicador.upper()
        return None

    # Herramienta para generar un grafico listo para Streamlit
    def generar_grafico(self, etiquetas, series, tipo="linea", titulo=""):
        print(f"Herramienta generar_grafico llamada con tipo: {tipo}, titulo: {titulo}")

        if not isinstance(etiquetas, list) or not isinstance(series, list) or not series:
            return {"error": "Se requieren 'etiquetas' y 'series' validas para generar el grafico."}

        try:
            datos_validos = []
            for s in series:
                nombre = s.get("nombre")
                valores = s.get("valores")
                if not nombre or not isinstance(valores, list):
                    continue
                if len(valores) != len(etiquetas):
                    return {"error": "Cada serie debe tener el mismo número de valores que etiquetas."}
                datos_validos.append({"nombre": nombre, "valores": [float(v) for v in valores]})

            if not datos_validos:
                return {"error": "No se recibieron series validas para graficar."}

            return {
                "_tipo_resultado": "grafico",
                "tipo": tipo if tipo in ("barra", "linea") else "linea",
                "titulo": titulo,
                "etiquetas": [str(x) for x in etiquetas],
                "series": datos_validos,
            }
        except Exception as e:
            return {"error": f"No se pudo preparar el gráfico: {e}"}

    # Herramienta para consultar el tipo de cambio (original del licenciado)
    def consultar_tipo_cambio_api(self, moneda: str):
        print(f"Herramienta consultar_tipo_cambio_api llamada con moneda: {moneda}")

        if not moneda:
            return "Error: Se requiere el codigo de la moneda para obtener el tipo de cambio."

        # URL del servicio para obtener el tipo de cambio segun la moneda:
        url = (
            f"https://open.er-api.com/v6/latest/{moneda.upper()}"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Lanza una excepcion si la respuesta no es exitosa
            return response.json()  # Intentar decodificar la respuesta como JSON
        except Exception as e:
            print(f"Error al obtener_tipo_cambio_api: {moneda}. Error: {e}")
            return f"ERROR: No se pudo obtener el tipo de cambio para la moneda: {moneda}"

    # Herramienta para consultar indicadores del Banco Mundial (uno o varios paises)
    def consultar_indicador_banco_mundial(self, indicador: str, pais: str = "GTM", anio: str = None):
        print(f"Herramienta consultar_indicador_banco_mundial llamada con "
              f"indicador: {indicador}, pais: {pais}, anio: {anio}")

        if not indicador:
            return {"error": "Se requiere el nombre o codigo del indicador."}

        # 1) Resolver el indicador (nombre amigable -> codigo oficial)
        codigo = self._resolver_indicador(indicador)
        if codigo is None:
            return {
                "error": f"No reconozco el indicador '{indicador}'.",
                "indicadores_validos": list(self.INDICADORES.keys()),
            }

        # 2) Los paises pueden venir separados por ';' (ej. 'GTM;HND;SLV')
        pais = (pais or "GTM").upper().replace(",", ";").replace(" ", "")

        # 3) Construir la peticion al Banco Mundial
        url = f"https://api.worldbank.org/v2/country/{pais}/indicator/{codigo}"
        params = {"format": "json", "per_page": 500}
        if anio:
            params["date"] = str(anio)
        else:
            actual = datetime.now().year
            params["date"] = f"{actual - 15}:{actual}"  # ultimos 15 anios para ver tendencia

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            body = response.json()
        except Exception as e:
            print(f"Error en consultar_indicador_banco_mundial: {e}")
            return {"error": f"No se pudo consultar el Banco Mundial: {e}"}

        # 4) El Banco Mundial reporta sus errores como HTTP 200 con un 'message'
        if isinstance(body, list) and body and isinstance(body[0], dict) and body[0].get("message"):
            return {"error": body[0]["message"][0].get("value", "Error del Banco Mundial")}

        if not isinstance(body, list) or len(body) < 2 or not body[1]:
            return {"error": f"No hay datos para '{indicador}' en {pais}"
                             + (f" para {anio}." if anio else ".")}

        datos = body[1]
        nombre_indicador = datos[0]["indicator"]["value"]

        # 5) Agrupar los resultados por pais (para comparar contextos)
        paises = {}
        for d in datos:
            if d["value"] is None:
                continue
            nombre_pais = d["country"]["value"]
            paises.setdefault(nombre_pais, []).append(
                {"anio": d["date"], "valor": d["value"]}
            )

        if not paises:
            return {"error": f"El indicador '{nombre_indicador}' no tiene valores "
                             f"reportados en el periodo consultado."}

        # 6) Ordenar cada serie y marcar el valor mas reciente
        resultado_paises = {}
        for nombre_pais, serie in paises.items():
            serie.sort(key=lambda x: x["anio"])
            resultado_paises[nombre_pais] = {
                "valor_mas_reciente": serie[-1],
                "serie": serie,
            }

        return {
            "indicador": nombre_indicador,
            "codigo": codigo,
            "fuente": "Banco Mundial - World Development Indicators",
            "paises": resultado_paises,
        }

    # ---------------------------------------------------------------------- #
    # Utilidad: aceptar valores como porcentaje (20) o como fraccion (0.20)
    # ---------------------------------------------------------------------- #
    def _a_fraccion(self, x, defecto=0.0):
        try:
            v = float(x)
        except (TypeError, ValueError):
            return defecto
        # Si viene como porcentaje (1 o mayor), se convierte a fraccion.
        # Los parametros del modelo (s, alpha, delta, n, g) siempre son < 1 como
        # fraccion, asi que cualquier valor >= 1 se interpreta como porcentaje.
        return v / 100 if v >= 1 else v

    # Herramienta: simulacion del modelo de crecimiento de Solow
    def simular_modelo_solow(self, tasa_ahorro, participacion_capital=0.33,
                             depreciacion=0.05, crecimiento_poblacion=0.0,
                             crecimiento_tecnologico=0.0, productividad=1.0,
                             capital_inicial=None, anios=30):
        print(f"Herramienta simular_modelo_solow llamada con tasa_ahorro: {tasa_ahorro}, "
              f"alpha: {participacion_capital}, delta: {depreciacion}, "
              f"n: {crecimiento_poblacion}, g: {crecimiento_tecnologico}")

        # 1) Normalizar entradas (aceptan porcentaje o fraccion)
        s = self._a_fraccion(tasa_ahorro)
        alpha = self._a_fraccion(participacion_capital, 0.33)
        delta = self._a_fraccion(depreciacion, 0.05)
        n = self._a_fraccion(crecimiento_poblacion, 0.0)
        g = self._a_fraccion(crecimiento_tecnologico, 0.0)
        try:
            A = float(productividad)
            T = int(anios)
        except (TypeError, ValueError):
            return {"error": "productividad y anios deben ser numeros."}

        # 2) Validaciones economicas
        if not (0 < s < 1):
            return {"error": "La tasa de ahorro debe estar entre 0 y 1 (o 0 y 100%)."}
        if not (0 < alpha < 1):
            return {"error": "La participacion del capital (alpha) debe estar entre 0 y 1."}
        denom = n + g + delta
        if denom <= 0:
            return {"error": "La suma (n + g + depreciacion) debe ser mayor a 0."}
        if A <= 0:
            return {"error": "La productividad (A) debe ser positiva."}

        # 3) Estado estacionario (formulas del modelo de Solow con Cobb-Douglas)
        #    k* = ( s*A / (n+g+delta) ) ^ ( 1 / (1-alpha) )
        exp = 1.0 / (1.0 - alpha)
        k_ss = (s * A / denom) ** exp
        y_ss = A * (k_ss ** alpha)
        c_ss = (1 - s) * y_ss

        # 4) Regla de oro: la tasa de ahorro que maximiza el consumo (s = alpha)
        s_oro = alpha
        k_oro = (s_oro * A / denom) ** exp
        y_oro = A * (k_oro ** alpha)
        c_oro = (1 - s_oro) * y_oro

        # 5) Trayectoria: convergencia desde el capital inicial hacia el estado estacionario
        try:
            k0 = float(capital_inicial) if capital_inicial is not None else k_ss * 0.25
        except (TypeError, ValueError):
            k0 = k_ss * 0.25
        k = k0

        trayectoria = []
        anio_95 = None
        for t in range(0, T + 1):
            y = A * (k ** alpha)
            # Guardamos algunos puntos (cada 5 anios + el ultimo) para no saturar
            if t % 5 == 0 or t == T:
                trayectoria.append({
                    "anio": t,
                    "capital_k": round(k, 3),
                    "producto_y": round(y, 3),
                    "consumo_c": round((1 - s) * y, 3),
                })
            if anio_95 is None and y >= 0.95 * y_ss:
                anio_95 = t
            # Ecuacion de acumulacion: k_{t+1} = k_t + s*A*k^alpha - (n+g+delta)*k
            k = k + s * A * (k ** alpha) - denom * k
            if k < 0:
                k = 0

        # 6) Nota interpretativa segun haya o no progreso tecnologico
        if g > 0:
            nota = ("Con progreso tecnologico (g>0), los valores son POR TRABAJADOR "
                    "EFECTIVO; el producto por trabajador crece a la tasa g en el largo plazo.")
        else:
            nota = "Sin progreso tecnologico: los valores son por trabajador y constantes en el largo plazo."

        return {
            "modelo": "Solow-Swan (Cobb-Douglas)",
            "parametros_usados": {
                "tasa_ahorro_s": round(s, 4),
                "participacion_capital_alpha": round(alpha, 4),
                "depreciacion_delta": round(delta, 4),
                "crecimiento_poblacion_n": round(n, 4),
                "crecimiento_tecnologico_g": round(g, 4),
                "productividad_A": A,
            },
            "estado_estacionario": {
                "capital_por_trabajador_k": round(k_ss, 3),
                "producto_por_trabajador_y": round(y_ss, 3),
                "consumo_por_trabajador_c": round(c_ss, 3),
            },
            "regla_de_oro": {
                "tasa_ahorro_optima_s": round(s_oro, 4),
                "consumo_maximo_c": round(c_oro, 3),
                "nota": "Es la tasa de ahorro que maximiza el consumo de largo plazo.",
            },
            "convergencia": {
                "capital_inicial_k0": round(k0, 3),
                "anios_simulados": T,
                "anios_para_alcanzar_95pct_del_producto": anio_95,
            },
            "trayectoria": trayectoria,
            "nota_interpretativa": nota,
        }

    # Herramienta: indices de pobreza de Foster-Greer-Thorbecke (FGT)
    def calcular_fgt(self, ingresos, linea_pobreza, alpha=None, pesos=None):
        print(f"Herramienta calcular_fgt llamada con {len(ingresos) if isinstance(ingresos, list) else '?'} "
              f"ingresos, linea_pobreza: {linea_pobreza}, alpha: {alpha}")

        # 1) Validar la linea de pobreza
        try:
            z = float(linea_pobreza)
        except (TypeError, ValueError):
            return {"error": "La linea de pobreza debe ser un numero."}
        if z <= 0:
            return {"error": "La linea de pobreza debe ser mayor a 0."}

        # 2) Validar y convertir los ingresos
        if not isinstance(ingresos, list) or len(ingresos) == 0:
            return {"error": "Se requiere una lista de ingresos (microdatos)."}
        try:
            y = [float(v) for v in ingresos]
        except (TypeError, ValueError):
            return {"error": "Todos los ingresos deben ser numeros."}
        n = len(y)

        # 3) Pesos / factores de expansion (opcional). Si no hay, todos valen 1.
        if pesos is not None:
            if not isinstance(pesos, list) or len(pesos) != n:
                return {"error": "Los pesos deben ser una lista del mismo tamaño que los ingresos."}
            try:
                w = [float(p) for p in pesos]
            except (TypeError, ValueError):
                return {"error": "Todos los pesos deben ser numeros."}
        else:
            w = [1.0] * n
        W = sum(w)
        if W <= 0:
            return {"error": "La suma de los pesos debe ser mayor a 0."}

        # 4) Funcion FGT para un alpha dado:  (1/W) * sum( w_i * ((z - y_i)/z)^alpha )
        #    solo sobre los pobres (y_i < z). La brecha normalizada es g_i = (z - y_i)/z.
        def fgt(a):
            total = 0.0
            for yi, wi in zip(y, w):
                if yi < z:
                    g = (z - yi) / z
                    total += wi * (g ** a)
            return total / W

        fgt0 = fgt(0)  # incidencia (headcount ratio)
        fgt1 = fgt(1)  # brecha de pobreza
        fgt2 = fgt(2)  # severidad (brecha al cuadrado)

        # 5) Conteos de apoyo
        pobres_ponderados = sum(wi for yi, wi in zip(y, w) if yi < z)

        indices = {
            "FGT0_incidencia": round(fgt0, 4),
            "FGT1_brecha": round(fgt1, 4),
            "FGT2_severidad": round(fgt2, 4),
        }

        # 6) Alpha personalizado opcional
        if alpha is not None:
            try:
                a = float(alpha)
                if a < 0:
                    return {"error": "El parametro alpha debe ser mayor o igual a 0."}
                indices[f"FGT_alpha_{a}"] = round(fgt(a), 4)
            except (TypeError, ValueError):
                return {"error": "El parametro alpha debe ser un numero."}

        return {
            "metodo": "Indices de Foster-Greer-Thorbecke (FGT)",
            "linea_pobreza": z,
            "n_observaciones": n,
            "poblacion_considerada": round(W, 2),
            "personas_pobres": round(pobres_ponderados, 2),
            "ponderado": pesos is not None,
            "indices_fgt": indices,
            "interpretacion": {
                "FGT0": "Incidencia: proporcion de la poblacion bajo la linea de pobreza.",
                "FGT1": "Brecha: profundidad promedio de la pobreza (que tan lejos estan los pobres de la linea).",
                "FGT2": "Severidad: pondera mas a los mas pobres; sensible a la desigualdad entre pobres.",
            },
        }

    # Herramienta: indices de desarrollo humano del PNUD (IDH y familia)
    def consultar_idh_pnud(self, pais="GTM", anio=None, indicador="hdi"):
        print(f"Herramienta consultar_idh_pnud llamada con pais: {pais}, "
              f"anio: {anio}, indicador: {indicador}")

        # 1) La API del PNUD requiere una llave (registro gratuito en hdrdata.org)
        api_key = os.environ.get("HDR_API_KEY")
        if not api_key:
            return {
                "error": "Falta la API key del PNUD.",
                "solucion": "Registrate gratis en https://hdrdata.org, revisa tu correo "
                            "y agrega la linea HDR_API_KEY=tu_llave a tu archivo .env.",
            }

        # 2) Resolver el indicador (nombre amigable -> codigo del PNUD)
        codigo = self.INDICES_PNUD.get(self._normalizar(indicador), indicador)

        # 3) Paises: uno o varios separados por coma
        pais = (pais or "GTM").upper().replace(";", ",").replace(" ", "")

        # 4) Construir y enviar la peticion
        url = "https://hdrdata.org/api/CompositeIndices/query"
        params = {"apikey": api_key, "countryOrAggregation": pais, "indicator": codigo}
        if anio:
            params["year"] = str(anio)

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            body = response.json()
        except Exception as e:
            print(f"Error en consultar_idh_pnud: {e}")
            return {"error": f"No se pudo consultar la API del PNUD: {e}"}

        # 5) La API suele devolver una lista de registros; a veces viene envuelta
        if isinstance(body, dict):
            listas = [v for v in body.values() if isinstance(v, list)]
            datos = listas[0] if listas else [body]
        elif isinstance(body, list):
            datos = body
        else:
            datos = []

        if not datos:
            return {
                "error": "La API del PNUD no devolvio datos para esa consulta.",
                "sugerencia": "Verifica el codigo del indicador y el pais. Puedes listar "
                              "los indicadores validos en el endpoint de metadatos.",
            }

        # 6) Los campos vienen directo de la API; se los pasamos limpios al modelo
        cap = 300
        return {
            "fuente": "PNUD - Human Development Report Office (hdrdata.org)",
            "consulta": {"pais": pais, "indicador": codigo, "anio": anio},
            "n_registros": len(datos),
            "datos": datos[:cap],
            "nota": "Cada registro trae pais, año, valor e indicador segun la API del PNUD.",
        }

    # Herramienta: medidas de desigualdad a partir de microdatos (Gini, Palma, Theil)
    def calcular_desigualdad(self, ingresos, pesos=None):
        print(f"Herramienta calcular_desigualdad llamada con "
              f"{len(ingresos) if isinstance(ingresos, list) else '?'} ingresos")

        # 1) Validar ingresos
        if not isinstance(ingresos, list) or len(ingresos) == 0:
            return {"error": "Se requiere una lista de ingresos (microdatos)."}
        try:
            y = [float(v) for v in ingresos]
        except (TypeError, ValueError):
            return {"error": "Todos los ingresos deben ser numeros."}
        n = len(y)
        if any(v < 0 for v in y):
            return {"error": "Los ingresos no pueden ser negativos para medir desigualdad."}

        # 2) Pesos / factores de expansion (opcional)
        if pesos is not None:
            if not isinstance(pesos, list) or len(pesos) != n:
                return {"error": "Los pesos deben ser una lista del mismo tamaño que los ingresos."}
            try:
                w = [float(p) for p in pesos]
            except (TypeError, ValueError):
                return {"error": "Todos los pesos deben ser numeros."}
        else:
            w = [1.0] * n

        W = sum(w)
        if W <= 0:
            return {"error": "La suma de los pesos debe ser mayor a 0."}
        Y = sum(wi * yi for yi, wi in zip(y, w))
        if Y <= 0:
            return {"error": "El ingreso total debe ser mayor a 0."}
        media = Y / W

        # 3) Ordenar de menor a mayor y construir la curva de Lorenz
        pares = sorted(zip(y, w), key=lambda t: t[0])
        p = [0.0]  # fraccion acumulada de poblacion
        L = [0.0]  # fraccion acumulada de ingreso
        cw = cy = 0.0
        for yi, wi in pares:
            cw += wi
            cy += wi * yi
            p.append(cw / W)
            L.append(cy / Y)

        # 4) Gini = 1 - 2 * (area bajo la curva de Lorenz), por trapecios
        B = 0.0
        for i in range(1, len(p)):
            B += (p[i] - p[i - 1]) * (L[i] + L[i - 1]) / 2
        gini = 1 - 2 * B

        # 5) Interpolar la Lorenz en una fraccion de poblacion dada
        def lorenz_at(pp):
            for i in range(1, len(p)):
                if p[i] >= pp:
                    if p[i] == p[i - 1]:
                        return L[i]
                    frac = (pp - p[i - 1]) / (p[i] - p[i - 1])
                    return L[i - 1] + frac * (L[i] - L[i - 1])
            return 1.0

        # 6) Ratio de Palma = ingreso del 10% mas rico / ingreso del 40% mas pobre
        bottom40 = lorenz_at(0.4)
        top10 = 1 - lorenz_at(0.9)
        palma = (top10 / bottom40) if bottom40 > 0 else None

        # 7) Participacion del ingreso por quintiles (20% cada uno)
        cortes = [0.2, 0.4, 0.6, 0.8, 1.0]
        Lcuts = [lorenz_at(c) for c in cortes]
        quintiles = []
        prev = 0.0
        for lc in Lcuts:
            quintiles.append(round((lc - prev) * 100, 2))
            prev = lc

        # 8) Curva de Lorenz resumida por deciles (share acumulado de ingreso)
        deciles = [round(lorenz_at(k / 10) * 100, 2) for k in range(1, 11)]

        # 9) Indice de Theil (requiere ingresos estrictamente positivos)
        theil = None
        if all(v > 0 for v in y):
            s = 0.0
            for yi, wi in zip(y, w):
                r = yi / media
                s += (wi / W) * r * math.log(r)
            theil = round(s, 4)

        return {
            "metodo": "Medidas de desigualdad (a partir de microdatos)",
            "n_observaciones": n,
            "poblacion_considerada": round(W, 2),
            "ingreso_promedio": round(media, 2),
            "ponderado": pesos is not None,
            "gini": round(gini, 4),
            "palma": {
                "ratio": round(palma, 4) if palma is not None else None,
                "share_top10": round(top10, 4),
                "share_bottom40": round(bottom40, 4),
            },
            "participacion_por_quintil_pct": quintiles,
            "curva_lorenz_deciles_pct": deciles,
            "theil": theil,
            "interpretacion": {
                "gini": "0 = igualdad perfecta, 1 = desigualdad maxima.",
                "palma": "Ingreso del 10% mas rico dividido entre el del 40% mas pobre.",
                "quintiles": "% del ingreso total que recibe cada 20% de la poblacion, del mas pobre al mas rico.",
                "theil": "0 = igualdad; a mayor valor, mayor desigualdad (sensible a la parte alta).",
            },
        }
