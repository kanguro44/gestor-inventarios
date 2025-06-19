================================================================
**Gestor de Inventario y Precios para Mercado Libre (ESPAITEC)**
================================================================

**Versión:** 1.0.0
**Fecha de última actualización:** 2025-06-19

**Descripción General**
-------------------
Esta aplicación de escritorio está diseñada para facilitar la gestión masiva de inventario y la estrategia de precios para las publicaciones de ESPAITEC Tactical & Outdoors en Mercado Libre. Permite sincronizar el stock basándose en un archivo de proveedor, calcular precios de venta competitivos y diagnosticar problemas en las publicaciones.

**Características Principales**
--------------------------
1.  **Sincronización de Inventario Segura:**
    *   Actualiza el stock de miles de publicaciones y variaciones en minutos.
    *   El sistema está "blindado": **no elimina publicaciones ni variaciones**.
    *   Pausa automáticamente las publicaciones cuyo stock total llega a cero.
    *   Maneja un umbral de seguridad (stock menor o igual a 3 se considera 0).

2.  **Calculadora de Precios de Venta:**
    *   Calcula el precio de venta final en Mercado Libre a partir del costo de mayoreo.
    *   Permite configurar parámetros clave: margen de utilidad, costo de envío, IVA y comisión de ML.
    *   Aplica reglas de negocio: redondeo hacia el entero superior y precio mínimo de $299.00 MXN.

3.  **Herramientas de Diagnóstico:**
    *   **Auditor de Variaciones Perdidas:** Compara dos reportes de inventario (uno antiguo y uno nuevo) para identificar variaciones que han desaparecido, ayudando a recuperar ventas perdidas.

**Requisitos Previos**
--------------------
*   Tener Python instalado en el sistema (versión 3.9 o superior).
*   Tener `pip` (el gestor de paquetes de Python) disponible en la línea de comandos.

**Instalación y Configuración**
-----------------------------
1.  **Instalar Dependencias:**
    Abre una terminal o línea de comandos, navega a la carpeta `inventarios` y ejecuta el siguiente comando para instalar todas las librerías necesarias:
    ```
    pip install -r requirements.txt
    ```

2.  **Configurar el Token de Acceso (`ml_token.json`):**
    Esta aplicación necesita un token para comunicarse de forma segura con la API de Mercado Libre.
    *   **Propósito:** El archivo `ml_token.json` contiene las credenciales de acceso a la API. Debe estar presente en la misma carpeta que `app.py`.
    *   **Obtención:** Este archivo se genera a través del proceso de autenticación de Mercado Libre para desarrolladores. Si el archivo se pierde o caduca, será necesario generar uno nuevo siguiendo la documentación oficial de la API de Mercado Libre.
    *   **Formato del archivo:**
        ```json
        {
          "access_token": "APP_USR-...",
          "token_type": "bearer",
          "expires_in": 21600,
          "scope": "offline_access read write",
          "user_id": 12345678,
          "refresh_token": "TG-..."
        }
        ```

**Cómo Ejecutar la Aplicación**
------------------------------
1.  Abre una terminal o línea de comandos.
2.  Asegúrate de estar en el directorio que contiene la carpeta `inventarios` (por ejemplo, el Escritorio).
3.  Ejecuta el siguiente comando:
    ```
    streamlit run inventarios/app.py
    ```
4.  La aplicación se abrirá automáticamente en tu navegador web.

**Guía de Uso Rápida**
--------------------
La aplicación está dividida en pestañas que representan un flujo de trabajo lógico.

*   **Pestaña 1: Cargar Datos**
    1.  **Inventario de Mercado Libre:** Haz clic en "Sincronizar desde Mercado Libre" para descargar la información más reciente de tus publicaciones.
    2.  **Inventario del Proveedor:** Carga el archivo Excel con las existencias actuales.

*   **Pestaña 2: Revisar y Confirmar**
    *   La aplicación mostrará un resumen de los cambios: cuántas variaciones se actualizarán y cuántas publicaciones se pausarán.
    *   Revisa la tabla de "Vista Previa de Cambios" para verificar que todo es correcto.
    *   Si estás de acuerdo, haz clic en "Confirmar y Ejecutar Sincronización". **Esta acción es irreversible.**

*   **Pestaña 3: Resultados**
    *   Aquí verás un resumen de las actualizaciones exitosas y los errores.
    *   Un registro detallado te mostrará el resultado para cada publicación procesada.

*   **Pestaña 4: Calculadora de Precios**
    1.  Sube tu catálogo maestro que contenga la columna "PRECIO MAYOREO".
    2.  Ajusta los parámetros (utilidad, envío, etc.).
    3.  Los resultados se mostrarán en una tabla.
    4.  Descarga el catálogo completo con los precios de venta sugeridos.

*   **Pestaña 5: Herramientas de Recuperación**
    1.  Usa el "Auditor de Variaciones Perdidas" para diagnosticar problemas.
    2.  Carga un archivo de inventario de respaldo (antes del problema) y el archivo actual.
    3.  La herramienta generará un reporte con las variaciones que faltan.
