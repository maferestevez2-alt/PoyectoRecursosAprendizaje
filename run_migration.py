import mysql.connector

# Database connection
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)

cursor = conexion.cursor()

print("Running database migration...")

# 1. Add columns to usuarios table
try:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN perfil_id INT")
    print("✓ Added perfil_id column to usuarios")
except Exception as e:
    print(f"  perfil_id column might already exist: {e}")

try:
    cursor.execute("ALTER TABLE usuarios ADD COLUMN nombre_completo VARCHAR(255)")
    print("✓ Added nombre_completo column to usuarios")
except Exception as e:
    print(f"  nombre_completo column might already exist: {e}")

# 2. Add columns to recursos table
try:
    cursor.execute("ALTER TABLE recursos ADD COLUMN grupo VARCHAR(10)")
    print("✓ Added grupo column to recursos")
except Exception as e:
    print(f"  grupo column might already exist: {e}")

try:
    cursor.execute("ALTER TABLE recursos ADD COLUMN semestre INT")
    print("✓ Added semestre column to recursos")
except Exception as e:
    print(f"  semestre column might already exist: {e}")

try:
    cursor.execute("ALTER TABLE recursos ADD COLUMN turno VARCHAR(20)")
    print("✓ Added turno column to recursos")
except Exception as e:
    print(f"  turno column might already exist: {e}")

# 3. Create materias_asignadas table
try:
    cursor.execute("""
        CREATE TABLE materias_asignadas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre_materia VARCHAR(255),
            semestre INT,
            no_empleado INT,
            grupo VARCHAR(10),
            INDEX idx_empleado (no_empleado),
            INDEX idx_grupo (grupo),
            INDEX idx_semestre (semestre)
        )
    """)
    print("✓ Created materias_asignadas table")
except Exception as e:
    print(f"  materias_asignadas table might already exist: {e}")

conexion.commit()

# 4. Update existing usuarios with their full names
print("\nUpdating user full names...")

# For students (alumnos)
try:
    cursor.execute("""
        UPDATE usuarios u
        INNER JOIN alumnos a ON u.usuario = a.no_control
        SET u.nombre_completo = CONCAT(a.nombre, ' ', a.apellido_paterno, ' ', IFNULL(a.apellido_materno, '')),
            u.perfil_id = a.id
        WHERE u.rol = 'alumno'
    """)
    print(f"✓ Updated {cursor.rowcount} student names")
except Exception as e:
    print(f"  Error updating student names: {e}")

# For teachers (docentes)
try:
    cursor.execute("""
        UPDATE usuarios u
        INNER JOIN docentes d ON u.usuario = d.no_empleado
        SET u.nombre_completo = CONCAT(d.nombre, ' ', d.apellido_paterno, ' ', IFNULL(d.apellido_materno, '')),
            u.perfil_id = d.id
        WHERE u.rol = 'docente'
    """)
    print(f"✓ Updated {cursor.rowcount} teacher names")
except Exception as e:
    print(f"  Error updating teacher names: {e}")

# For orientadores
try:
    cursor.execute("""
        UPDATE usuarios u
        INNER JOIN orientadores o ON CAST(u.usuario AS UNSIGNED) = o.id
        SET u.nombre_completo = CONCAT(o.nombre, ' ', o.apellido_paterno, ' ', IFNULL(o.apellido_materno, '')),
            u.perfil_id = o.id
        WHERE u.rol = 'orientador'
    """)
    print(f"✓ Updated {cursor.rowcount} orientador names")
except Exception as e:
    print(f"  Error updating orientador names: {e}")

# For directivos
try:
    cursor.execute("""
        UPDATE usuarios u
        INNER JOIN directivos d ON CAST(u.usuario AS UNSIGNED) = d.id
        SET u.nombre_completo = CONCAT(d.nombre, ' ', d.apellido_paterno, ' ', IFNULL(d.apellido_materno, '')),
            u.perfil_id = d.id
        WHERE u.rol = 'directivo'
    """)
    print(f"✓ Updated {cursor.rowcount} directivo names")
except Exception as e:
    print(f"  Error updating directivo names: {e}")

conexion.commit()
cursor.close()
conexion.close()

print("\n✅ Database migration completed successfully!")
