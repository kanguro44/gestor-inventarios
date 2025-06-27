import streamlit as st
import requests
import json
import os
import pandas as pd
import io
import numpy as np
import time
from datetime import datetime
import hashlib
import urllib.parse
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import threading
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("inventarios-app")

st.set_page_config(layout="wide", page_title="Gestión de Inventario ESPAITEC")

# ---- CUSTOM STYLES ----
st.markdown("""
    <style>
    .main .block-container {padding: 0;}
    div[data-testid="stHeader"], div[data-testid="stFooter"] {display: none;}
    .user-info {text-align: right;}
    .sidebar-title {color:#F39200;font-size:1.3em;font-weight:bold;}
    .sidebar-logo {margin:0 0 1.5em 0;display:block;}
    </style>
""", unsafe_allow_html=True)

# ---- SESSION & LOGIN ----
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_email" not in st.session_state:
    st.session_state.user_email = ""
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "state" not in st.session_state:
    st.session_state.state = hashlib.sha256(os.urandom(1024)).hexdigest()

def is_valid_email(email):
    return email and "@espaitec.mx" in email

def logout():
    keys_to_keep = ['authenticated', 'user_email', 'user_name', 'access_token', 'state']
    for key in list(st.session_state.keys()):
        if key not in keys_to_keep:
            del st.session_state[key]
    st.session_state.authenticated = False
    st.session_state.user_email = ""
    st.session_state.user_name = ""
    st.session_state.access_token = None
    st.rerun()

def get_user_info(credentials):
    try:
        service = build('oauth2', 'v2', credentials=credentials)
        return service.userinfo().get().execute()
    except Exception as e:
        st.error(f"Error usuario: {str(e)}")
        return None

def handle_oauth_callback():
    """Maneja el callback de Google OAuth para autenticar al usuario."""
    try:
        code = st.query_params.get("code")
        if not code:
            return False

        # Detectar si estamos en Render y leer desde variables de entorno
        if "RENDER" in os.environ:
            client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
            redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
        else:
            client_id = st.secrets["google_oauth"]["client_id"]
            client_secret = st.secrets["google_oauth"]["client_secret"]
            redirect_uri = st.secrets["google_oauth"]["redirect_uri"]

        client_config = {
            "web": {
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uris": [redirect_uri],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token"
            }
        }
        
        flow = Flow.from_client_config(
            client_config,
            scopes=["openid", "https://www.googleapis.com/auth/userinfo.email", "https://www.googleapis.com/auth/userinfo.profile"],
            redirect_uri=redirect_uri
        )
        
        flow.fetch_token(code=code)
        credentials = flow.credentials
        st.session_state.access_token = credentials.token
        user_info = get_user_info(credentials)
        if user_info and "email" in user_info:
            email = user_info["email"]
            if is_valid_email(email):
                st.session_state.authenticated = True
                st.session_state.user_email = email
                st.session_state.user_name = user_info.get("name", email.split("@")[0])
                # Generar y guardar token de sesión
                st.session_state.session_token = hashlib.sha256(os.urandom(1024)).hexdigest()
                st.query_params.clear()
                st.query_params["session_token"] = st.session_state.session_token
                return True
            else:
                st.error(f"Acceso denegado. El correo {email} no pertenece al dominio @espaitec.mx")
                return False
        else:
            st.error("No se pudo obtener el correo electrónico del usuario.")
            return False
    
    except Exception as e:
        st.error(f"Error en la autenticación: {str(e)}")
        return False

def get_google_auth_url():
    # Detectar si estamos en Render y leer desde variables de entorno
    if "RENDER" in os.environ:
        client_id = os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        redirect_uri = os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
    else:
        client_id = st.secrets["google_oauth"]["client_id"]
        redirect_uri = st.secrets["google_oauth"]["redirect_uri"]
        
    return (
        "https://accounts.google.com/o/oauth2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={urllib.parse.quote(redirect_uri)}"
        f"&scope={urllib.parse.quote('openid email profile')}"
        "&response_type=code"
        f"&state={st.session_state.state}"
        "&access_type=offline"
        "&prompt=consent"
    )

# ---- FILE HISTORY ----
def manage_file_history(directory, file_extension, max_files=3):
    if not os.path.exists(directory):
        os.makedirs(directory)
    
    history = sorted(
        [os.path.join(directory, f) for f in os.listdir(directory) if f.endswith(file_extension)],
        key=os.path.getmtime
    )
    
    while len(history) >= max_files:
        os.remove(history.pop(0))

# ---- API MERCADO LIBRE ----
def refresh_access_token(client_id, client_secret):
    """Obtiene un nuevo token de acceso usando las credenciales de la aplicación."""
    url = "https://api.mercadolibre.com/oauth/token"
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json"
    }
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    try:
        resp = requests.post(url, headers=headers, data=data, timeout=10)
        resp.raise_for_status()
        token_info = resp.json()
        
        # Guardar el nuevo token en las variables de entorno en memoria
        os.environ["MERCADOLIBRE_ACCESS_TOKEN"] = token_info["access_token"]
        
        # Registrar la renovación en el log
        logger.info(f"Token de Mercado Libre renovado. Expira en {token_info.get('expires_in')} segundos.")
        
        return token_info["access_token"]
    except requests.RequestException as e:
        logger.error(f"Error al renovar el token: {str(e)}")
        if hasattr(e, 'response') and e.response:
            logger.error(f"Respuesta del servidor: {e.response.text}")
        return None

def get_headers(token):
    """Genera los headers de autorización para la API de Mercado Libre."""
    return {"Authorization": f"Bearer {token}"}

