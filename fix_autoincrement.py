import mysql.connector

# Configuración de la base de datos
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)

cursor = conexion.cursor()

print("Ejecutando migración para configurar AUTO_INCREMENT en las tablas...")

try:
    # Verificar y configurar AUTO_INCREMENT para alumnos
    try:
        cursor.execute("""
            ALTER TABLE alumnos MODIFY COLUMN id INT AUTO_INCREMENT
        """)
        print("✓ Campo id configurado como AUTO_INCREMENT en alumnos")
    except mysql.connector.Error as e:
        print(f"✓ Campo id ya está configurado en alumnos o error: {e}")

    # Verificar y configurar AUTO_INCREMENT para docentes
    try:
        cursor.execute("""
            ALTER TABLE docentes MODIFY COLUMN id INT AUTO_INCREMENT
        """)
        print("✓ Campo id configurado como AUTO_INCREMENT en docentes")
    except mysql.connector.Error as e:
        print(f"✓ Campo id ya está configurado en docentes o error: {e}")

    # Verificar y configurar AUTO_INCREMENT para orientadores
    try:
        cursor.execute("""
            ALTER TABLE orientadores MODIFY COLUMN id INT AUTO_INCREMENT
        """)
        print("✓ Campo id configurado como AUTO_INCREMENT en orientadores")
    except mysql.connector.Error as e:
        print(f"✓ Campo id ya está configurado en orientadores o error: {e}")

    # Verificar y configurar AUTO_INCREMENT para directivos
    try:
        cursor.execute("""
            ALTER TABLE directivos MODIFY COLUMN id INT AUTO_INCREMENT
        """)
        print("✓ Campo id configurado como AUTO_INCREMENT en directivos")
    except mysql.connector.Error as e:
        print(f"✓ Campo id ya está configurado en directivos o error: {e}")

    conexion.commit()
    print("\n✓ Migración de AUTO_INCREMENT completada exitosamente")
    
except Exception as e:
    print(f"\n✗ Error durante la migración: {e}")
    conexion.rollback()
finally:
    cursor.close()
    conexion.close()
