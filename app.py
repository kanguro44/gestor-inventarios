import streamlit as st
import requests
import json
import os
import pandas as pd
import io
from datetime import datetime
import numpy as np
import time
import math

# ==============================
# CONFIGURACIÓN INICIAL Y ESTILO
# ==============================

st.set_page_config(layout="wide", page_title="Gestión de Inventario ESPAITEC")

COLOR_NARANJA = "#F39200"
COLOR_NEGRO = "#1D1D1B"
COLOR_GRIS = "#f4f4f4"

st.markdown(f"""
    <style>
        .main .block-container {{
            padding-top: 2rem;
        }}
        html, body, [class*="css"]  {{
            font-family: Helvetica, Arial, sans-serif !important;
        }}
        .stButton>button {{
            background-color: {COLOR_NARANJA};
            color: white;
            border-radius:8px;
            font-weight:bold;
            border:none;
            transition: background-color 0.3s ease;
        }}
        .stButton>button:hover {{
            background-color: #e97d00;
            color: white;
        }}
        .stMetric {{
            background-color: #FFFFFF;
            border: 1px solid #E0E0E0;
            border-radius: 10px;
            padding: 15px;
        }}
    </style>
""", unsafe_allow_html=True)

# ==============================
# FUNCIONES CORE
# ==============================

# --- Interacción con API de Mercado Libre ---
def get_headers(token):
    return {"Authorization": f"Bearer {token}"}

def get_user_id(token):
    url = "https://api.mercadolibre.com/users/me"
    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()["id"]
    except requests.RequestException:
        return None

def get_items(user_id, token, status):
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
        except requests.RequestException:
            break
    return items

def get_item_detail(item_id, token):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    try:
        resp = requests.get(url, headers=get_headers(token), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException:
        return None

def update_item_stock(item_id, payload, token):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = get_headers(token)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    
    try:
        for attempt in range(3):
            resp = requests.put(url, data=json.dumps(payload), headers=headers, timeout=15)
            if resp.status_code == 200:
                return {"success": True, "data": resp.json()}
            if resp.status_code == 429:
                time.sleep((attempt + 1) * 2)
                continue
            resp.raise_for_status()
        return {"success": False, "error": f"El servidor respondió con estatus {resp.status_code}", "details": resp.text}
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "details": ""}

def pause_item(item_id, token):
    url = f"https://api.mercadolibre.com/items/{item_id}"
    headers = get_headers(token)
    headers["Content-Type"] = "application/json"
    headers["Accept"] = "application/json"
    payload = {"status": "paused"}
    
    try:
        resp = requests.put(url, data=json.dumps(payload), headers=headers, timeout=10)
        resp.raise_for_status()
        return {"success": True}
    except requests.RequestException as e:
        return {"success": False, "error": str(e)}

# --- Manejo de Archivos Locales ---
import os

def load_token():
    access_token = os.getenv("ML_ACCESS_TOKEN")
    if access_token:
        return {"access_token": access_token}
    return None

