#######################
# Agente Basico De IA #
# Herramientas        #
#######################

# Importacion para el manejo de sistema
import os

class BasicTools:

    def __init__(self):
        pass

    # Herramienta para consultar el tipo de cambio
    def consultar_tipo_cambio(self, moneda: str = ""):
        print(f"Herramienta consultar_tipo_cambio llamada con {moneda}")

        if moneda.upper() == "USD":
            return "El tipo de cambio es 7.80 quetzales por dólar"
        else:
            return f"No tengo información para la moneda {moneda}"