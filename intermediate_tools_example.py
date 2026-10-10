import os
import requests

class IntermediateTools:

    def __init__(self):
        pass

    def obtener_clima_api(self, lat:str, long:str):
        print(f"Herramienta obtener_clima_api llamada con lat: {lat}, long: {long}")

        if not lat or not long:
            return "Error: Se requiere latitud y longitud para obtener el clima."

        # URL del servicio para obtener el clima según latitud y longitud:
        url = (
            f"https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={long}&current_weather=true"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa
            return response.json()  # Intentar decodificar la respuesta como JSON
        except Exception as e:
            print(f"Error al obtener_clima_api: {lat}, {long}. Error: {e}")
            return f"ERROR: No se pudo obtener el clima para lat: {lat}, long: {long}" 

    def obtener_lat_long(self, ciudad:str):
        print(f"Herramienta obtener_lat_lon llamada con ciudad: {ciudad}")

        if not ciudad:
            return "Error: Se requiere el nombre de la ciudad para obtener la latitud y longitud."

        #URL del servicio para obtener la latitud y longitud según el nombre de la ciudad:

        url = (
            f"https://geocoding-api.open-meteo.com/v1/search"
            f"?name={ciudad}&count=1&language=es&format=json"
        )

        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Lanza una excepción si la respuesta no es exitosa
            return response.json()  # Intentar decodificar la respuesta como JSON
        except Exception as e:
            print(f"Error al obtener_lat_lon: {ciudad}. Error: {e}")
            return f"ERROR: No se pudo obtener la latitud y longitud para ciudad: {ciudad}" 