def get_user_id(token):
    """Obtiene el ID del usuario autenticado en Mercado Libre."""
    url = "https://api.mercadolibre.com/users/me"
    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)
        
        # Si el token expiró (401), intentar renovarlo
        if resp.status_code == 401:
            logger.warning("Token expirado. Intentando renovar...")
            
            # Obtener credenciales para renovar
            if "RENDER" in os.environ:
                client_id = os.environ.get("MERCADOLIBRE_CLIENT_ID")
                client_secret = os.environ.get("MERCADOLIBRE_CLIENT_SECRET")
            else:
                try:
                    client_id = st.secrets["mercadolibre"]["client_id"]
                    client_secret = st.secrets["mercadolibre"]["client_secret"]
                except (KeyError, FileNotFoundError):
                    logger.error("No se encontraron las credenciales para renovar el token")
                    return None
            
            # Renovar token
            new_token = refresh_access_token(client_id, client_secret)
            if new_token:
                # Reintentar con el nuevo token
                resp = requests.get(url, headers=get_headers(new_token), timeout=10)
            else:
                logger.error("No se pudo renovar el token")
                return None
        
        resp.raise_for_status()
        return resp.json()["id"]
    except requests.RequestException as e:
        logger.error(f"Error al obtener user_id: {str(e)}")
        return None

def get_items(user_id, token, status):
    """Obtiene todos los items de un usuario con un status específico (active, paused, etc)."""
    items = []
    offset = 0
    limit = 50
    while True:
        url = f"https://api.mercadolibre.com/users/{user_id}/items/search?status={status}&limit={limit}&offset={offset}"
        try:
            resp = requests.get(url, headers=get_headers(token), timeout=10)
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            items.extend(results)
            if not results or len(results) < limit:
                break
            offset += limit
        except requests.RequestException as e:
            logger.error(f"Error al obtener items con status {status}: {str(e)}")
            break
    return items

