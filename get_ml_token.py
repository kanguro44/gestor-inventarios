import requests
import json
import os
import sys

def get_access_token(app_id, client_secret):
    """
    Obtiene un token de acceso de Mercado Libre usando las credenciales de la aplicación.
    """
    url = "https://api.mercadolibre.com/oauth/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": app_id,
        "client_secret": client_secret
    }
    
    try:
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error al obtener el token: {str(e)}")
        if hasattr(e, 'response') and e.response:
            print(f"Respuesta del servidor: {e.response.text}")
        return None

def main():
    if len(sys.argv) != 3:
        print("Uso: python get_ml_token.py <app_id> <client_secret>")
        print("Ejemplo: python get_ml_token.py 7372371327572562 qGsMsOj13Wqe21tEojMBHcY9aGwYaIJ3")
        return
    
    app_id = sys.argv[1]
    client_secret = sys.argv[2]
    
    print(f"Obteniendo token para App ID: {app_id}")
    token_info = get_access_token(app_id, client_secret)
    
    if token_info:
        print("\n=== Token obtenido con éxito ===")
        print(f"Access Token: {token_info.get('access_token')}")
        print(f"Token Type: {token_info.get('token_type')}")
        print(f"Expires In: {token_info.get('expires_in')} segundos")
        print(f"Scope: {token_info.get('scope')}")
        print(f"User ID: {token_info.get('user_id')}")
        print(f"Refresh Token: {token_info.get('refresh_token', 'No disponible')}")
        
        # Guardar en un archivo para referencia
        with open("ml_token_info.json", "w") as f:
            json.dump(token_info, f, indent=2)
        print("\nLa información del token se ha guardado en ml_token_info.json")
        
        print("\n=== Instrucciones ===")
        print("1. Copia el Access Token")
        print("2. Ve a la configuración de tu aplicación en Render")
        print("3. Actualiza la variable de entorno MERCADOLIBRE_ACCESS_TOKEN con este nuevo token")
        print("4. Guarda los cambios y espera a que Render redespliegue la aplicación")
    else:
        print("No se pudo obtener el token. Verifica tus credenciales.")

if __name__ == "__main__":
    main()
