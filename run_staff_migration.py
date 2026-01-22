import mysql.connector

# Configuración de la base de datos
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)

cursor = conexion.cursor()

print("Ejecutando migración para agregar columnas necesarias...")

try:
    # Agregar no_empleado a orientadores
    try:
        cursor.execute("""
            ALTER TABLE orientadores 
            ADD COLUMN no_empleado VARCHAR(50) AFTER id
        """)
        print("✓ Columna no_empleado agregada a orientadores")
    except mysql.connector.Error as e:
        if "Duplicate column name" in str(e):
            print("✓ Columna no_empleado ya existe en orientadores")
        else:
            raise e

    # Agregar grupos_encargado a orientadores
    try:
        cursor.execute("""
            ALTER TABLE orientadores 
            ADD COLUMN grupos_encargado VARCHAR(255) AFTER apellido_materno
        """)
        print("✓ Columna grupos_encargado agregada a orientadores")
    except mysql.connector.Error as e:
        if "Duplicate column name" in str(e):
            print("✓ Columna grupos_encargado ya existe en orientadores")
        else:
            raise e

    # Agregar no_empleado a directivos
    try:
        cursor.execute("""
            ALTER TABLE directivos 
            ADD COLUMN no_empleado VARCHAR(50) AFTER id
        """)
        print("✓ Columna no_empleado agregada a directivos")
    except mysql.connector.Error as e:
        if "Duplicate column name" in str(e):
            print("✓ Columna no_empleado ya existe en directivos")
        else:
            raise e

    # Agregar puesto a directivos
    try:
        cursor.execute("""
            ALTER TABLE directivos 
            ADD COLUMN puesto VARCHAR(100) AFTER apellido_materno
        """)
        print("✓ Columna puesto agregada a directivos")
    except mysql.connector.Error as e:
        if "Duplicate column name" in str(e):
            print("✓ Columna puesto ya existe en directivos")
        else:
            raise e

    conexion.commit()
    print("\n✓ Migración completada exitosamente")
    
except Exception as e:
    print(f"\n✗ Error durante la migración: {e}")
    conexion.rollback()
finally:
    cursor.close()
    conexion.close()
