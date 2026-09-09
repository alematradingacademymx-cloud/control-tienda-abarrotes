# Sistema de Administración — Tienda de Abarrotes

App web hecha en **Streamlit** para llevar el control de una tienda de
abarrotes: inventario, ventas diarias, corte de caja, proveedores, pagos
internos/deudas, nómina y mensajería. Toda la información se guarda en un
**Google Sheet**, así que puedes abrirlo y revisarlo también directamente
desde Google Sheets si lo necesitas.

## 1. Qué incluye

- Login con dos roles: **admin** (ve y administra todo, incluyendo usuarios)
  y **encargado** (ve lo operativo del día a día: inventario, ventas, corte
  de caja y mensajería).
- **Inventario**: alta de productos por sección, stock, costo, precio de
  venta y alerta de stock mínimo.
- **Ventas diarias**: registra la venta por sección/producto y método de
  pago (efectivo, transferencia, tarjeta); descuenta automáticamente el
  inventario.
- **Corte de caja**: calcula automáticamente cuánto entró por cada medio de
  pago según las ventas del día, y compara contra el efectivo contado
  físicamente para detectar faltantes o sobrantes.
- **Proveedores**: catálogo con fechas de entrega y de pago.
- **Pagos a proveedores / deudas**: registra compras a crédito y sus
  abonos, con saldo pendiente y estatus.
- **Nómina**: catálogo de empleados y registro de pagos de sueldo.
- **Mensajería**: registro de envíos, mensajero asignado, costo y quién lo
  paga.
- **Usuarios** (solo admin): alta de nuevos usuarios y activar/desactivar
  accesos.

## 2. Cómo funciona por dentro

La app no usa una base de datos tradicional: usa **Google Sheets** como
"base de datos" a través de la librería `gspread`. Esto significa que:

- Puedes compartir la app entre tu computadora personal y la computadora
  de la tienda sin preocuparte por sincronizar archivos: todos leen y
  escriben en el mismo Google Sheet en la nube.
- Puedes abrir el Google Sheet directamente para revisar o exportar datos
  cuando quieras (por ejemplo, para hacer un reporte en Excel).
- La conexión se hace con una **cuenta de servicio** de Google Cloud (no
  con tu cuenta personal de Gmail), que es un tipo de cuenta especial para
  que programas como esta app puedan leer/escribir Google Sheets de forma
  automática y seria.

## 3. Configuración paso a paso (una sola vez)

### 3.1 Crear el proyecto en Google Cloud y la cuenta de servicio

