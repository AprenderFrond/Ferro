import sqlite3
from flask import Flask, url_for, flash,  session, render_template, request, redirect, jsonify
from datetime import datetime 
from functools import wraps

app = Flask(__name__)
app.secret_key = 'clave_secreta_ferreteria_la_clinica'

# Decorador para proteger cualquier pantalla
def login_requerido(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Ruta del Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        password = request.form.get('password')
        
        conexion = conectar_bd()
        user = conexion.execute('SELECT * FROM usuarios WHERE usuario = ? AND password = ?', 
                                (usuario, password)).fetchone()
        conexion.close()
        
        if user:
            session['usuario'] = user[1]
            return redirect(url_for('pantalla_ventas'))  # O la ruta principal de tu app
        else:
            flash('Usuario o contraseña incorrectos', 'danger')
            
    return render_template('login.html')

# Ruta para cerrar sesión
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==============================================================================
# CONFIGURACIÓN Y CONEXIÓN A LA BASE DE DATOS
# ==============================================================================
def conectar_bd():
    conexion = sqlite3.connect('ferreteria.db')
    conexion.row_factory = sqlite3.Row  # Permite acceder a las columnas por nombre
    return conexion


# ==============================================================================
# RUTA PRINCIPAL: VER INVENTARIO Y CONFIGURACIÓN INICIAL
# ==============================================================================
@app.route('/')
@login_requerido
def inicio():
    conexion = conectar_bd()
    
    # 1. Crear tablas de Ventas y Detalles si no existen (Estructura base)
    conexion.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente TEXT DEFAULT 'Consumidor Final',
            total REAL NOT NULL,
            fecha TEXT NOT NULL
        )
    ''')
    
    # PARCHE AUTOMÁTICO: Si la tabla ventas ya existía pero no tenía la columna 'cliente', la agregamos
    try:
        conexion.execute('ALTER TABLE ventas ADD COLUMN cliente TEXT DEFAULT "Consumidor Final";')
        conexion.commit()
    except sqlite3.OperationalError:
        pass

    conexion.execute('''
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER NOT NULL,
            producto_id INTEGER NOT NULL,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            FOREIGN KEY (venta_id) REFERENCES ventas(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')
    
    # Asegurar que existan categorías base si la tabla está vacía
    try:
        categorias_existentes = conexion.execute('SELECT COUNT(*) as total FROM categorias').fetchone()
        if categorias_existentes['total'] == 0:
            categorias_base = [('Eléctricos',), ('Grifería',), ('Duchas',), ('Herramientas',), ('Pinturas',)]
            conexion.executemany('INSERT INTO categorias (nombre) VALUES (?)', categorias_base)
            conexion.commit()
    except sqlite3.OperationalError:
        pass
        
    conexion.close()

    # 2. Traer los datos limpios para la interfaz de inventario
    conexion = conectar_bd()
    categorias = conexion.execute('SELECT * FROM categorias ORDER BY nombre ASC').fetchall()
    productos = conexion.execute('''
        SELECT p.*, c.nombre as categoria_nombre 
        FROM productos p 
        LEFT JOIN categorias c ON p.categoria_id = c.id
        ORDER BY p.id DESC
    ''').fetchall()
    conexion.close()
    
    return render_template('inventario.html', productos=productos, categories=categorias)


# ==============================================================================
# MÓDULO DE GESTIÓN DE PRODUCTOS (INVENTARIO)
# ==============================================================================
@app.route('/guardar_producto', methods=['POST'])
@login_requerido
def guardar_producto():
    nombre = request.form.get('nombre')
    categoria_id = request.form.get('categoria_id')
    precio = request.form.get('precio')
    stock = request.form.get('stock')
    codigo_barras = request.form.get('codigo_barras')

    conexion = conectar_bd()
    try:
        conexion.execute('''
            INSERT INTO productos (nombre, categoria_id, precio, stock, codigo_barras)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, categoria_id, precio, stock, codigo_barras))
    except sqlite3.OperationalError:
        conexion.execute('''
            INSERT INTO productos (nombre, category_id, precio, stock, codigo_barras)
            VALUES (?, ?, ?, ?, ?)
        ''', (nombre, categoria_id, precio, stock, codigo_barras))
        
    conexion.commit()
    conexion.close()
    
    return redirect('/')


@app.route('/editar_producto/<int:id>', methods=['POST'])
@login_requerido

def editar_producto(id):
    nombre = request.form.get('nombre')
    categoria_id = request.form.get('categoria_id')
    precio = request.form.get('precio')
    stock = request.form.get('stock')
    codigo_barras = request.form.get('codigo_barras')

    conexion = conectar_bd()
    
    # Inspeccionamos las columnas reales de la tabla productos
    cursor = conexion.execute('SELECT * FROM productos LIMIT 1')
    columnas = [desc[0].lower() for desc in cursor.description]
    
    # Construimos la consulta UPDATE dinámicamente según lo que sí existe en la BD
    campos = []
    valores = []
    
    if 'nombre' in columnas:
        campos.append("nombre = ?")
        valores.append(nombre)
        
    if 'precio' in columnas:
        campos.append("precio = ?")
        valores.append(precio)
        
    if 'stock' in columnas:
        campos.append("stock = ?")
        valores.append(stock)
        
    # Verificamos cuál de los nombres de categoría existe en tu base de datos
    if 'categoria_id' in columnas:
        campos.append("categoria_id = ?")
        valores.append(categoria_id)
    elif 'category_id' in columnas:
        campos.append("category_id = ?")
        valores.append(categoria_id)
    elif 'id_categoria' in columnas:
        campos.append("id_categoria = ?")
        valores.append(categoria_id)

    if 'codigo_barras' in columnas:
        campos.append("codigo_barras = ?")
        valores.append(codigo_barras)
    elif 'codigo' in columnas:
        campos.append("codigo = ?")
        valores.append(codigo_barras)

    # Añadimos el ID al final para la cláusula WHERE
    valores.append(id)
    
    sql_query = f"UPDATE productos SET {', '.join(campos)} WHERE id = ?"
    
    try:
        conexion.execute(sql_query, valores)
        conexion.commit()
    except Exception as e:
        print(f"Error al editar: {e}")
    finally:
        conexion.close()
    
    return redirect('/')


# ==============================================================================
# MÓDULO DE VENTAS (PANTALLA)
# ==============================================================================
@app.route('/ventas')
@login_requerido

def pantalla_ventas():
    return render_template('ventas.html')

# ==============================================================================
# BUSCADOR COMPLETO CON DETECCIÓN DE TIPOS Y BACKUP SENSATO
# ==============================================================================
@app.route('/api/buscar_producto')
@login_requerido

def buscar_producto():
    q = request.args.get('q', '')
    conexion = conectar_bd()
    
    # 1. Primero miramos qué columnas reales existen en tu tabla para evitar errores
    cursor = conexion.execute('SELECT * FROM productos LIMIT 1')
    columnas = [desc[0].lower() for desc in cursor.description]
    
    # 2. Identificamos cómo se llama la columna del código en tu BD
    columna_codigo = 'codigo_barras' if 'codigo_barras' in columnas else ('codigo' if 'codigo' in columnas else None)
    
    # 3. Construimos la consulta SQL para que busque por Nombre O por Código
    if columna_codigo:
        sql = f'''
            SELECT * FROM productos 
            WHERE nombre LIKE ? OR {columna_codigo} LIKE ?
        '''
        parametros = (f'%{q}%', f'%{q}%')
    else:
        sql = 'SELECT * FROM productos WHERE nombre LIKE ?'
        parametros = (f'%{q}%',)
        
    # 4. Ejecutamos la búsqueda real con los filtros aplicados
    cursor = conexion.execute(sql, parametros)
    productos = cursor.fetchall()
    conexion.close()
    
    lista = []
    for p in productos:
        fila = list(p)
        
        # 1. ID
        p_id = fila[columnas.index('id')] if 'id' in columnas else fila[0]
        
        # 2. NOMBRE (Buscamos la columna texto más larga o por índice)
        p_nombre = ""
        if 'nombre' in columnas:
            p_nombre = fila[columnas.index('nombre')]
        else:
            textos = [x for x in fila if isinstance(x, str)]
            p_nombre = textos[0] if textos else fila[1]

        # 3. PRECIO Y STOCK (Detección inteligente por exclusión)
        p_precio = None
        p_stock = None
        
        # Intentamos primero por nombre directo de columna
        if 'precio' in columnas:
            p_precio = fila[columnas.index('precio')]
        if 'stock' in columnas:
            p_stock = fila[columnas.index('stock')]
            
        # Si siguen vacíos o incoherentes, analizamos numéricamente
        numeros = []
        for i, val in enumerate(fila):
            if i != (columnas.index('id') if 'id' in columnas else 0):
                try:
                    # Si es almacenable como número y no es igual al ID
                    if val is not None and not isinstance(val, str):
                        numeros.append(float(val))
                except:
                    pass
                    
        if p_precio is None or p_precio == 0:
            # El precio suele ser el número más alto (ej: 15000 vs 12 unidades de stock)
            p_precio = max(numeros) if numeros else 0.0
        if p_stock is None or p_stock == 0:
            p_stock = min(numeros) if numeros else 0
            
        # Si el máximo y mínimo dieron el mismo número, reajustamos con prudencia
        if p_precio == p_stock and len(numeros) > 1:
            p_stock = numeros[1]

        # 4. CÓDIGO DE BARRAS
        p_codigo = ""
        if 'codigo_barras' in columnas:
            p_codigo = fila[columnas.index('codigo_barras')]
        elif 'codigo' in columnas:
            p_codigo = fila[columnas.index('codigo')]
            
        if not p_codigo or str(p_codigo) == str(p_precio) or str(p_codigo) == str(p_nombre):
            p_codigo = f"{p_id:03d}"

        lista.append({
            'id': int(p_id),
            'nombre': str(p_nombre),
            'precio': float(p_precio) if p_precio else 0.0,
            'stock': int(p_stock) if p_stock else 0,
            'codigo_barras': str(p_codigo)
        })
        
    return jsonify(lista)

# ==============================================================================
# PROCESAR TRANSACCIÓN DE VENTA
# ==============================================================================
@app.route('/api/procesar_venta', methods=['POST'])
@login_requerido

def procesar_venta():
    datos = request.get_json()
    
    if not datos or 'productos' not in datos or len(datos['productos']) == 0:
        return jsonify({'success': False, 'message': 'No hay productos en la venta.'})
        
    try:
        conexion = conectar_bd()
        cursor = conexion.cursor()
        
        cursor.execute('''
            INSERT INTO ventas (cliente, total, fecha) 
            VALUES (?, ?, ?)
        ''', (datos.get('cliente', 'Consumidor Final'), datos['total'], datos['fecha']))
        
        venta_id = cursor.lastrowid
        
        for p in datos['productos']:
            cursor.execute('''
                INSERT INTO detalle_ventas (venta_id, producto_id, cantidad, precio_unitario)
                VALUES (?, ?, ?, ?)
            ''', (venta_id, p['id'], p['cantidad'], p['precio']))
            
            cursor.execute('''
                UPDATE productos 
                SET stock = stock - ? 
                WHERE id = ?
            ''', (p['cantidad'], p['id']))
            
        conexion.commit()
        conexion.close()
        
        return jsonify({'success': True, 'venta_id': venta_id})
        
    except Exception as e:
        if 'conexion' in locals():
            conexion.rollback()
            conexion.close()
        return jsonify({'success': False, 'message': str(e)})


# ==============================================================================
# MÓDULO DE REPORTE E HISTORIAL DE VENTAS
# ==============================================================================
@app.route('/historial')
@login_requerido

def historial_ventas():
    conexion = conectar_bd()
    ventas = conexion.execute('''
        SELECT id, cliente, total, fecha 
        FROM ventas 
        ORDER BY id DESC
    ''').fetchall()
    conexion.close()
    return render_template('historial.html', ventas=ventas)


@app.route('/api/detalle_venta/<int:venta_id>')
@login_requerido

def api_detalle_venta(venta_id):
    conexion = conectar_bd()
    detalles = conexion.execute('''
        SELECT dv.cantidad, dv.precio_unitario, p.nombre 
        FROM detalle_ventas dv
        JOIN productos p ON dv.producto_id = p.id
        WHERE dv.venta_id = ?
    ''', (venta_id,)).fetchall()
    conexion.close()
    
    lista_detalles = []
    for d in detalles:
        lista_detalles.append({
            'nombre': d['nombre'],
            'cantidad': d['cantidad'],
            'precio': d['precio_unitario'],
            'subtotal': d['cantidad'] * d['precio_unitario']
        })
    return jsonify(lista_detalles)


# ==============================================================================
# VISTA DE IMPRESIÓN FORMATO FACTURA ELECTRÓNICA DE VENTA
# ==============================================================================
@app.route('/historial/imprimir/<int:venta_id>')
@login_requerido

def imprimir_factura(venta_id):
    conexion = conectar_bd()
    
    venta = conexion.execute('SELECT * FROM ventas WHERE id = ?', (venta_id,)).fetchone()
    if not venta:
        conexion.close()
        return "Factura no encontrada", 404
        
    detalles = conexion.execute('''
        SELECT dv.cantidad, dv.precio_unitario, p.nombre, p.id as prod_codigo
        FROM detalle_ventas dv
        JOIN productos p ON dv.producto_id = p.id
        WHERE dv.venta_id = ?
    ''', (venta_id,)).fetchall()
    
    conexion.close()

    total = venta['total']
    subtotal = total / 1.19
    iva = total - subtotal

    return render_template('imprimir_factura.html', venta=venta, detalles=detalles, subtotal=subtotal, iva=iva)

# ==============================================================================
# MÓDULO DE REPORTES Y ESTADÍSTICAS (CIERRE DE CAJA)
# ==============================================================================

@app.route('/reportes')
@login_requerido

def vista_reportes():
    # Renderiza la plantilla base de los reportes
    return render_template('reportes.html')


@app.route('/api/obtener_reportes')
@login_requerido

def obtener_reportes():
    # Capturamos los filtros de fecha (si no vienen, por defecto calculamos el día de hoy)
    fecha_inicio = request.args.get('inicio', '')
    fecha_fin = request.args.get('fin', '')
    
    # Si las fechas vienen vacías desde el cliente, tomamos la fecha actual en formato YYYY-MM-DD
    from datetime import datetime
    hoy_str = datetime.now().strftime('%Y-%m-%d')
    
    if not fecha_inicio:
        fecha_inicio = hoy_str
    if not fecha_fin:
        fecha_fin = hoy_str

    conexion = conectar_bd()
    
    # 1. Total Ventas y Cantidad de Facturas en el rango de fecha elegido
    # Usamos date() en SQL para extraer solo la fecha si en la BD se guarda con hora (YYYY-MM-DD HH:MM:SS)
    query_total = '''
        SELECT COALESCE(SUM(total), 0) as ingresos_totales, COUNT(id) as total_facturas 
        FROM ventas 
        WHERE date(fecha) BETWEEN date(?) AND date(?)
    '''
    res_total = conexion.execute(query_total, (fecha_inicio, fecha_fin)).fetchone()
    ingresos = res_total[0]
    facturas = res_total[1]
    

# ==============================================================================
    # 2. Productos Más Vendidos (Top 5) - Estructura Exacta de la BD
    # ==============================================================================
    query_top = '''
        SELECT p.nombre, SUM(dv.cantidad) as total_unidades, SUM(dv.cantidad * dv.precio_unitario) as total_dinero
        FROM detalle_ventas dv
        JOIN ventas v ON dv.venta_id = v.id
        JOIN productos p ON dv.producto_id = p.id
        WHERE date(v.fecha) BETWEEN date(?) AND date(?)
        GROUP BY dv.producto_id, p.nombre
        ORDER BY total_unidades DESC
        LIMIT 5
    '''
    
    res_top = conexion.execute(query_top, (fecha_inicio, fecha_fin)).fetchall()
    
    top_productos = []
    for fila in res_top:
        top_productos.append({
            'nombre': fila[0],
            'unidades': fila[1],
            'total_generado': fila[2]
        })
    # 3. Listado resumido de facturas del periodo para el cuadre
    query_lista = '''
        SELECT id, fecha, cliente, total 
        FROM ventas 
        WHERE date(fecha) BETWEEN date(?) AND date(?)
        ORDER BY id DESC
    '''
    res_lista = conexion.execute(query_lista, (fecha_inicio, fecha_fin)).fetchall()
    
    listado_ventas = []
    for fila in res_lista:
        listado_ventas.append({
            'id': fila[0],
            'fecha': fila[1],
            'cliente': fila[2],
            'total': fila[3]
        })

    conexion.close()
    
    # Retornamos todo empaquetado en un JSON para que JavaScript lo procese sin recargar
    return jsonify({
        'rango': {'inicio': fecha_inicio, 'fin': fecha_fin},
        'ingresos_totales': ingresos,
        'total_facturas': facturas,
        'top_productos': top_productos,
        'ventas': listado_ventas
    })


import json

@app.route('/imprimir_cotizacion', methods=['POST'])
@login_requerido

def imprimir_cotizacion():
    cliente = request.form.get('cliente', 'Consumidor Final')
    productos_json = request.form.get('productos', '[]')
    
    # Decodificamos los productos enviados desde el navegador
    productos_cotizados = json.loads(productos_json)
    
    # Calculamos el total de la cotización
    total = 0
    for p in productos_cotizados:
        # Aseguramos de mapear cómo se llaman tus variables en el JS (ej: precio o precio_venta)
        precio = p.get('precio_venta') or p.get('precio') or 0.0
        cantidad = p.get('cantidad', 1)
        p['subtotal'] = float(precio) * int(cantidad)
        p['precio_formateado'] = float(precio)
        total += p['subtotal']
        
    from datetime import datetime
    fecha_hoy = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    return render_template('imprimir_cotizacion.html', 
                           cliente=cliente, 
                           productos=productos_cotizados, 
                           total=total, 
                           fecha=fecha_hoy)

# ==============================================================================
# ARRANQUE DEL SERVIDOR
# ==============================================================================
if __name__ == '__main__':
    app.run(debug=True, port=5000)