def guardar_inventario_local(df):
    script_dir = os.path.dirname(__file__)
    inv_path = os.path.join(script_dir, "inventario_ml.xlsx")
    fecha_path = os.path.join(script_dir, "inventario_ml.fecha.txt")
    
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    with open(inv_path, "wb") as f:
        f.write(output.getvalue())
    with open(fecha_path, "w") as f:
        f.write(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    st.session_state.df_inv = df
    st.session_state.fecha_inv = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def cargar_inventario_local():
    script_dir = os.path.dirname(__file__)
    inv_path = os.path.join(script_dir, "inventario_ml.xlsx")
    fecha_path = os.path.join(script_dir, "inventario_ml.fecha.txt")

    if 'df_inv' not in st.session_state:
        if os.path.exists(inv_path):
            st.session_state.df_inv = pd.read_excel(inv_path)
            if os.path.exists(fecha_path):
                with open(fecha_path) as f:
                    st.session_state.fecha_inv = f.read().strip()
            else:
                st.session_state.fecha_inv = "Fecha desconocida"
        else:
            st.session_state.df_inv = None
            st.session_state.fecha_inv = None

# ==============================
# INICIALIZACIÓN DE SESSION STATE
# ==============================

if 'results' not in st.session_state:
    st.session_state.results = None

cargar_inventario_local()

# ==============================
# INTERFAZ DE USUARIO (UI)
# ==============================

# --- Encabezado ---
st.markdown(
    f"""
    <div style="display:flex;align-items:center;margin-bottom:1.2em;">
      <img src="https://cdn.shopify.com/s/files/1/0603/0016/5294/files/logo-1.png?v=1750307988" width="80" style="margin-right:18px;border-radius:16px;">
      <div>
        <h1 style="color:{COLOR_NARANJA};margin-bottom:0px;font-family:Helvetica;">Gestión de Inventario Mercado Libre</h1>
        <div style="color:{COLOR_NEGRO};font-size:1.12em;">Plataforma oficial para actualizar stock <b>masivo y seguro</b> de <b>ESPAITEC Tactical & Outdoors</b>.</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Verificación de Token ---
token_data = load_token()
if not token_data:
    st.error("🔴 **Error de Autenticación:** No se encontró el archivo `ml_token.json`. Por favor, asegúrate de que el archivo de token esté en la misma carpeta que la aplicación.")
    st.stop()
access_token = token_data["access_token"]

# --- Pestañas de Flujo de Trabajo ---
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Paso 1: Cargar Datos", 
    "Paso 2: Revisar y Confirmar", 
    "Paso 3: Resultados",
    "💰 Calculadora de Precios",
    "🛠️ Herramientas de Recuperación"
])

# --- PESTAÑA 1: CARGAR DATOS ---
with tab1:
    st.header("Paso 1: Cargar y Sincronizar Datos", anchor=False)
    st.markdown("El primer paso es tener la información más reciente. Extrae tu inventario de Mercado Libre y luego carga el archivo de existencias de tu proveedor.")

    st.divider()

    col1, col2 = st.columns(2, gap="large")

    with col1:
        with st.container(border=True):
            st.subheader("📦 Inventario de Mercado Libre")
            st.markdown("Obtén una copia fresca de todas tus publicaciones activas y pausadas.")

            if st.session_state.df_inv is not None:
                st.success(f"Inventario local disponible. Última extracción: **{st.session_state.fecha_inv}**.")
                
                script_dir = os.path.dirname(__file__)
                inv_path = os.path.join(script_dir, "inventario_ml.xlsx")
                if os.path.exists(inv_path):
                    with open(inv_path, "rb") as f:
                        st.download_button(
                            label="📥 Descargar Copia del Inventario Actual",
                            data=f.read(),
                            file_name="inventario_ml_extraido.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                with st.expander("Ver inventario de Mercado Libre"):
                    st.dataframe(st.session_state.df_inv, use_container_width=True)
            else:
                st.info("Aún no has extraído tu inventario de Mercado Libre. Haz clic en el botón para empezar.")

            if st.button("🔄 Sincronizar desde Mercado Libre", use_container_width=True, type="primary"):
                with st.spinner("Contactando a Mercado Libre... (Puede tardar varios minutos)"):
                    user_id = get_user_id(access_token)
                    if not user_id:
                        st.error("No se pudo obtener tu user_id. Revisa tu token.")
                        st.stop()

                status_list = ["active", "paused"]
                all_items_info = []
                
                progress_bar = st.progress(0, text="Obteniendo IDs de publicaciones...")
                item_ids = []
                for status in status_list:
                    item_ids.extend(get_items(user_id, access_token, status))
                
                total_publicaciones = len(item_ids)
                for idx, item_id in enumerate(item_ids):
                    progress_bar.progress((idx + 1) / total_publicaciones, text=f"Descargando detalle de publicación {idx+1}/{total_publicaciones}")
                    item = get_item_detail(item_id, access_token)
                    if item:
                        status = item.get("status", "unknown")
                        if "variations" in item and item["variations"]:
                            for v in item["variations"]:
                                all_items_info.append({
                                    "status": status, "item_id": item_id, "título": item.get("title", ""),
                                    "sku": v.get("seller_custom_field", ""), "variación_id": v.get("id", np.nan),
                                    "stock": v.get("available_quantity", 0),
                                })
                        else:
                            all_items_info.append({
                                "status": status, "item_id": item_id, "título": item.get("title", ""),
                                "sku": item.get("seller_custom_field", ""), "variación_id": np.nan,
                                "stock": item.get("available_quantity", 0),
                            })
                
                df_inv_nuevo = pd.DataFrame(all_items_info)
                guardar_inventario_local(df_inv_nuevo)
                st.success("¡Extracción completada! Inventario guardado.")
                st.rerun()

    with col2:
        with st.container(border=True):
            st.subheader("🚚 Inventario del Proveedor")
            st.markdown("Carga el archivo Excel que contiene los SKUs y las existencias actuales.")
            
            st.session_state.archivo_proveedor = st.file_uploader(
                "Selecciona el archivo de existencias del proveedor", 
                type=["xlsx"],
                help="Asegúrate de que el archivo contenga las columnas 'CLAVE_ARTICULO' y 'EXISTENCIAS'.",
                key="proveedor_uploader",
                label_visibility="collapsed"
            )
            if st.session_state.archivo_proveedor:
                st.success(f"Archivo **{st.session_state.archivo_proveedor.name}** cargado.")
                with st.expander("Ver contenido del archivo"):
                    df_prov_preview = pd.read_excel(st.session_state.archivo_proveedor)
                    st.dataframe(df_prov_preview, use_container_width=True)

# --- PESTAÑA 2: REVISAR Y CONFIRMAR ---
with tab2:
    st.header("Paso 2: Revisar y Confirmar Cambios", anchor=False)
    st.markdown("Aquí puedes ver un resumen de los cambios que se aplicarán. **Verifica los datos cuidadosamente antes de confirmar.**")
    st.divider()

    if st.session_state.archivo_proveedor and st.session_state.df_inv is not None:
        df_prov = pd.read_excel(st.session_state.archivo_proveedor)
        df_prov = df_prov.rename(columns=lambda x: x.strip().upper())

        if "CLAVE_ARTICULO" in df_prov.columns and "EXISTENCIAS" in df_prov.columns:
            df_prov_filtrado = df_prov[
                df_prov["CLAVE_ARTICULO"].apply(lambda x: isinstance(x, str) and x.strip() != "") &
                df_prov["EXISTENCIAS"].apply(lambda x: isinstance(x, (int, float)))
            ].copy()
            
            inventario_dict = dict(zip(df_prov_filtrado["CLAVE_ARTICULO"], df_prov_filtrado["EXISTENCIAS"]))
            
            df_merged = st.session_state.df_inv.copy()
            df_merged['stock_nuevo'] = df_merged['sku'].map(inventario_dict).fillna(0).astype(int)
            df_merged['stock_nuevo'] = df_merged['stock_nuevo'].apply(lambda x: 0 if x <= 3 else x)
            df_merged['cambio'] = df_merged['stock'].astype(int) != df_merged['stock_nuevo'].astype(int)
            
            df_actualizar = df_merged[df_merged['cambio']].copy()
            
            # --- Métricas Visuales ---
            st.subheader("Resumen de la Sincronización", anchor=False)
            col1, col2, col3 = st.columns(3)
            col1.metric("🔄 Variaciones a Actualizar", f"{len(df_actualizar)}")
            
            stock_total_nuevo = df_merged.groupby('item_id')['stock_nuevo'].sum()
            items_a_pausar = stock_total_nuevo[stock_total_nuevo == 0].count()
            col2.metric("⏸️ Publicaciones a Pausar", f"{items_a_pausar}")
            
            col3.metric("✅ Variaciones sin Cambios", f"{len(df_merged) - len(df_actualizar)}")

            # --- Vista Previa Interactiva ---
            st.subheader("Vista Previa de Cambios", anchor=False)
            st.info("Esta tabla muestra únicamente las variaciones cuyo stock será modificado.")
            st.dataframe(df_actualizar[['item_id', 'título', 'sku', 'stock', 'stock_nuevo']].rename(columns={
                'item_id': 'ID Publicación', 'título': 'Título', 'sku': 'SKU', 'stock': 'Stock Actual', 'stock_nuevo': 'Stock Nuevo'
            }), use_container_width=True)

            st.divider()
            
            with st.container(border=True):
                st.warning("🔴 **Acción Irreversible**")
                st.markdown("Al hacer clic en el botón, se aplicarán los cambios de stock en Mercado Libre. Asegúrate de que todo es correcto.")
                if st.button("🚀 Confirmar y Ejecutar Sincronización", use_container_width=True, type="primary"):
                    # --- Lógica de Actualización Segura ---
                    items_con_cambios = df_actualizar['item_id'].unique()
                    total_items_a_procesar = len(items_con_cambios)
                    progreso = st.progress(0, text="Iniciando actualización...")
                    
                    results_log = []
                    errores_tipo = set()
                    exito_count = 0
                    error_count = 0

                    for i, item_id in enumerate(items_con_cambios):
                        progreso.progress((i + 1) / total_items_a_procesar, text=f"Procesando item {i+1}/{total_items_a_procesar}: {item_id}")
                        
                        item_df = df_merged[df_merged['item_id'] == item_id]
                        
                        has_variations = not pd.isna(item_df['variación_id'].iloc[0])
                        payload = {}

                        if has_variations:
                            variations_payload = [
                                {"id": int(row['variación_id']), "available_quantity": int(row['stock_nuevo'])}
                                for _, row in item_df.iterrows()
                            ]
                            payload = {"variations": variations_payload}
                        else:
                            new_stock = item_df['stock_nuevo'].iloc[0]
                            payload = {"available_quantity": int(new_stock)}
                        
                        update_result = update_item_stock(item_id, payload, access_token)

                        if update_result["success"]:
                            num_variations = len(item_df)
                            exito_count += num_variations
                            results_log.append(f"✔️ {item_id}: Actualizado con éxito ({num_variations} variaciones/items).")
                        else:
                            num_variations = len(item_df)
                            error_count += num_variations
                            error_msg = update_result.get("error", "Error desconocido")
                            details = update_result.get("details", "")
                            full_error = f"{error_msg} - {details}" if details else error_msg
                            results_log.append(f"❌ {item_id}: Error en la actualización. Causa: {full_error}")
                            errores_tipo.add(error_msg)

                    # --- Lógica de Pausado ---
                    stock_total_nuevo = df_merged.groupby('item_id')['stock_nuevo'].sum()
                    items_a_pausar_df = stock_total_nuevo[stock_total_nuevo == 0]
                    
                    if not items_a_pausar_df.empty:
                        results_log.append("\n--- Iniciando proceso de pausado de publicaciones sin stock ---")
                        for item_id_pausar in items_a_pausar_df.index:
                            item_original = st.session_state.df_inv[st.session_state.df_inv['item_id'] == item_id_pausar]
                            if not item_original.empty and item_original['stock'].sum() > 0:
                                pause_result = pause_item(item_id_pausar, access_token)
                                if pause_result["success"]:
                                    results_log.append(f"⏸️ {item_id_pausar}: Publicación pausada correctamente.")
                                else:
                                    error_msg_pause = pause_result.get("error", "Error desconocido")
                                    results_log.append(f"❌ {item_id_pausar}: Error al intentar pausar. Causa: {error_msg_pause}")
                                    errores_tipo.add(f"Error al pausar: {error_msg_pause}")

                    st.session_state.results = {
                        "log": results_log,
                        "errors": list(errores_tipo),
                        "exito": exito_count,
                        "error": error_count
                    }
                    st.success("Proceso finalizado. Ve a la pestaña 'Paso 3: Resultados' para ver el detalle.")
                    st.rerun()

        else:
            st.error("El archivo del proveedor no contiene las columnas 'CLAVE_ARTICULO' y 'EXISTENCIAS'.")
    else:
        st.info("Sube un archivo de proveedor y asegúrate de haber extraído el inventario de Mercado Libre para continuar.")

# --- PESTAÑA 3: RESULTADOS ---
with tab3:
    st.header("Paso 3: Resultados de la Sincronización", anchor=False)
    st.markdown("Aquí puedes ver el resumen y el registro detallado del proceso que acaba de terminar.")
    st.divider()

    if st.session_state.results:
        res = st.session_state.results
        col1, col2 = st.columns(2)
        col1.metric("✅ Actualizaciones Exitosas", res['exito'])
        col2.metric("❌ Errores", res['error'])

        if res['errors']:
            st.subheader("Resumen de Errores", anchor=False)
            for err in res['errors']:
                st.error(f"**Tipo de Error:** {err}")
            if any("validación" in err.lower() for err in res['errors']):
                st.warning("Se encontraron errores de validación. Esto puede ocurrir si una publicación fue modificada manualmente en ML. Se recomienda re-extraer el inventario para asegurar la consistencia de los datos.")

        st.subheader("Registro de Procesamiento", anchor=False)
        with st.container(height=400):
            st.code("\n".join(res['log']), language="log")
        
        if st.button("✨ Iniciar un Nuevo Proceso"):
            st.session_state.results = None
            st.rerun()
    else:
        st.info("Aún no se ha ejecutado ningún proceso de actualización. Completa los pasos 1 y 2.")

# --- PESTAÑA 4: CALCULADORA DE PRECIOS ---
with tab4:
    st.header("💰 Catálogo Maestro y Calculadora de Precios")
    st.markdown("Sube tu lista 'madre' de productos para calcular precios de venta basados en tus costos y la utilidad deseada.")

    master_file = st.file_uploader(
        "Sube tu archivo Excel 'madre' de productos",
        type=["xlsx"],
        key="master_list_uploader"
    )

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
        comision_ml_porcentaje = st.number_input("Comisión de Mercado Libre (%)", min_value=0.0, value=15.0, step=0.5, format="%.2f")

    if master_file:
        df_master = pd.read_excel(master_file)
        df_master.columns = [str(c).strip().upper() for c in df_master.columns]

        if "PRECIO MAYOREO" in df_master.columns:
            
            def calcular_precio_venta(costo):
                if pd.isna(costo) or not isinstance(costo, (int, float)) or costo <= 0:
                    return np.nan
                
                # Convertir porcentajes a decimales
                utilidad_dec = utilidad_deseada / 100.0
                iva_dec = iva_porcentaje / 100.0
                comision_ml_dec = comision_ml_porcentaje / 100.0

                # Fórmula de precios
                precio_sugerido = (costo * (1 + iva_dec + utilidad_dec) + costo_envio_promedio) / (1 - comision_ml_dec)

                # Regla de negocio: precio mínimo de $299
                if precio_sugerido < 299.00:
                    precio_final = 299.00
                else:
                    # Redondear siempre hacia arriba al siguiente peso entero
                    precio_final = math.ceil(precio_sugerido)
                
                return precio_final

            df_master['PRECIO VENTA SUGERIDO'] = df_master['PRECIO MAYOREO'].apply(calcular_precio_venta)
            
            st.markdown("---")
            st.subheader("Catálogo con Precios Calculados")
            
            columnas_a_mostrar = [
                "CLAVE_ARTICULO", "DESCRIPCION DEL ARTICULO", "PRECIO MAYOREO", "PRECIO VENTA SUGERIDO"
            ]
            columnas_existentes = [col for col in columnas_a_mostrar if col in df_master.columns]
            
            st.dataframe(df_master[columnas_existentes], use_container_width=True)

            # Botón para descargar el reporte
            output_precios = io.BytesIO()
            with pd.ExcelWriter(output_precios, engine='openpyxl') as writer:
                df_master.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Catálogo con Precios Calculados",
                data=output_precios.getvalue(),
                file_name="catalogo_precios_calculados.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

        else:
            st.error("El archivo maestro no contiene la columna 'PRECIO MAYOREO'. Por favor, verifica el archivo.")

# --- PESTAÑA 5: HERRAMIENTAS DE RECUPERACIÓN ---
with tab5:
    st.header("🔍 Auditor de Variaciones Perdidas")
    st.warning("""
        **Propósito:** Esta herramienta te ayuda a identificar variaciones que pueden haber sido eliminadas accidentalmente de tus publicaciones.
        Compara un archivo de respaldo (antes del problema) con un archivo actual (después del problema) para generar un reporte de lo que falta.
    """)

    col1, col2 = st.columns(2)
    with col1:
        respaldo_file = st.file_uploader(
            "1. Sube tu inventario de RESPALDO (el archivo bueno)", 
            type=["xlsx"],
            key="respaldo_uploader"
        )
    with col2:
        actual_file = st.file_uploader(
            "2. Sube tu inventario ACTUAL (extraído después del problema)", 
            type=["xlsx"],
            key="actual_uploader"
        )

    if respaldo_file and actual_file:
        df_respaldo = pd.read_excel(respaldo_file)
        df_actual = pd.read_excel(actual_file)

        # Contar variaciones por item en cada dataframe
        counts_respaldo = df_respaldo.groupby('item_id').size()
        counts_actual = df_actual.groupby('item_id').size()

        # Comparar los conteos
        df_compare = pd.DataFrame({'respaldo': counts_respaldo, 'actual': counts_actual}).fillna(0)
        df_compare['diferencia'] = df_compare['respaldo'] - df_compare['actual']
        
        items_afectados = df_compare[df_compare['diferencia'] > 0].index

        if not items_afectados.empty:
            st.subheader("Publicaciones con Variaciones Faltantes")
            
            # Identificar las variaciones exactas que faltan
            # Usamos 'indicator=True' para saber de dónde viene cada fila
            df_merged = df_respaldo.merge(
                df_actual, 
                on=['item_id', 'variación_id'], 
                how='outer', 
                indicator=True
            )
            
            # Las que solo existen en el respaldo son las perdidas
            df_perdidas = df_merged[df_merged['_merge'] == 'left_only']
            
            # Filtrar solo para los items que sabemos que están afectados
            df_reporte = df_perdidas[df_perdidas['item_id'].isin(items_afectados)]
            
            columnas_reporte = ['item_id', 'título_x', 'sku_x', 'variación_id']
            df_reporte = df_reporte[columnas_reporte].rename(columns={
                'título_x': 'título',
                'sku_x': 'sku'
            })

            st.dataframe(df_reporte, use_container_width=True)
            st.success(f"Se encontraron {len(df_reporte)} variaciones faltantes en {len(items_afectados)} publicaciones.")

            # Botón para descargar el reporte
            output_reporte = io.BytesIO()
            with pd.ExcelWriter(output_reporte, engine='openpyxl') as writer:
                df_reporte.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Descargar Reporte de Variaciones Faltantes",
                data=output_reporte.getvalue(),
                file_name="reporte_variaciones_faltantes.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                type="primary"
            )

        else:
            st.success("✅ ¡Excelente! No se encontraron diferencias en el número de variaciones entre los dos archivos.")