1. Entra a [Google Cloud Console](https://console.cloud.google.com/) con tu
   cuenta de Gmail.
2. Crea un proyecto nuevo (arriba a la izquierda, "Nuevo proyecto"). Ponle
   un nombre, por ejemplo `tienda-abarrotes`.
3. En el buscador de la consola, busca **"Google Sheets API"** y haz clic
   en **Habilitar**. Haz lo mismo para **"Google Drive API"**.
4. Ve a **"APIs y servicios" → "Credenciales"**.
5. Haz clic en **"Crear credenciales" → "Cuenta de servicio"**.
6. Dale un nombre (ej. `tienda-abarrotes-bot`) y termina el asistente (los
   permisos por defecto están bien, no necesitas agregar roles).
7. Ya creada la cuenta de servicio, entra a ella, ve a la pestaña
   **"Claves" ("Keys")** → **"Agregar clave" → "Crear clave nueva"** →
   tipo **JSON**. Se descargará un archivo `.json`.
8. Renombra ese archivo a `credentials.json` y guárdalo dentro de la
   carpeta de este proyecto (junto a `app.py`). **Nunca lo compartas ni lo
   subas a un repositorio público** — con ese archivo cualquiera puede
   leer/escribir tus datos.
9. Anota el correo de la cuenta de servicio (algo como
   `tienda-abarrotes-bot@tienda-abarrotes.iam.gserviceaccount.com`), lo vas
   a necesitar en el siguiente paso.

### 3.2 Instalar dependencias

Necesitas Python 3.10 o superior instalado. Luego, dentro de la carpeta del
proyecto:

```bash
pip install -r requirements.txt
```

### 3.3 Crear y compartir el Google Sheet

Corre el script de inicialización, pasando **tu correo personal de Gmail**
(el que vas a usar para entrar a Google Sheets y ver los datos):

```bash
python setup_sheet.py tu_correo_personal@gmail.com
```

Esto va a:

- Crear un Google Sheet llamado `TiendaAbarrotes_DB`.
- Compartirlo contigo como editor (para que lo veas en tu Google Drive).
- Crear todas las pestañas necesarias (Usuarios, Inventario, Ventas, etc.)
  con sus encabezados.

Si algún día quieres agregar más pestañas o cambiar columnas, edítalas en
`config.py` (diccionario `HOJAS`) y vuelve a correr `setup_sheet.py`; las
pestañas que ya existen no se tocan, solo se agregan las que falten.

### 3.4 Correr la app localmente

```bash
streamlit run app.py
```

Se abrirá en tu navegador (normalmente `http://localhost:8501`). La
primera vez, como no hay usuarios todavía, la app te va a pedir crear el
usuario **administrador**. Después de eso, ya puedes iniciar sesión
normalmente y, desde el menú **Usuarios**, crear cuentas para tus
encargados.

## 4. Para que la tienda y tú puedan usarla desde distintos lugares

Si solo la vas a correr en una computadora, con el paso 3.4 es
suficiente. Pero como mencionaste que quieres compartirla entre tu
computadora y la de la tienda (y consultarla tú también desde la tuya), lo
más práctico es **publicar la app en internet** con
[Streamlit Community Cloud](https://streamlit.io/cloud), que es gratuito
para este tipo de proyectos:

1. Sube esta carpeta (sin `credentials.json` ni `.streamlit/secrets.toml`,
   ya excluidos en `.gitignore`) a un repositorio de GitHub.
2. Entra a [share.streamlit.io](https://share.streamlit.io/), conecta tu
   cuenta de GitHub y selecciona el repositorio. Indica `app.py` como
   archivo principal.
3. Antes de desplegar, abre **"Advanced settings" → "Secrets"** y pega el
   contenido de `.streamlit/secrets_example.toml`, pero con los valores
   reales de tu `credentials.json` (copia cada campo del JSON al formato
   TOML que ya está de ejemplo).
4. Despliega. Streamlit te da una URL pública (algo como
   `https://tu-app.streamlit.app`) — esa es la que vas a abrir tanto en la
   computadora de la tienda como en la tuya, cada quien con su usuario y
   contraseña.

Así, los datos siempre están en el mismo Google Sheet en la nube: no
importa desde qué computadora entren, todos ven la misma información
actualizada al instante.

## 5. Estructura del proyecto

```
tienda_abarrotes_app/
├── app.py                     # Punto de entrada, login y navegación
├── config.py                  # Definición de hojas/columnas y catálogos
├── auth.py                    # Login, roles y manejo de sesión
├── sheets_connector.py        # Toda la lectura/escritura a Google Sheets
├── setup_sheet.py             # Script para crear/compartir el Google Sheet
├── requirements.txt
├── .streamlit/
│   └── secrets_example.toml   # Plantilla de credenciales para despliegue
└── modules/
    ├── inicio.py               # Panel resumen
    ├── inventario.py
    ├── ventas.py
    ├── corte_caja.py
    ├── proveedores.py
    ├── pagos_proveedores.py
    ├── nomina.py
    ├── mensajeria.py
    └── usuarios.py             # Solo visible para admin
```

## 6. Notas importantes

- Las contraseñas se guardan **hasheadas** (con `bcrypt`), nunca en texto
  plano, ni siquiera en el Google Sheet.
- Google Sheets tiene un límite de cuota de aproximadamente 60
  escrituras/lecturas por minuto por usuario, más que suficiente para el
  uso normal de una tienda. Si en el futuro el negocio crece mucho y esto
  se vuelve una limitante, se puede migrar el mismo diseño a una base de
  datos real (por ejemplo PostgreSQL) sin rehacer toda la app.
- El rol **encargado** no puede eliminar productos ni ver el módulo de
  Usuarios; el rol **admin** tiene acceso completo.
- Si quieres agregar un campo nuevo a algún módulo (por ejemplo, una foto
  del producto, o un campo de "descuento"), se agrega en `config.py` y en
  el formulario correspondiente dentro de `modules/`.

## 7. Siguientes pasos sugeridos

Este es el sistema completo tal como lo pediste (inventario, ventas,
corte de caja, proveedores, pagos, nómina y mensajería). Algunas mejoras
que se pueden agregar después, cuando quieras:

- Reportes descargables (PDF/Excel) de ventas, corte de caja o nómina por
  rango de fechas.
- Gráficas de ventas por sección o por producto más vendido.
- Notificaciones automáticas (por correo o WhatsApp) cuando se acerque una
  fecha de pago a proveedores o de nómina.
- Códigos de barras para agilizar el registro de ventas.
