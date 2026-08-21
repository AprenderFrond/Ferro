import sqlite3

def inicializar_bd():
    # Se conecta (o crea) el archivo local de la base de datos
    conexion = sqlite3.connect('ferreteria.db')
    cursor = conexion.cursor()
    
    # 1. Tabla de Categorías
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL UNIQUE
        )
    ''')
    
    # 2. Tabla de Productos (Relacionada con Categorías)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo_barras TEXT UNIQUE,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            precio_compra REAL NOT NULL,
            precio_venta REAL NOT NULL,
            stock INTEGER NOT NULL DEFAULT 0,
            stock_minimo INTEGER NOT NULL DEFAULT 5,
            categoria_id INTEGER,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    ''')
    
    # 3. Tabla de Ventas (Cabecera de la Factura)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total REAL NOT NULL DEFAULT 0.0
        )
    ''')
    
    # 4. Tabla de Detalle de Ventas (Productos por Factura)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS detalle_ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            producto_id INTEGER,
            cantidad INTEGER NOT NULL,
            precio_unitario REAL NOT NULL,
            FOREIGN KEY (venta_id) REFERENCES ventas(id),
            FOREIGN KEY (producto_id) REFERENCES productos(id)
        )
    ''')
    
     # 5. Tabla de Usuarios para el Login
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            usuario TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    
    # Creamos un usuario administrador por defecto si no existe
    cursor.execute('''
        INSERT OR IGNORE INTO usuarios (id, usuario, password)
        VALUES (1, 'admin', '12345')
    ''')
    
    conexion.commit()
    conexion.close()
    print("¡Base de datos y tablas creadas con éxito!")
    
   

if __name__ == '__main__':
    inicializar_bd()