def get_item_detail(item_id, token):
    """Obtiene los detalles completos de un item específico con manejo robusto de errores."""
    url = f"https://api.mercadolibre.com/items/{item_id}"
    max_retries = 3
    
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=get_headers(token), timeout=15)  # Timeout aumentado
            
            # Si hay rate limiting, esperar y reintentar
            if resp.status_code == 429:
                wait_time = 2 ** attempt  # Backoff exponencial
                logger.warning(f"Rate limit para {item_id}, esperando {wait_time}s (intento {attempt + 1}/{max_retries})")
                time.sleep(wait_time)
                continue
                
            resp.raise_for_status()
            return resp.json()
            
        except requests.Timeout:
            logger.warning(f"Timeout para {item_id} (intento {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
        except requests.RequestException as e:
            logger.error(f"Error al obtener detalles del item {item_id} (intento {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
    
    logger.error(f"Falló completamente la obtención de {item_id} después de {max_retries} intentos")
    return None

def extract_sku_from_item(item_or_variation):
    """Extrae el SKU de un item o variación de forma más robusta."""
    
    # Debug: Log la estructura del item para identificar problemas
    item_id = item_or_variation.get("item_id", item_or_variation.get("id", "unknown"))
    
    # 1. seller_custom_field (preferido)
    sku = item_or_variation.get("seller_custom_field", None)
    if isinstance(sku, str) and sku.strip():
        logger.debug(f"SKU encontrado en seller_custom_field para {item_id}: {sku.strip()}")
        return sku.strip()

    # 2. Nuevo: Buscar en el campo "seller_sku" que es donde ML guarda el "Código de identificación (SKU)"
    sku = item_or_variation.get("seller_sku", None)
    if isinstance(sku, str) and sku.strip():
        logger.debug(f"SKU encontrado en seller_sku para {item_id}: {sku.strip()}")
        return sku.strip()

    # 3. Buscar en attributes con más variaciones de nombres
    if "attributes" in item_or_variation:
        for attr in item_or_variation["attributes"]:
            attr_id = attr.get("id", "").upper()
            # Buscar múltiples variaciones de SKU incluyendo SELLER_SKU que es el campo oficial
            if attr_id in ["SELLER_SKU", "SKU", "ITEM_SKU", "PRODUCT_SKU", "CUSTOM_SKU", "IDENTIFIER"]:
                # Probar diferentes campos de valor
                for value_field in ["value_name", "value", "values"]:
                    value = attr.get(value_field)
                    if isinstance(value, str) and value.strip():
                        logger.debug(f"SKU encontrado en attributes.{attr_id}.{value_field} para {item_id}: {value.strip()}")
                        return value.strip()
                    elif isinstance(value, list) and value and isinstance(value[0], str):
                        logger.debug(f"SKU encontrado en attributes.{attr_id}.{value_field}[0] para {item_id}: {value[0].strip()}")
                        return value[0].strip()

    # 4. Buscar en attribute_combinations (para variaciones)
    if "attribute_combinations" in item_or_variation:
        for attr in item_or_variation["attribute_combinations"]:
            attr_id = attr.get("id", "").upper()
            if attr_id in ["SELLER_SKU", "SKU", "ITEM_SKU", "PRODUCT_SKU"]:
                for value_field in ["value_name", "value", "values"]:
                    value = attr.get(value_field)
                    if isinstance(value, str) and value.strip():
                        logger.debug(f"SKU encontrado en attribute_combinations.{attr_id}.{value_field} para {item_id}: {value.strip()}")
                        return value.strip()

    # 5. Campos directos de SKU (ampliados)
    for key in ["sku", "variation_sku", "seller_sku", "custom_sku", "identifier", "code"]:
        value = item_or_variation.get(key, None)
        if isinstance(value, str) and value.strip():
            logger.debug(f"SKU encontrado en campo directo {key} para {item_id}: {value.strip()}")
            return value.strip()

    # 6. Si no se encuentra, log para debugging con más detalle
    logger.warning(f"No se encontró SKU para item {item_id}. Estructura disponible: {list(item_or_variation.keys())}")
    
    # Log específico de atributos para debug
    if "attributes" in item_or_variation:
        attr_list = [f"{attr.get('id', 'NO_ID')}:{attr.get('value_name', attr.get('value', 'NO_VALUE'))}" for attr in item_or_variation["attributes"]]
        logger.warning(f"Atributos disponibles en {item_id}: {attr_list}")
    
    # 7. Último recurso: buscar cualquier campo que contenga "sku" en el nombre
    for key, value in item_or_variation.items():
        if "sku" in key.lower() and isinstance(value, str) and value.strip():
            logger.debug(f"SKU encontrado en campo alternativo {key} para {item_id}: {value.strip()}")
            return value.strip()
    
    return ""

def update_item_stock_safe(item_id, all_variations, token):
    """Actualiza el stock de un item asegurando que se envíen TODAS las variantes para evitar eliminaciones."""
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = get_headers(token)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    
    try:
        # Primer intento
        resp = requests.put(url, data=json.dumps(all_variations), headers=headers, timeout=15)
        if resp.status_code == 200:
            logger.info(f"Item {item_id} actualizado correctamente")
            return {"success": True, "data": resp.json()}
            
        # Si hay rate limiting, esperar y reintentar
        if resp.status_code == 429:
            logger.warning(f"Rate limit alcanzado para {item_id}, reintentando después de pausa")
            time.sleep(2)
            resp = requests.put(url, data=json.dumps(all_variations), headers=headers, timeout=15)
            if resp.status_code == 200:
                logger.info(f"Item {item_id} actualizado correctamente en segundo intento")
                return {"success": True, "data": resp.json()}
                
        # Si sigue fallando, registrar el error
        error_msg = f"Status {resp.status_code}"
        logger.error(f"Error al actualizar {item_id}: {error_msg} - {resp.text}")
        return {"success": False, "error": error_msg, "details": resp.text}
        
    except requests.RequestException as e:
        logger.error(f"Excepción al actualizar {item_id}: {str(e)}")
        return {"success": False, "error": str(e), "details": ""}

def pause_item(item_id, token):
    """Pausa una publicación en Mercado Libre (cuando su stock total es 0)."""
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = get_headers(token)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    payload = {"status": "paused"}
    
    try:
        resp = requests.put(url, data=json.dumps(payload), headers=headers, timeout=10)
        resp.raise_for_status()
        logger.info(f"Item {item_id} pausado correctamente")
        return {"success": True}
    except requests.RequestException as e:
        logger.error(f"Error al pausar item {item_id}: {str(e)}")
        return {"success": False, "error": str(e)}

# ---- LOGIN UI ----
if "session_token" in st.query_params and "session_token" in st.session_state:
    if st.query_params["session_token"] == st.session_state.session_token:
        st.session_state.authenticated = True
    else:
        st.session_state.authenticated = False
        st.error("Token de sesión inválido.")
        
if not st.session_state.authenticated:
    if "code" in st.query_params:
        if handle_oauth_callback():
            st.rerun()
    google_auth_url = get_google_auth_url()
    st.markdown(f"""
        <div style='display:flex;align-items:center;justify-content:center;height:80vh;'>
            <div style='background:#222;padding:3em 4em;border-radius:14px;text-align:center;'>
                <img src="https://cdn.shopify.com/s/files/1/0603/0016/5294/files/logo-1.png?v=1750307988" width="150" style="margin-bottom:2rem;">
                <h2 style="color:#fff;">Gestión de Inventario Mercado Libre</h2>
                <p style="color:#aaa;">Solo para usuarios ESPAITEC.mx</p>
                <a href="{google_auth_url}" style="background:#4285F4;color:#fff;padding:1em 2em;border-radius:6px;text-decoration:none;font-size:1.1em;">Iniciar sesión con Google</a>
            </div>
        </div>
    """, unsafe_allow_html=True)
    st.stop()

# ---- SIDEBAR MENU ----
with st.sidebar:
    st.markdown(
        "<img src='https://cdn.shopify.com/s/files/1/0603/0016/5294/files/logo-1.png?v=1750307988' width='110' class='sidebar-logo'>",
        unsafe_allow_html=True)
    st.markdown("<div class='sidebar-title'>Gestor ESPAITEC</div>", unsafe_allow_html=True)
    menu = st.radio(
        "Menú principal",
        options=["Sincronizar Inventario", "Calculadora de Precios", "Auditor de Variaciones", "Historial"],
        format_func=lambda x: {
            "Sincronizar Inventario": "🟠 Sincronizar Inventario",
            "Calculadora de Precios": "💰 Calculadora de Precios",
            "Auditor de Variaciones": "🔍 Auditor de Variaciones",
            "Historial": "📂 Historial"
        }[x],
        label_visibility="collapsed"
    )
    st.divider()
    st.markdown(
        f"<small>Usuario:<br><b>{st.session_state.user_name}</b><br>{st.session_state.user_email}</small>",
        unsafe_allow_html=True
    )
    if st.button("Cerrar Sesión", use_container_width=True):
        logout()

# ---- SECTION 1: INVENTARIO ----
if menu == "Sincronizar Inventario":
    st.markdown(
        "<h1 style='color:#F39200;'>Gestión de Inventario Mercado Libre</h1>"
        "<div style='color:#888;margin-bottom:20px;'>Actualiza tu inventario de forma segura. <b>Nunca se elimina ninguna variante/publicación.</b></div>",
        unsafe_allow_html=True
    )
    st.header("1. Sincroniza tu inventario en Mercado Libre", anchor=False)
    st.info(
        "1. Extrae tu inventario actual de Mercado Libre.\n"
        "2. Sube el inventario de tu proveedor (Excel con CLAVE_ARTICULO y EXISTENCIAS).\n"
        "3. Revisa la tabla previa de cambios.\n"
        "4. Ejecuta la sincronización (solo se modifica inventario; nunca se elimina nada)."
    )
    # Detectar si estamos en Render y leer desde variables de entorno
    if "RENDER" in os.environ:
        access_token = os.environ.get("MERCADOLIBRE_ACCESS_TOKEN")
        client_id = os.environ.get("MERCADOLIBRE_CLIENT_ID")
        client_secret = os.environ.get("MERCADOLIBRE_CLIENT_SECRET")
    else:
        try:
            access_token = st.secrets["mercadolibre"]["access_token"]
            client_id = st.secrets["mercadolibre"].get("client_id")
            client_secret = st.secrets["mercadolibre"].get("client_secret")
        except (KeyError, FileNotFoundError):
            st.error("🔴 No se pudo cargar el token de acceso. Revisa tu archivo `.streamlit/secrets.toml`.")
            st.stop()
            
    if not access_token:
        st.error("🔴 El token de acceso de Mercado Libre no está configurado.")
        st.stop()
        
    # Verificar si tenemos las credenciales para renovación automática
    if client_id and client_secret:
        st.session_state.ml_can_refresh = True
        st.session_state.ml_client_id = client_id
        st.session_state.ml_client_secret = client_secret
    else:
        st.session_state.ml_can_refresh = False
        st.warning("⚠️ No se han configurado las credenciales para la renovación automática de tokens. Si el token expira, tendrás que renovarlo manualmente.")
    # Cargar el último inventario extraído de Mercado Libre
    if "ml_inventory" not in st.session_state:
        st.session_state.ml_inventory = None
        ml_history_dir = "inventario_ml_historial"
        if os.path.exists(ml_history_dir):
            ml_files = sorted([f for f in os.listdir(ml_history_dir) if f.endswith(".xlsx")], 
                             key=lambda x: os.path.getmtime(os.path.join(ml_history_dir, x)),
                             reverse=True)
            if ml_files:
                latest_ml_file = os.path.join(ml_history_dir, ml_files[0])
                try:
                    st.session_state.ml_inventory = pd.read_excel(latest_ml_file)
                    st.session_state.ml_inventory_fecha = datetime.fromtimestamp(os.path.getmtime(latest_ml_file)).strftime("%Y-%m-%d %H:%M:%S")
                    st.success(f"Inventario cargado automáticamente del historial: {ml_files[0]}")
                except Exception as e:
                    st.error(f"Error al cargar el inventario: {str(e)}")
    
    if "ml_inventory_fecha" not in st.session_state:
        st.session_state.ml_inventory_fecha = None

    # --------- EXTRACCIÓN CON STOP Y PROGRESO ---------
    if "extraction_job" not in st.session_state:
        st.session_state.extraction_job = {"status": "idle"}

    def run_extraction_job(token, job_state):
        """Función principal para extraer el inventario de Mercado Libre en segundo plano."""
        user_id = get_user_id(token)
        if not user_id:
            job_state["status"] = "error"
            job_state["message"] = "No se pudo obtener tu user_id. Revisa tu token."
            logger.error("Extracción fallida: No se pudo obtener user_id")
            return

        # Obtener IDs de todas las publicaciones (activas y pausadas)
        status_list = ["active", "paused"]
        all_items_info = []
        item_ids = []
        for status in status_list:
            status_items = get_items(user_id, token, status)
            logger.info(f"Obtenidas {len(status_items)} publicaciones con status {status}")
            item_ids.extend(status_items)
        
        total_publicaciones = len(item_ids)
        job_state["total"] = total_publicaciones
        logger.info(f"Iniciando extracción de {total_publicaciones} publicaciones")
        
        # Procesar cada publicación
        for idx, item_id in enumerate(item_ids):
            # Verificar si el usuario canceló la operación
            if job_state["status"] == "cancelled":
                logger.info("Extracción cancelada por el usuario")
                return

            # Actualizar progreso
            job_state["progress"] = (idx + 1) / total_publicaciones
            job_state["text"] = f"Descargando {idx+1}/{total_publicaciones}"

            # Obtener detalles de la publicación con manejo de errores robusto
            try:
                item = get_item_detail(item_id, token)
                if not item:
                    logger.warning(f"No se pudo obtener detalles para {item_id}, saltando...")
                    continue
                    
                status = item.get("status", "unknown")
                
                # Debug específico para publicaciones problemáticas
                if item_id in ["MLM1338123694", "MLM1339305557", "MLM1339298925", "MLM1339298922", "MLM1856162519", "MLM2308903050", "MLM3088252038"]:
                    logger.info(f"DEBUG: Analizando publicación problemática {item_id}")
                    try:
                        debug_item_structure(item_id, token)
                    except Exception as debug_error:
                        logger.error(f"Error en debug de {item_id}: {debug_error}")
                
                # Procesar publicación con variaciones
                if "variations" in item and item["variations"]:
                    for v in item["variations"]:
                        try:
                            sku = extract_sku_from_item(v)
                            # Debug adicional para variaciones sin SKU en publicaciones problemáticas
                            if not sku and item_id in ["MLM1338123694", "MLM1339305557", "MLM1339298925", "MLM1339298922", "MLM1856162519", "MLM2308903050", "MLM3088252038"]:
                                logger.warning(f"DEBUG: Variación sin SKU en {item_id}, variation_id: {v.get('id')}")
                                logger.warning(f"Estructura de variación sin SKU: keys={list(v.keys())}, seller_custom_field={v.get('seller_custom_field')}, seller_sku={v.get('seller_sku')}")
                            
                            all_items_info.append({
                                "status": status, 
                                "item_id": item_id, 
                                "título": item.get("title", ""),
                                "sku": sku, 
                                "variación_id": v.get("id", np.nan),
                                "stock": v.get("available_quantity", 0),
                            })
                        except Exception as var_error:
                            logger.error(f"Error procesando variación de {item_id}: {var_error}")
                            continue
                # Procesar publicación sin variaciones
                else:
                    try:
                        sku = extract_sku_from_item(item)
                        # Debug adicional para publicaciones sin SKU
                        if not sku and item_id in ["MLM1338123694", "MLM1339305557", "MLM1339298925", "MLM1339298922", "MLM1856162519", "MLM2308903050", "MLM3088252038"]:
                            logger.warning(f"DEBUG: Publicación sin SKU {item_id}")
                            logger.warning(f"Estructura de publicación sin SKU: keys={list(item.keys())}, seller_custom_field={item.get('seller_custom_field')}, seller_sku={item.get('seller_sku')}")
                        
                        all_items_info.append({
                            "status": status, 
                            "item_id": item_id, 
                            "título": item.get("title", ""),
                            "sku": sku, 
                            "variación_id": np.nan,
                            "stock": item.get("available_quantity", 0),
                        })
                    except Exception as item_error:
                        logger.error(f"Error procesando item {item_id}: {item_error}")
                        continue
                        
                # Pequeña pausa para evitar rate limiting
                if idx % 50 == 0:  # Cada 50 publicaciones
                    time.sleep(0.5)
                    
            except Exception as general_error:
                logger.error(f"Error general procesando {item_id}: {general_error}")
                # Continuar con el siguiente item en lugar de fallar completamente
                continue
        
        if job_state["status"] != "cancelled":
            df_inv = pd.DataFrame(all_items_info)
            # Identificar publicaciones sin SKU
            df_sin_sku = df_inv[df_inv["sku"].apply(lambda x: x is None or str(x).strip() == "")]
            if not df_sin_sku.empty:
                job_state["sin_sku"] = True
                job_state["sin_sku_count"] = len(df_sin_sku)
                job_state["sin_sku_items"] = df_sin_sku[["item_id", "título"]].drop_duplicates().to_dict('records')
                # Guardar reporte Excel de publicaciones/variaciones sin SKU
                sin_sku_dir = "reportes_sin_sku"
                if not os.path.exists(sin_sku_dir):
                    os.makedirs(sin_sku_dir)
                reporte_path = os.path.join(sin_sku_dir, f"sin_sku_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx")
                df_sin_sku.to_excel(reporte_path, index=False)
                job_state["sin_sku_reporte"] = reporte_path
                logger.warning(f"Se encontraron {len(df_sin_sku)} variaciones sin SKU en {len(job_state['sin_sku_items'])} publicaciones")
            else:
                job_state["sin_sku"] = False
                job_state["sin_sku_reporte"] = None
                logger.info("No se encontraron publicaciones sin SKU")
            
            # Guardar en session_state y en historial
            st.session_state.ml_inventory = df_inv
            st.session_state.ml_inventory_fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Guardar archivo en historial
            history_dir = "inventario_ml_historial"
            manage_file_history(history_dir, ".xlsx")
            filename = f"ml_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            file_path = os.path.join(history_dir, filename)
            df_inv.to_excel(file_path, index=False)
            logger.info(f"Inventario guardado en {file_path} con {len(df_inv)} variantes")

            job_state["status"] = "done"

    col_btn1, col_btn2 = st.columns([5, 1])
    with col_btn1:
        if st.session_state.extraction_job["status"] == "running":
            st.button("🔄 Extrayendo...", use_container_width=True, type="primary", disabled=True)
        else:
            if st.button("🔄 Extraer Inventario de Mercado Libre", use_container_width=True, type="primary"):
                st.session_state.extraction_job = {"status": "running", "progress": 0, "text": "Iniciando..."}
                job_thread = threading.Thread(target=run_extraction_job, args=(access_token, st.session_state.extraction_job))
                job_thread.start()
                st.rerun()

    with col_btn2:
        if st.session_state.extraction_job["status"] == "running":
            if st.button("⏹️ Stop", use_container_width=True, type="secondary"):
                st.session_state.extraction_job["status"] = "cancelled"
                st.rerun()
        else:
            st.button("⏹️ Stop", use_container_width=True, type="secondary", disabled=True)

    if st.session_state.extraction_job["status"] == "running":
        progress = st.session_state.extraction_job.get("progress", 0)
        text = st.session_state.extraction_job.get("text", "")
        st.progress(progress, text=text)
        
        # Mostrar logs de debugging en tiempo real
        if os.path.exists("app.log"):
            with st.expander("📋 Ver logs de debugging en tiempo real", expanded=False):
                try:
                    with open("app.log", "r") as f:
                        # Leer las últimas 50 líneas del log
                        lines = f.readlines()
                        recent_lines = lines[-50:] if len(lines) > 50 else lines
                        log_content = "".join(recent_lines)
                        st.text_area("Logs recientes:", value=log_content, height=200, disabled=True)
                except Exception:
                    st.text("No se pueden cargar los logs en este momento")
        
        time.sleep(1)
        st.rerun()
    
    if st.session_state.extraction_job["status"] == "done":
        st.success("¡Inventario extraído!")
        
        # Mostrar alerta de publicaciones sin SKU
        if st.session_state.extraction_job.get("sin_sku", False):
            sin_sku_count = st.session_state.extraction_job.get("sin_sku_count", 0)
            sin_sku_items = st.session_state.extraction_job.get("sin_sku_items", [])
            st.warning(f"⚠️ Se encontraron {sin_sku_count} variaciones sin SKU en {len(sin_sku_items)} publicaciones.")
            if st.session_state.extraction_job.get("sin_sku_reporte"):
                with open(st.session_state.extraction_job["sin_sku_reporte"], "rb") as f:
                    st.download_button(
                        "Descargar reporte de publicaciones sin SKU",
                        f.read(),
                        file_name=os.path.basename(st.session_state.extraction_job["sin_sku_reporte"])
                    )
            with st.expander("Ver publicaciones sin SKU"):
                for item in sin_sku_items:
                    st.markdown(f"**{item['item_id']}**: {item['título']}")
                st.markdown("""
                **Importante:** Las publicaciones sin SKU no podrán ser actualizadas automáticamente.
                Te recomendamos agregar SKUs a todas tus publicaciones en Mercado Libre.
                """)
        
        st.session_state.extraction_job = {"status": "idle"}

    if st.session_state.extraction_job["status"] == "cancelled":
        st.warning("⏹️ Extracción cancelada por el usuario.")
        st.session_state.extraction_job = {"status": "idle"}
        
    if st.session_state.extraction_job["status"] == "error":
        st.error(st.session_state.extraction_job["message"])
        st.session_state.extraction_job = {"status": "idle"}

    if st.session_state.ml_inventory is not None:
        st.success(f"Inventario local disponible. Última extracción: {st.session_state.ml_inventory_fecha}")
        with st.expander("Ver inventario Mercado Libre"):
            st.dataframe(st.session_state.ml_inventory, use_container_width=True)
        
    proveedor_file = st.file_uploader("Sube el inventario del proveedor", type=["xlsx"])
    
    # Botón para procesar el inventario
    procesar_btn = False
    if st.session_state.ml_inventory is not None and proveedor_file is not None:
        procesar_btn = st.button("📊 Procesar Inventario", use_container_width=True, type="primary")


    if procesar_btn:
            try:
                # Leer y validar el archivo del proveedor
                df_prov = pd.read_excel(proveedor_file)
                df_prov.columns = [str(c).strip().upper() for c in df_prov.columns]
                
                # Verificar que tenga las columnas necesarias
                if not {"CLAVE_ARTICULO", "EXISTENCIAS"}.issubset(df_prov.columns):
                    st.error("El archivo debe tener las columnas CLAVE_ARTICULO y EXISTENCIAS.")
                    logger.error("Archivo de proveedor sin columnas requeridas")
                    st.stop()
                
                # Guardar archivo en historial
                history_dir = "inventario_proveedor_historial"
                manage_file_history(history_dir, ".xlsx")
                filename = f"proveedor_inventory_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                file_path = os.path.join(history_dir, filename)
                with open(file_path, "wb") as f:
                    f.write(proveedor_file.getbuffer())
                logger.info(f"Archivo de proveedor guardado en {file_path}")

                # Filtrar datos válidos
                df_prov_filtrado = df_prov[
                    df_prov["CLAVE_ARTICULO"].apply(lambda x: isinstance(x, str) and x.strip() != "") &
                    df_prov["EXISTENCIAS"].apply(lambda x: isinstance(x, (int, float)))
                ].copy()
                
                # Crear diccionario de inventario y aplicar a inventario ML
                inventario_dict = dict(zip(df_prov_filtrado["CLAVE_ARTICULO"], df_prov_filtrado["EXISTENCIAS"]))
                df_ml = st.session_state.ml_inventory.copy()
                
                # Mapear stock nuevo y aplicar regla de seguridad (stock ≤ 3 → stock = 0)
                df_ml["stock_nuevo"] = df_ml["sku"].map(inventario_dict).fillna(0).astype(int)
                df_ml["stock_nuevo"] = df_ml["stock_nuevo"].apply(lambda x: 0 if x <= 3 else x)
                
                # Identificar cambios
                df_ml["cambio"] = df_ml["stock"].astype(int) != df_ml["stock_nuevo"].astype(int)
                st.session_state.df_actualizar = df_ml[df_ml["cambio"]].copy()
                st.session_state.df_ml = df_ml.copy()
                
                logger.info(f"Procesamiento completado: {len(st.session_state.df_actualizar)} variantes con cambios")
                
            except Exception as e:
                st.error(f"Error al procesar el archivo: {str(e)}")
                logger.error(f"Error en procesamiento de inventario: {str(e)}")

    if "df_actualizar" in st.session_state:
        st.divider()
        st.header("2. Vista previa de cambios a aplicar")
        st.markdown("<b>Solo se modifican existencias. Nunca se elimina ningún SKU/variante/publicación.</b>", unsafe_allow_html=True)

        col1, col2, col3 = st.columns(3)
        col1.metric("Variaciones a Actualizar", f"{len(st.session_state.df_actualizar)}")
        stock_total_nuevo = st.session_state.df_ml.groupby('item_id')['stock_nuevo'].sum()
        items_a_pausar = stock_total_nuevo[stock_total_nuevo == 0].count()
        col2.metric("Publicaciones a Pausar", f"{items_a_pausar}")
        col3.metric("Sin Cambio", f"{len(st.session_state.df_ml) - len(st.session_state.df_actualizar)}")

        st.dataframe(st.session_state.df_actualizar[["item_id", "título", "sku", "stock", "stock_nuevo"]], use_container_width=True, hide_index=True)
        
        st.divider()
        st.warning("Al ejecutar, la app actualizará SOLO el inventario de todas las variantes, sin eliminar ninguna. Si una publicación queda en stock 0, se pausa. Revisa bien antes de continuar.", icon="⚠️")
        if st.button("🚀 Ejecutar sincronización", type="primary", use_container_width=True):
            with st.spinner("Actualizando Mercado Libre..."):
                try:
                    log = []
                    errores_tipo = set()
                    exito_count = 0
                    error_count = 0
                    
                    # Actualizar cada publicación con cambios
                    logger.info(f"Iniciando sincronización de {len(st.session_state.df_actualizar['item_id'].unique())} publicaciones")
                    for item_id in st.session_state.df_actualizar['item_id'].unique():
                        # Obtener TODAS las variantes de la publicación (no solo las que cambian)
                        # Esto es CRÍTICO para evitar que Mercado Libre elimine variantes por omisión
                        all_variations_item = st.session_state.df_ml[st.session_state.df_ml['item_id'] == item_id].copy()
                        has_variations = not pd.isna(all_variations_item['variación_id'].iloc[0])
                        
                        # Preparar payload según si tiene variaciones o no
                        if has_variations:
                            # IMPORTANTE: Incluir TODAS las variantes en el payload
                            variations_payload = [{"id": int(row['variación_id']), "available_quantity": int(row['stock_nuevo'])} 
                                                for _, row in all_variations_item.iterrows()]
                            payload = {"variations": variations_payload}
                            logger.info(f"Actualizando {item_id} con {len(variations_payload)} variantes")
                        else:
                            payload = {"available_quantity": int(all_variations_item['stock_nuevo'].iloc[0])}
                            logger.info(f"Actualizando {item_id} sin variantes")
                        
                        # Actualizar en Mercado Libre
                        update_result = update_item_stock_safe(item_id, payload, access_token)
                        if update_result["success"]:
                            exito_count += len(all_variations_item)
                            log.append(f"✔️ {item_id}: Actualizado correctamente ({len(all_variations_item)} variantes/items).")
                        else:
                            error_count += len(all_variations_item)
                            error_msg = update_result.get("error", "Error desconocido")
                            details = update_result.get("details", "")
                            full_error = f"{error_msg} - {details}" if details else error_msg
                            log.append(f"❌ {item_id}: Error en actualización. Causa: {full_error}")
                            errores_tipo.add(error_msg)
                    
                    # Pausar publicaciones con stock 0
                    stock_total_nuevo = st.session_state.df_ml.groupby('item_id')['stock_nuevo'].sum()
                    items_a_pausar_df = stock_total_nuevo[stock_total_nuevo == 0]
                    logger.info(f"Pausando {len(items_a_pausar_df)} publicaciones con stock 0")
                    
                    for item_id_pausar in items_a_pausar_df.index:
                        item_original = st.session_state.df_ml[st.session_state.df_ml['item_id'] == item_id_pausar]
                        if not item_original.empty and item_original['stock'].sum() > 0:
                            pause_result = pause_item(item_id_pausar, access_token)
                            if pause_result["success"]:
                                log.append(f"⏸️ {item_id_pausar}: Publicación pausada correctamente.")
                            else:
                                error_msg_pause = pause_result.get("error", "Error desconocido")
                                log.append(f"❌ {item_id_pausar}: Error al pausar. Causa: {error_msg_pause}")
                                errores_tipo.add(f"Error al pausar: {error_msg_pause}")
                    
                    # Guardar log
                    log_filename = f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
                    log_dir = "logs"
                    if not os.path.exists(log_dir):
                        os.makedirs(log_dir)
                    with open(os.path.join(log_dir, log_filename), "w") as f:
                        f.write("\n".join(log))
                    
                    # Guardar resultado en session_state
                    st.session_state.resultado = {
                        "log": log, 
                        "errores": list(errores_tipo), 
                        "exito": exito_count, 
                        "error": error_count, 
                        "log_file": log_filename
                    }
                    
                    logger.info(f"Sincronización completada: {exito_count} éxitos, {error_count} errores")
                    st.success("¡Proceso terminado! Consulta el resumen abajo.")
                    
                    # Limpiar datos temporales
                    del st.session_state.df_actualizar
                    del st.session_state.df_ml
                    
                except Exception as e:
                    st.error(f"Error durante la sincronización: {str(e)}")
                    logger.error(f"Error no controlado durante sincronización: {str(e)}")

    if "resultado" in st.session_state:
        res = st.session_state.resultado
        colA, colB = st.columns(2)
        colA.metric("Actualizaciones exitosas", res['exito'])
        colB.metric("Errores", res['error'])
        if res['errores']:
            st.subheader("Resumen de errores:")
            for err in res['errores']:
                st.error(f"Tipo de Error: {err}")
        st.subheader("Log de procesamiento:")
        st.code("\n".join(res['log']), language="log")
        with open(os.path.join("logs", res['log_file']), "r") as f:
            st.download_button("Descargar Log Completo", f.read(), file_name=res['log_file'])
        if st.button("✨ Reiniciar proceso"):
            del st.session_state.resultado
            st.rerun()

# ---- SECTION 2: CALCULADORA DE PRECIOS ----
elif menu == "Calculadora de Precios":
    st.markdown(
        "<h1 style='color:#F39200;'>💰 Calculadora de Precios</h1>"
        "<div style='color:#888;margin-bottom:20px;'>Calcula el precio ideal considerando costos, IVA, comisiones y utilidad.</div>",
        unsafe_allow_html=True
    )
    master_file = st.file_uploader("Sube tu archivo Excel 'madre' de productos", type=["xlsx"], key="master_list_uploader")
    st.markdown("---")
    st.subheader("Parámetros de Cálculo")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        utilidad_deseada = st.number_input("Margen de Utilidad Deseado (%)", min_value=0.0, value=20.0, step=1.0, format="%.2f")
    with col2:
        costo_envio_promedio = st.number_input("Costo de Envío Promedio ($)", min_value=0.0, value=90.0, step=5.0, format="%.2f")
    with col3:
        iva_porcentaje = st.number_input("IVA (%)", min_value=0.0, value=16.0, step=1.0, format="%.2f")
    with col4:
        comision_ml_porcentaje = st.number_input("Comisión ML (%)", min_value=0.0, value=15.0, step=0.5, format="%.2f")
    if master_file:
        df_master = pd.read_excel(master_file)
        df_master.columns = [str(c).strip().upper() for c in df_master.columns]
        if "PRECIO MAYOREO" in df_master.columns:
            def calcular_precio_venta(costo):
                if pd.isna(costo) or not isinstance(costo, (int, float)) or costo <= 0:
                    return np.nan
                utilidad_dec = utilidad_deseada / 100.0
                iva_dec = iva_porcentaje / 100.0
                comision_ml_dec = comision_ml_porcentaje / 100.0
                precio_sugerido = (costo * (1 + iva_dec + utilidad_dec) + costo_envio_promedio) / (1 - comision_ml_dec)
                return np.ceil(precio_sugerido) if precio_sugerido >= 299.00 else 299.00
            df_master['PRECIO VENTA SUGERIDO'] = df_master['PRECIO MAYOREO'].apply(calcular_precio_venta)
            st.markdown("---")
            st.subheader("Catálogo con Precios Calculados")
            columnas_a_mostrar = ["CLAVE_ARTICULO", "DESCRIPCION DEL ARTICULO", "PRECIO MAYOREO", "PRECIO VENTA SUGERIDO"]
            columnas_existentes = [col for col in columnas_a_mostrar if col in df_master.columns]
            st.dataframe(df_master[columnas_existentes], use_container_width=True)
            output_precios = io.BytesIO()
            with pd.ExcelWriter(output_precios, engine='openpyxl') as writer:
                df_master.to_excel(writer, index=False)
            st.download_button("Descargar Catálogo con Precios Calculados", data=output_precios.getvalue(), file_name="catalogo_precios_calculados.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.error("El archivo maestro no contiene la columna 'PRECIO MAYOREO'. Por favor, verifica el archivo.")

# ---- SECTION 3: AUDITOR ----
elif menu == "Auditor de Variaciones":
    st.markdown(
        "<h1 style='color:#F39200;'>🔍 Auditor de Variaciones Perdidas</h1>"
        "<div style='color:#888;margin-bottom:20px;'>Compara dos inventarios y detecta variaciones o SKUs que se hayan perdido.</div>",
        unsafe_allow_html=True
    )
    col1, col2 = st.columns(2)
    with col1:
        respaldo_file = st.file_uploader("1. Sube tu inventario de RESPALDO (archivo bueno)", type=["xlsx"], key="respaldo_uploader")
    with col2:
        actual_file = st.file_uploader("2. Sube tu inventario ACTUAL (tras el problema)", type=["xlsx"], key="actual_uploader")
    if respaldo_file and actual_file:
        df_respaldo = pd.read_excel(respaldo_file)
        df_actual = pd.read_excel(actual_file)
        counts_respaldo = df_respaldo.groupby('item_id').size()
        counts_actual = df_actual.groupby('item_id').size()
        df_compare = pd.DataFrame({'respaldo': counts_respaldo, 'actual': counts_actual}).fillna(0)
        df_compare['diferencia'] = df_compare['respaldo'] - df_compare['actual']
        items_afectados = df_compare[df_compare['diferencia'] > 0].index
        if not items_afectados.empty:
            st.subheader("Publicaciones con Variaciones Faltantes")
            df_merged = df_respaldo.merge(df_actual, on=['item_id', 'variación_id'], how='outer', indicator=True)
            df_perdidas = df_merged[df_merged['_merge'] == 'left_only']
            df_reporte = df_perdidas[df_perdidas['item_id'].isin(items_afectados)]
            columnas_reporte = ['item_id', 'título_x', 'sku_x', 'variación_id']
            df_reporte = df_reporte[columnas_reporte].rename(columns={'título_x': 'título', 'sku_x': 'sku'})
            st.dataframe(df_reporte, use_container_width=True)
            st.success(f"Se encontraron {len(df_reporte)} variaciones faltantes en {len(items_afectados)} publicaciones.")
            output_reporte = io.BytesIO()
            with pd.ExcelWriter(output_reporte, engine='openpyxl') as writer:
                df_reporte.to_excel(writer, index=False)
            st.download_button("Descargar Reporte de Variaciones Faltantes", data=output_reporte.getvalue(), file_name="reporte_variaciones_faltantes.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        else:
            st.success("✅ ¡No se encontraron diferencias en el número de variaciones entre los dos archivos!")

# ---- SECTION 4: HISTORIAL ----
elif menu == "Historial":
    st.markdown(
        "<h1 style='color:#F39200;'>📂 Historial de Archivos</h1>"
        "<div style='color:#888;margin-bottom:20px;'>Aquí puedes descargar los últimos 3 archivos de inventario de Mercado Libre y de tu proveedor.</div>",
        unsafe_allow_html=True
    )

    st.subheader("Historial de Inventarios de Mercado Libre")
    ml_history_dir = "inventario_ml_historial"
    if os.path.exists(ml_history_dir):
        ml_files = sorted(os.listdir(ml_history_dir), reverse=True)
        for f in ml_files:
            with open(os.path.join(ml_history_dir, f), "rb") as file:
                st.download_button(f, file.read(), file_name=f)
    else:
        st.info("No hay historial de inventarios de Mercado Libre.")

    st.subheader("Historial de Inventarios del Proveedor")
    prov_history_dir = "inventario_proveedor_historial"
    if os.path.exists(prov_history_dir):
        prov_files = sorted(os.listdir(prov_history_dir), reverse=True)
        for f in prov_files:
            with open(os.path.join(prov_history_dir, f), "rb") as file:
                st.download_button(f, file.read(), file_name=f)
    else:
        st.info("No hay historial de inventarios del proveedor.")

def debug_item_structure(item_id, token):
    """Función temporal para debuggear la estructura de un item específico."""
    url = f"https://api.mercadolibre.com/items/{item_id}"
    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)
        resp.raise_for_status()
        item = resp.json()
        
        logger.info(f"\n=== DEBUG ITEM {item_id} ===")
        logger.info(f"Título: {item.get('title', 'N/A')}")
        logger.info(f"seller_custom_field: {item.get('seller_custom_field', 'N/A')}")
        logger.info(f"seller_sku: {item.get('seller_sku', 'N/A')}")
        
        if "attributes" in item:
            logger.info("Attributes:")
            for attr in item["attributes"]:
                attr_id = attr.get('id', 'NO_ID')
                attr_value = attr.get('value_name', attr.get('value', 'NO_VALUE'))
                logger.info(f"  - {attr_id}: {attr_value}")
        
        if "variations" in item and item["variations"]:
            logger.info("Variations:")
            for i, var in enumerate(item["variations"]):
                logger.info(f"  Variation {i}:")
                logger.info(f"    - id: {var.get('id', 'N/A')}")
                logger.info(f"    - seller_custom_field: {var.get('seller_custom_field', 'N/A')}")
                logger.info(f"    - seller_sku: {var.get('seller_sku', 'N/A')}")
                if "attributes" in var:
                    for attr in var["attributes"]:
                        attr_id = attr.get('id', 'NO_ID')
                        attr_value = attr.get('value_name', attr.get('value', 'NO_VALUE'))
                        logger.info(f"    - {attr_id}: {attr_value}")
        
        return item
    except Exception as e:
        logger.error(f"Error debugging item {item_id}: {e}")
        return None
