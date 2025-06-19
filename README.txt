# Gestión de Inventario ESPAITEC

## Descripción

Esta aplicación permite gestionar de forma **segura y eficiente** el inventario de productos en Mercado Libre para ESPAITEC Tactical & Outdoors. Ofrece herramientas para sincronizar inventario, calcular precios y auditar variaciones de productos, todo en una **interfaz moderna con navegación lateral**.

> **IMPORTANTE:**  
> El sistema está diseñado para que **nunca se elimine ninguna variante ni publicación** en Mercado Libre.  
> Al actualizar, la app **siempre envía la información de TODAS las variantes**, aunque solo se modifique el stock, evitando así que Mercado Libre borre accidentalmente variantes/SKUs.  
> La app solo actualiza inventario y puede pausar publicaciones cuando el stock total es 0, pero nunca borra ni omite variantes o publicaciones.

---

## Características principales

- **Autenticación segura** con Google OAuth (solo correos @espaitec.mx)
- **Sesión persistente**: la sesión se mantiene activa al actualizar la página
- **Navegación por menú lateral**: sincronización de inventario, calculadora de precios, auditoría de variaciones e historial de archivos
- **Sincronización unificada y segura**: carga y actualización de inventario en una sola pantalla, sin riesgo de perder variantes
- **Extracción de inventario en segundo plano**: la extracción de inventario continúa aunque se recargue la página
- **Barra de progreso y botón de "Stop"** para cancelar la extracción de inventario en tiempo real
- **Detección inteligente de SKUs**: busca SKUs en múltiples campos de la API de Mercado Libre para asegurar la correcta sincronización
- **Alerta de publicaciones sin SKU**: identifica y muestra las publicaciones que no tienen SKU asignado
- **Carga automática del último inventario**: al iniciar, carga automáticamente el último inventario extraído del historial
- **Calculadora de precios** basada en costos, utilidad deseada, IVA, envío y comisión ML
- **Auditoría de variaciones perdidas**: compara archivos y encuentra SKUs/variantes faltantes
- **Regla de stock seguro**: cualquier SKU con stock igual o menor a 3 se marca automáticamente como stock 0 (para evitar sobreventas)
- **Feedback visual** detallado, logs descargables, advertencias claras y métricas en tiempo real
- **Historial de archivos**: guarda y permite descargar los últimos 3 archivos de inventario de Mercado Libre y del proveedor

---

## Seguridad

- La app **nunca elimina variantes ni publicaciones**. Siempre envía la lista completa de variantes en cada actualización de inventario, aunque solo se cambie una cantidad, **evitando que Mercado Libre elimine por omisión**.
- El botón de sincronización solo modifica existencias y, si una publicación queda en stock 0, únicamente la pausa (no la elimina).
- Al cancelar la extracción, no se guarda ningún inventario parcial.
- Solo los usuarios autenticados con correo @espaitec.mx pueden acceder.
- **Búsqueda exhaustiva de SKUs**: la aplicación busca SKUs en múltiples campos de la API para asegurar que ninguna variante quede sin identificar.
- **Alertas de seguridad**: notifica cuando se encuentran publicaciones sin SKU que podrían causar problemas en la sincronización.

---

## Requisitos

- Python 3.7 o superior
- Streamlit
- Pandas
- NumPy
- openpyxl
- requests
- google-auth-oauthlib
- google-api-python-client
- Google OAuth credenciales
- Token de acceso de Mercado Libre

---

## Instalación

1. Clona este repositorio:
    ```sh
    git clone <url-del-repositorio>
    cd inventarios
    ```

2. Instala las dependencias:
    ```sh
    pip install -r requirements.txt
    ```

3. Configura los secretos:
    - Crea un archivo `.streamlit/secrets.toml` con las credenciales necesarias
    - Incluye las secciones `[google_oauth]` y `[mercadolibre]`

---

## Configuración de Google OAuth

### Para desarrollo local:
1. En Google Cloud Console, usa la URI de redirección `http://localhost:8501/`
2. En `.streamlit/secrets.toml` configura:
    ```toml
    [google_oauth]
    client_id = "TU_CLIENT_ID"
    client_secret = "TU_CLIENT_SECRET"
    redirect_uri = "http://localhost:8501/"
    ```

### Para producción en Render:
1. En Google Cloud, agrega la URI de tu app en Render (ej: `https://tu-app.onrender.com/`)
2. En Render, configura las variables de entorno:
    - `GOOGLE_OAUTH_CLIENT_ID`
    - `GOOGLE_OAUTH_CLIENT_SECRET`
    - `GOOGLE_OAUTH_REDIRECT_URI`
    - `MERCADOLIBRE_ACCESS_TOKEN`
3. Actualiza `.streamlit/secrets.toml` para producción:
    ```toml
    [google_oauth]
    client_id = "TU_CLIENT_ID"
    client_secret = "TU_CLIENT_SECRET"
    redirect_uri = "https://tu-app.onrender.com/"
    ```

---

## Ejecución

Para ejecutar la aplicación localmente:
```sh
streamlit run app.py
```

## Notas técnicas

### Manejo de SKUs en Mercado Libre

La aplicación busca SKUs en múltiples ubicaciones de la API de Mercado Libre:
1. Campo `seller_custom_field` (ubicación principal)
2. Campo `attribute_combinations` con ID "SELLER_SKU"
3. Campo `sku` directo de la variante

Esta búsqueda exhaustiva asegura que todas las variantes sean correctamente identificadas, incluso cuando los SKUs están almacenados en diferentes campos según el tipo de publicación.

### Procesamiento de inventario

1. Al extraer el inventario de Mercado Libre, la aplicación identifica automáticamente las publicaciones sin SKU
2. Al cargar el inventario del proveedor, se comparan los SKUs con el inventario de Mercado Libre
3. Solo se actualizan las variantes que tienen cambios en el stock
4. Las publicaciones que quedan con stock total 0 se pausan automáticamente
5. Se genera un log detallado de todas las operaciones realizadas

### Mejores prácticas

- **Siempre asigna SKUs** a todas tus publicaciones en Mercado Libre para una sincronización óptima
- Revisa las alertas de publicaciones sin SKU y corrige estas publicaciones en Mercado Libre
- Ejecuta la sincronización regularmente para mantener tu inventario actualizado
- Utiliza la auditoría de variaciones si sospechas que se han perdido variantes
