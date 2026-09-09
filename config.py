"""
Configuración central de la app: nombres de hojas, columnas, catálogos fijos.
Aquí se define la "estructura de base de datos" que vive en Google Sheets.
"""

# Nombre del documento de Google Sheets (debe existir y estar compartido
# con el correo de la cuenta de servicio, ver README.md)
NOMBRE_SPREADSHEET = "TiendaAbarrotes_DB"

# ---------------------------------------------------------------------------
# Definición de hojas (tabs) y sus columnas, en el orden en que deben existir
# en el Google Sheet. setup_sheet.py usa esto para crear las hojas.
# ---------------------------------------------------------------------------

HOJAS = {
    "Usuarios": [
        "usuario", "nombre_completo", "password_hash", "rol", "activo",
    ],
    "Inventario": [
        "id_producto", "nombre_producto", "seccion", "unidad",
        "costo_unitario", "precio_venta", "stock_actual", "stock_minimo",
        "proveedor", "fecha_actualizacion", "codigo_barras",
    ],
    "Ventas": [
        "id_venta", "fecha", "hora", "usuario", "seccion", "id_producto",
        "producto", "cantidad", "precio_unitario", "total", "metodo_pago",
        "turno", "costo_unitario", "ganancia",
    ],
    "CorteCaja": [
        "id_corte", "fecha", "turno", "usuario",
        "total_efectivo_sistema", "total_transferencia_sistema",
        "total_tarjeta_sistema", "total_ventas_sistema",
        "efectivo_contado", "diferencia", "observaciones", "hora_cierre",
    ],
    "Proveedores": [
        "id_proveedor", "nombre", "contacto", "telefono",
        "productos_que_surte", "dia_entrega", "dia_pago",
        "condiciones", "activo",
    ],
    "PagosProveedores": [
        "id_pago", "id_proveedor", "proveedor", "fecha_compra", "concepto",
        "monto_total", "monto_pagado", "saldo_pendiente",
        "fecha_pago_programada", "estatus", "metodo_pago",
    ],
    "Nomina": [
        "id_empleado", "nombre", "puesto", "sueldo_periodo",
        "periodicidad", "fecha_pago_programada", "activo",
    ],
    "PagosNomina": [
        "id_pago", "id_empleado", "empleado", "periodo", "fecha_pago",
        "monto_pagado", "metodo_pago", "estatus",
    ],
    "Mensajeria": [
        "id_envio", "fecha", "cliente_pedido", "mensajero", "direccion_zona",
        "costo_envio", "metodo_pago_envio", "quien_paga", "estatus",
        "usuario_registro",
    ],
}

ROLES = ["admin", "encargado"]

METODOS_PAGO = ["Efectivo", "Transferencia", "Tarjeta"]

SECCIONES_DEFAULT = [
    "Abarrotes", "Lácteos", "Bebidas", "Botanas", "Limpieza",
    "Higiene personal", "Panadería", "Frutas y verduras", "Congelados", "Otros",
]

# Unidades de venta para productos que se venden por peso/fracción (ej. queso,
# jamón, granos a granel) además de los que se venden por pieza completa.
UNIDADES_VENTA = ["Pieza", "Kilo", "Medio kilo (500g)", "Cuarto de kilo (250g)"]

# Etiquetas de los campos de precio/costo/stock según la unidad elegida, para
# que el formulario de Inventario sea más claro (ej. "Precio por kilo" en vez
# de un genérico "Precio de venta" que no dice si es por pieza o por peso).
ETIQUETAS_UNIDAD = {
    "Pieza": {
        "precio": "Precio de venta (por pieza)",
        "costo": "Costo unitario (por pieza)",
        "stock": "Stock inicial (piezas)",
        "stock_min": "Stock mínimo (piezas)",
        "ajuste": "Ajustar stock (+ entrada / - salida, piezas)",
    },
    "Kilo": {
        "precio": "Precio por kilo",
        "costo": "Costo por kilo",
        "stock": "Stock inicial (kilos)",
        "stock_min": "Stock mínimo (kilos)",
        "ajuste": "Ajustar stock (+ entrada / - salida, kilos)",
    },
    "Medio kilo (500g)": {
        "precio": "Precio por medio kilo",
        "costo": "Costo por medio kilo",
        "stock": "Stock inicial (medios kilos)",
        "stock_min": "Stock mínimo (medios kilos)",
        "ajuste": "Ajustar stock (+ entrada / - salida, medios kilos)",
    },
    "Cuarto de kilo (250g)": {
        "precio": "Precio por cuarto de kilo",
        "costo": "Costo por cuarto de kilo",
        "stock": "Stock inicial (cuartos de kilo)",
        "stock_min": "Stock mínimo (cuartos de kilo)",
        "ajuste": "Ajustar stock (+ entrada / - salida, cuartos de kilo)",
    },
}

PERIODICIDAD_NOMINA = ["Semanal", "Quincenal", "Mensual"]

ESTATUS_PAGO = ["Pendiente", "Parcial", "Pagado"]

ESTATUS_ENVIO = ["Pendiente", "En camino", "Entregado", "Cancelado"]

QUIEN_PAGA_ENVIO = ["Cliente", "Tienda"]

# Menú y permisos por rol: qué secciones ve cada rol en la barra lateral
MENU_POR_ROL = {
    "admin": [
        "Inicio", "Inventario", "Ventas diarias", "Corte de caja",
        "Proveedores", "Pagos a proveedores", "Nómina", "Mensajería",
        "Usuarios",
    ],
    "encargado": [
        "Inicio", "Inventario", "Ventas diarias", "Corte de caja",
        "Mensajería",
    ],
}
