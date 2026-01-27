from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import mysql.connector
import os
import random
from werkzeug.utils import secure_filename
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "super_clave_segura"

# Configuración para subir archivos
UPLOAD_FOLDER = os.path.join('static', 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------- CONEXIÓN BASE DE DATOS -------------------
conexion = mysql.connector.connect(
    host="localhost",
    user="root",
    password="",
    database="proyecto"
)

# ==============================================================
#                FUNCIONES DE SEGURIDAD DE LOGIN
# ==============================================================

def check_user_lockout(usuario):
    """Verifica si el usuario está bloqueado y retorna el estado"""
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT intentos, bloqueado_hasta 
        FROM login_attempts 
        WHERE usuario=%s
    """, (usuario,))
    record = cursor.fetchone()
    cursor.close()
    
    if not record:
        return False, None
    
    if record['bloqueado_hasta']:
        if datetime.now() < record['bloqueado_hasta']:
            tiempo_restante = record['bloqueado_hasta'] - datetime.now()
            minutos = int(tiempo_restante.total_seconds() / 60)
            return True, minutos
        else:
            # El bloqueo ya expiró, limpiamos el registro
            cursor = conexion.cursor()
            cursor.execute("""
                UPDATE login_attempts 
                SET intentos=0, bloqueado_hasta=NULL 
                WHERE usuario=%s
            """, (usuario,))
            conexion.commit()
            cursor.close()
            return False, None
    
    return False, None

def record_failed_attempt(usuario):
    """Registra un intento fallido y bloquea si alcanza 4 intentos"""
    cursor = conexion.cursor(dictionary=True)
    
    # Verificar si existe el registro
    cursor.execute("SELECT intentos FROM login_attempts WHERE usuario=%s", (usuario,))
    record = cursor.fetchone()
    
    if record:
        nuevos_intentos = record['intentos'] + 1
        if nuevos_intentos >= 4:
            # Bloquear por 15 minutos
            bloqueado_hasta = datetime.now() + timedelta(minutes=15)
            cursor.execute("""
                UPDATE login_attempts 
                SET intentos=%s, bloqueado_hasta=%s, ultima_actualizacion=NOW() 
                WHERE usuario=%s
            """, (nuevos_intentos, bloqueado_hasta, usuario))
        else:
            cursor.execute("""
                UPDATE login_attempts 
                SET intentos=%s, ultima_actualizacion=NOW() 
                WHERE usuario=%s
            """, (nuevos_intentos, usuario))
    else:
        # Crear nuevo registro
        cursor.execute("""
            INSERT INTO login_attempts (usuario, intentos, ultima_actualizacion) 
            VALUES (%s, 1, NOW())
        """, (usuario,))
    
    conexion.commit()
    cursor.close()

def clear_login_attempts(usuario):
    """Limpia los intentos fallidos después de un login exitoso"""
    cursor = conexion.cursor()
    cursor.execute("""
        DELETE FROM login_attempts WHERE usuario=%s
    """, (usuario,))
    conexion.commit()
    cursor.close()

def generar_password_8digitos():
    """Genera una contraseña aleatoria de 8 dígitos"""
    return ''.join([str(random.randint(0, 9)) for _ in range(8)])

# ==============================================================
#                      LOGIN / CUENTAS
# ==============================================================

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        usuario = request.form["usuario"]
        password = request.form["password"]
        
        # Verificar si el usuario está bloqueado
        is_locked, minutos_restantes = check_user_lockout(usuario)
        if is_locked:
            flash(f"Usuario bloqueado. Intentos fallidos excedidos. Intente nuevamente en {minutos_restantes} minuto(s).", "error")
            return render_template("login.html")

        cursor = conexion.cursor(dictionary=True)
        user = None
        rol = None
        nombre_completo = None
        perfil_id = None
        
        # Intentar login como ALUMNO (usuario: no_control, password: curp)
        cursor.execute("SELECT * FROM alumnos WHERE no_control=%s", (usuario,))
        alumno = cursor.fetchone()
        
        if alumno and alumno["curp"] == password:
            user = alumno
            rol = "alumno"
            nombre_completo = f"{alumno['nombre']} {alumno['apellido_paterno']} {alumno['apellido_materno']}"
            perfil_id = alumno['id']
        
        # Si no es alumno, intentar login como DOCENTE 
        # (usuario: nombre apellido_paterno apellido_materno, password: no_empleado)
        if not user:
            cursor.execute("SELECT * FROM docentes")
            docentes = cursor.fetchall()
            
            for docente in docentes:
                nombre_usuario = f"{docente['nombre']} {docente['apellido_paterno']} {docente['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower() and docente["no_empleado"] == password:
                    user = docente
                    rol = "docente"
                    nombre_completo = nombre_usuario
                    perfil_id = docente['id']
                    break
        
        # Si no es docente, intentar login como ORIENTADOR
        # (usuario: nombre apellido_paterno apellido_materno, password: no_empleado)
        if not user:
            cursor.execute("SELECT * FROM orientadores")
            orientadores = cursor.fetchall()
            
            for orientador in orientadores:
                nombre_usuario = f"{orientador['nombre']} {orientador['apellido_paterno']} {orientador['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower() and orientador["no_empleado"] == password:
                    user = orientador
                    rol = "orientador"
                    nombre_completo = nombre_usuario
                    perfil_id = orientador['id']
                    break
        
        # Si no es orientador, intentar login como DIRECTIVO
        # (usuario: nombre apellido_paterno apellido_materno, password: no_empleado)
        if not user:
            cursor.execute("SELECT * FROM directivos")
            directivos = cursor.fetchall()
            
            for directivo in directivos:
                nombre_usuario = f"{directivo['nombre']} {directivo['apellido_paterno']} {directivo['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower() and directivo["no_empleado"] == password:
                    user = directivo
                    rol = "directivo"
                    nombre_completo = nombre_usuario
                    perfil_id = directivo['id']
                    break
        
        # Si no es ninguno de los anteriores, intentar login como ADMIN (tabla usuarios)
        if not user:
            cursor.execute("SELECT * FROM usuarios WHERE usuario=%s AND rol='admin'", (usuario,))
            admin = cursor.fetchone()
            
            if admin and admin["password"] == password:
                user = admin
                rol = "admin"
                nombre_completo = admin.get("nombre_completo", usuario)
                perfil_id = admin.get("perfil_id")
        
        cursor.close()

        # Si se encontró un usuario válido
        if user and rol:
            # Login exitoso - limpiar intentos fallidos
            clear_login_attempts(usuario)
            session["usuario"] = usuario
            session["rol"] = rol
            session["nombre_completo"] = nombre_completo
            
            if perfil_id:
                session["perfil_id"] = perfil_id
            
            return redirect(url_for("menu"))
        else:
            # Login fallido - registrar intento
            record_failed_attempt(usuario)
            
            # Verificar si ahora está bloqueado
            is_locked, minutos_restantes = check_user_lockout(usuario)
            if is_locked:
                flash(f"Demasiados intentos fallidos. Usuario bloqueado por {minutos_restantes} minutos.", "error")
            else:
                flash("Usuario o contraseña incorrectos", "error")

    return render_template("login.html")


@app.route("/crear_cuenta", methods=["GET", "POST"])
def crear_cuenta():
    if request.method == "POST":
        rol = request.form["rol"]
        cursor = conexion.cursor()
        
        try:
            if rol == "alumno":
                # Para alumnos: usar campos del formulario de agregar alumno
                no_control = request.form['no_control']
                curp = request.form['curp']
                nombre = request.form['nombre']
                apellido_paterno = request.form['apellido_paterno']
                apellido_materno = request.form['apellido_materno']
                grupo = request.form['grupo']
                turno = request.form['turno']
                semestre = request.form['semestre']
                
                # Verificar si el alumno ya existe
                cursor.execute("SELECT * FROM alumnos WHERE no_control=%s", (no_control,))
                if cursor.fetchone():
                    flash("El alumno ya existe", "error")
                    cursor.close()
                    return render_template("crear_cuenta.html")
                
                # Insertar en tabla alumnos
                cursor.execute("""
                    INSERT INTO alumnos (no_control, curp, nombre, apellido_paterno, apellido_materno, grupo, turno, semestre)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                """, (no_control, curp, nombre, apellido_paterno, apellido_materno, grupo, turno, semestre))
                
                conexion.commit()
                flash(f"Cuenta de alumno creada correctamente. Usuario: {no_control}, Contraseña: {curp}", "success")
                
            elif rol == "docente":
                # Para docentes
                no_empleado = request.form['no_empleado']
                nombre = request.form['nombre']
                apellido_paterno = request.form['apellido_paterno']
                apellido_materno = request.form['apellido_materno']
                materia = request.form['materia']
                
                nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
                
                # Verificar si el docente ya existe
                cursor.execute("SELECT * FROM docentes WHERE no_empleado=%s", (no_empleado,))
                if cursor.fetchone():
                    flash("El docente ya existe", "error")
                    cursor.close()
                    return render_template("crear_cuenta.html")
                
                # Insertar en tabla docentes
                cursor.execute("""
                    INSERT INTO docentes (no_empleado, nombre, apellido_paterno, apellido_materno, materia)
                    VALUES (%s, %s, %s, %s, %s)
                """, (no_empleado, nombre, apellido_paterno, apellido_materno, materia))
                
                conexion.commit()
                flash(f"Cuenta de docente creada correctamente. Usuario: {nombre_completo}, Contraseña: {no_empleado}", "success")
                
            elif rol == "orientador":
                # Para orientadores
                no_empleado = request.form['no_empleado']
                nombre = request.form['nombre']
                apellido_paterno = request.form['apellido_paterno']
                apellido_materno = request.form['apellido_materno']
                grupos_encargado = request.form['grupos_encargado']
                
                nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
                
                # Verificar si el orientador ya existe
                cursor.execute("SELECT * FROM orientadores WHERE no_empleado=%s", (no_empleado,))
                if cursor.fetchone():
                    flash("El orientador ya existe", "error")
                    cursor.close()
                    return render_template("crear_cuenta.html")
                
                # Insertar en tabla orientadores
                cursor.execute("""
                    INSERT INTO orientadores (no_empleado, nombre, apellido_paterno, apellido_materno, grupos_encargado)
                    VALUES (%s, %s, %s, %s, %s)
                """, (no_empleado, nombre, apellido_paterno, apellido_materno, grupos_encargado))
                
                conexion.commit()
                flash(f"Cuenta de orientador creada correctamente. Usuario: {nombre_completo}, Contraseña: {no_empleado}", "success")
                
            elif rol == "directivo":
                # Para directivos
                no_empleado = request.form['no_empleado']
                nombre = request.form['nombre']
                apellido_paterno = request.form['apellido_paterno']
                apellido_materno = request.form['apellido_materno']
                puesto = request.form['puesto']
                
                nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
                
                # Verificar si el directivo ya existe
                cursor.execute("SELECT * FROM directivos WHERE no_empleado=%s", (no_empleado,))
                if cursor.fetchone():
                    flash("El directivo ya existe", "error")
                    cursor.close()
                    return render_template("crear_cuenta.html")
                
                # Insertar en tabla directivos
                cursor.execute("""
                    INSERT INTO directivos (no_empleado, nombre, apellido_paterno, apellido_materno, puesto)
                    VALUES (%s, %s, %s, %s, %s)
                """, (no_empleado, nombre, apellido_paterno, apellido_materno, puesto))
                
                conexion.commit()
                flash(f"Cuenta de directivo creada correctamente. Usuario: {nombre_completo}, Contraseña: {no_empleado}", "success")
                
            else:
                # Para admin, mantener el método original
                usuario = request.form["usuario"]
                password = request.form["password"]
                
                cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
                if cursor.fetchone():
                    flash("El usuario ya existe", "error")
                else:
                    cursor.execute("INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
                                   (usuario, password, rol))
                    conexion.commit()
                    flash("Cuenta creada correctamente", "info")
                    
            cursor.close()
            return redirect(url_for("login"))
            
        except Exception as e:
            conexion.rollback()
            cursor.close()
            flash(f"Error al crear la cuenta: {str(e)}", "error")
            return render_template("crear_cuenta.html")

    return render_template("crear_cuenta.html")


@app.route("/recuperar_contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    if request.method == "POST":
        usuario = request.form["usuario"]
        nueva_password = request.form["password"]

        cursor = conexion.cursor(dictionary=True)
        actualizado = False
        
        # Intentar actualizar en tabla alumnos (password es curp)
        cursor.execute("SELECT * FROM alumnos WHERE no_control=%s", (usuario,))
        if cursor.fetchone():
            cursor.execute("UPDATE alumnos SET curp=%s WHERE no_control=%s", (nueva_password, usuario))
            conexion.commit()
            actualizado = True
        
        # Si no es alumno, buscar por nombre completo en docentes
        if not actualizado:
            cursor.execute("SELECT * FROM docentes")
            docentes = cursor.fetchall()
            for docente in docentes:
                nombre_usuario = f"{docente['nombre']} {docente['apellido_paterno']} {docente['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower():
                    cursor.execute("UPDATE docentes SET no_empleado=%s WHERE id=%s", (nueva_password, docente['id']))
                    conexion.commit()
                    actualizado = True
                    break
        
        # Si no es docente, buscar en orientadores
        if not actualizado:
            cursor.execute("SELECT * FROM orientadores")
            orientadores = cursor.fetchall()
            for orientador in orientadores:
                nombre_usuario = f"{orientador['nombre']} {orientador['apellido_paterno']} {orientador['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower():
                    cursor.execute("UPDATE orientadores SET no_empleado=%s WHERE id=%s", (nueva_password, orientador['id']))
                    conexion.commit()
                    actualizado = True
                    break
        
        # Si no es orientador, buscar en directivos
        if not actualizado:
            cursor.execute("SELECT * FROM directivos")
            directivos = cursor.fetchall()
            for directivo in directivos:
                nombre_usuario = f"{directivo['nombre']} {directivo['apellido_paterno']} {directivo['apellido_materno']}"
                if nombre_usuario.lower() == usuario.lower():
                    cursor.execute("UPDATE directivos SET no_empleado=%s WHERE id=%s", (nueva_password, directivo['id']))
                    conexion.commit()
                    actualizado = True
                    break
        
        # Si no es ninguno de los anteriores, buscar en usuarios (admin)
        if not actualizado:
            cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
            if cursor.fetchone():
                cursor.execute("UPDATE usuarios SET password=%s WHERE usuario=%s", (nueva_password, usuario))
                conexion.commit()
                actualizado = True
        
        cursor.close()
        
        if actualizado:
            flash("Contraseña actualizada correctamente", "success")
            return redirect(url_for("login"))
        else:
            flash("El usuario no existe", "error")

    return render_template("recuperar_contrasena.html")


@app.route("/menu")
def menu():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    rol = session["rol"]
    nombre_completo = session.get("nombre_completo", session["usuario"])
    
    # Redirigir a cada menú según el rol
    if rol == "admin":
        return render_template("menu_admin.html", usuario=session["usuario"], rol=rol, nombre_completo=nombre_completo)
    elif rol == "directivo":
        return render_template("menu_directivo.html", usuario=session["usuario"], rol=rol, nombre_completo=nombre_completo)
    elif rol == "orientador":
        return render_template("menu_orientador.html", usuario=session["usuario"], rol=rol, nombre_completo=nombre_completo)
    elif rol == "docente":
        return render_template("menu_docente.html", usuario=session["usuario"], rol=rol, nombre_completo=nombre_completo)
    elif rol == "alumno":
        return render_template("menu_alumnos.html", usuario=session["usuario"], rol=rol, nombre_completo=nombre_completo)
    else:
        return redirect(url_for("login"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# ==============================================================
#                      CRUD: ALUMNOS
# ==============================================================
@app.route("/alumnos", methods=["GET"])
def alumnos():
    query = request.args.get('q', '').strip()
    cursor = conexion.cursor(dictionary=True)

    if query:
        sql = """
            SELECT * FROM alumnos
            WHERE nombre LIKE %s OR apellido_paterno LIKE %s OR apellido_materno LIKE %s
            OR no_control LIKE %s OR curp LIKE %s OR grupo LIKE %s OR turno LIKE %s OR semestre LIKE %s
        """
        params = tuple(['%' + query + '%'] * 8)
        cursor.execute(sql, params)
    else:
        cursor.execute("SELECT * FROM alumnos")

    alumnos = cursor.fetchall()
    cursor.close()
    return render_template("alumnos.html", alumnos=alumnos, query=query)


@app.route("/alumnos/agregar", methods=["POST"])
def agregar_alumno():
    no_control = request.form['no_control']
    curp = request.form['curp']
    nombre = request.form['nombre']
    apellido_paterno = request.form['apellido_paterno']
    apellido_materno = request.form['apellido_materno']
    grupo = request.form['grupo']
    turno = request.form['turno']
    semestre = request.form['semestre']
    
    cursor = conexion.cursor()
    
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (no_control,))
        if cursor.fetchone():
            flash("El número de control ya existe como usuario", "error")
            cursor.close()
            return redirect(url_for("alumnos"))
        
        # Insertar en tabla alumnos
        cursor.execute("""
            INSERT INTO alumnos (no_control, curp, nombre, apellido_paterno, apellido_materno, grupo, turno, semestre)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        """, (no_control, curp, nombre, apellido_paterno, apellido_materno, grupo, turno, semestre))
        
        # Obtener el ID del alumno recién insertado
        alumno_id = cursor.lastrowid
        
        # Crear usuario automáticamente
        nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
        cursor.execute("""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, perfil_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (no_control, curp, 'alumno', nombre_completo, alumno_id))
        
        conexion.commit()
        flash(f"Alumno agregado correctamente. Usuario creado: {no_control}", "success")
        
    except Exception as e:
        conexion.rollback()
        flash(f"Error al agregar alumno: {str(e)}", "error")
    finally:
        cursor.close()
    
    return redirect(url_for("alumnos"))

@app.route("/logout_inactivity", methods=["POST"])
def logout_inactivity():
    session.clear()
    flash("Se cerró sesión por inactividad", "warning")
    return {"status": "logged_out"}
@app.route("/alumnos/editar/<int:id>", methods=["GET", "POST"])
def editar_alumno(id):
    cursor = conexion.cursor(dictionary=True)
    if request.method == "POST":
        data = (
            request.form['no_control'],
            request.form['curp'],
            request.form['nombre'],
            request.form['apellido_paterno'],
            request.form['apellido_materno'],
            request.form['grupo'],
            request.form['turno'],
            request.form['semestre'],
            id
        )
        cursor.execute("""
            UPDATE alumnos SET no_control=%s, curp=%s, nombre=%s, apellido_paterno=%s,
            apellido_materno=%s, grupo=%s, turno=%s, semestre=%s WHERE id=%s
        """, data)
        conexion.commit()
        cursor.close()
        return redirect(url_for("alumnos"))

    cursor.execute("SELECT * FROM alumnos WHERE id=%s", (id,))
    alumno = cursor.fetchone()
    cursor.close()
    return render_template("editar_alumno.html", alumno=alumno)


@app.route("/alumnos/eliminar/<int:id>")
def eliminar_alumno(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM alumnos WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()
    return redirect(url_for("alumnos"))

# ==============================================================
#                      CRUD: DOCENTES
# ==============================================================
@app.route("/docentes", methods=["GET"])
def docentes():
    query = request.args.get('q', '').strip()
    cursor = conexion.cursor(dictionary=True)

    if query:
        cursor.execute("""
            SELECT * FROM docentes
            WHERE no_empleado LIKE %s OR nombre LIKE %s OR apellido_paterno LIKE %s
            OR apellido_materno LIKE %s OR materia LIKE %s
        """, tuple(['%' + query + '%'] * 5))
    else:
        cursor.execute("SELECT * FROM docentes")

    docentes = cursor.fetchall()
    cursor.close()
    return render_template("docentes.html", docentes=docentes, query=query)


@app.route("/docentes/agregar", methods=["POST"])
def agregar_docente():
    no_empleado = request.form["no_empleado"]
    nombre = request.form["nombre"]
    apellido_paterno = request.form["apellido_paterno"]
    apellido_materno = request.form["apellido_materno"]
    materia = request.form["materia"]
    
    cursor = conexion.cursor()
    
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (no_empleado,))
        if cursor.fetchone():
            flash("El número de empleado ya existe como usuario", "error")
            cursor.close()
            return redirect(url_for("docentes"))
        
        # Insertar en tabla docentes
        cursor.execute("""
            INSERT INTO docentes (no_empleado, nombre, apellido_paterno, apellido_materno, materia)
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, nombre, apellido_paterno, apellido_materno, materia))
        
        # Obtener el ID del docente recién insertado
        docente_id = cursor.lastrowid
        
        # Generar contraseña de 8 dígitos
        password = generar_password_8digitos()
        
        # Crear usuario automáticamente
        nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
        cursor.execute("""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, perfil_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, password, 'docente', nombre_completo, docente_id))
        
        conexion.commit()
        flash(f"Docente agregado correctamente. Usuario: {no_empleado}, Contraseña: {password}", "success")
        
    except Exception as e:
        conexion.rollback()
        flash(f"Error al agregar docente: {str(e)}", "error")
    finally:
        cursor.close()
    
    return redirect(url_for("docentes"))


@app.route("/docentes/editar/<int:id>", methods=["GET", "POST"])
def editar_docente(id):
    cursor = conexion.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE docentes SET no_empleado=%s, nombre=%s, apellido_paterno=%s,
            apellido_materno=%s, materia=%s WHERE id=%s
        """, (
            request.form["no_empleado"],
            request.form["nombre"],
            request.form["apellido_paterno"],
            request.form["apellido_materno"],
            request.form["materia"],
            id
        ))
        conexion.commit()
        cursor.close()
        flash("Docente actualizado correctamente")
        return redirect(url_for("docentes"))

    cursor.execute("SELECT * FROM docentes WHERE id=%s", (id,))
    docente = cursor.fetchone()
    cursor.close()
    return render_template("editar_docente.html", docente=docente)


@app.route("/docentes/eliminar/<int:id>")
def eliminar_docente(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM docentes WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()
    flash("Docente eliminado correctamente")
    return redirect(url_for("docentes"))

@app.route("/docente/visualizaciones/<int:id_recurso>")
def ver_visualizaciones_docente(id_recurso):
    if session.get("rol") != "docente":
        abort(403)

    # 🔹 KPI TOTAL
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    total = cursor.fetchone()["total"]
    cursor.close()

    # 🔹 KPI USUARIOS ÚNICOS
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(DISTINCT usuario) AS usuarios_unicos
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    usuarios_unicos = cursor.fetchone()["usuarios_unicos"]
    cursor.close()

    # 🔹 KPI HOY
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) AS hoy
        FROM visualizaciones
        WHERE id_recurso = %s
        AND DATE(fecha) = CURDATE()
    """, (id_recurso,))
    hoy = cursor.fetchone()["hoy"]
    cursor.close()

    # 🔹 KPI SEMANA
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT COUNT(*) AS semana
        FROM visualizaciones
        WHERE id_recurso = %s
        AND YEARWEEK(fecha, 1) = YEARWEEK(CURDATE(), 1)
    """, (id_recurso,))
    semana = cursor.fetchone()["semana"]
    cursor.close()

    # 🔹 KPI ÚLTIMA
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT MAX(fecha) AS ultima
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    ultima = cursor.fetchone()["ultima"]
    cursor.close()

    # 🔹 USUARIOS (UNA SOLA VEZ POR USUARIO)
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("""
        SELECT
            u.nombre_completo,
            MAX(v.fecha) AS fecha
        FROM visualizaciones v
        JOIN usuarios u ON v.usuario = u.usuario
        WHERE v.id_recurso = %s
        GROUP BY v.usuario, u.nombre_completo
        ORDER BY fecha DESC
    """, (id_recurso,))
    visualizaciones = cursor.fetchall()
    cursor.close()

    return render_template(
        "visualizaciones_docente.html",
        total=total,
        usuarios_unicos=usuarios_unicos,
        hoy=hoy,
        semana=semana,
        ultima=ultima,
        visualizaciones=visualizaciones
    )

###########################################################################
#                      REPORTE GENERAL DE VISUALIZACION                   #
###########################################################################
@app.route("/docente/reporte/visualizaciones/<int:id_recurso>")
def reporte_visualizaciones(id_recurso):
    if session.get("rol") != "docente":
        abort(403)

    cursor = conexion.cursor(dictionary=True)

    # Reporte general con nombre completo del usuario
    cursor.execute("""
        SELECT 
            u.nombre_completo,
            v.fecha
        FROM visualizaciones v
        JOIN usuarios u ON v.id_usuario = u.id_usuario
        WHERE v.id_recurso = %s
        ORDER BY v.fecha DESC
    """, (id_recurso,))

    visualizaciones = cursor.fetchall()

    # KPIs
    cursor.execute("""
        SELECT COUNT(*) AS total
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    total = cursor.fetchone()["total"]

    cursor.execute("""
        SELECT COUNT(DISTINCT id_usuario) AS usuarios_unicos
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    usuarios_unicos = cursor.fetchone()["usuarios_unicos"]

    cursor.execute("""
        SELECT MAX(fecha) AS ultima
        FROM visualizaciones
        WHERE id_recurso = %s
    """, (id_recurso,))
    ultima = cursor.fetchone()["ultima"]

    cursor.close()

    return render_template(
        "reporte_visualizaciones_docente.html",
        visualizaciones=visualizaciones,
        total=total,
        usuarios_unicos=usuarios_unicos,
        ultima=ultima
    )


# ==============================================================
#                      CRUD: ORIENTADORES
# ==============================================================
@app.route("/orientadores", methods=["GET"])
def orientadores():
    query = request.args.get('q', '').strip()
    cursor = conexion.cursor(dictionary=True)

    if query:
        cursor.execute("""
            SELECT * FROM orientadores
            WHERE nombre LIKE %s OR apellido_paterno LIKE %s OR apellido_materno LIKE %s OR correo LIKE %s
        """, tuple(['%' + query + '%'] * 4))
    else:
        cursor.execute("SELECT * FROM orientadores")

    orientadores = cursor.fetchall()
    cursor.close()
    return render_template("orientadores.html", orientadores=orientadores, query=query)


@app.route("/orientadores/agregar", methods=["POST"])
def agregar_orientador():
    no_empleado = request.form["no_empleado"]
    nombre = request.form["nombre"]
    apellido_paterno = request.form["apellido_paterno"]
    apellido_materno = request.form["apellido_materno"]
    grupos_encargado = request.form["grupos_encargado"]
    
    cursor = conexion.cursor()
    
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (no_empleado,))
        if cursor.fetchone():
            flash("El número de empleado ya existe como usuario", "error")
            cursor.close()
            return redirect(url_for("orientadores"))
        
        # Insertar en tabla orientadores
        cursor.execute("""
            INSERT INTO orientadores (no_empleado, nombre, apellido_paterno, apellido_materno, grupos_encargado)
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, nombre, apellido_paterno, apellido_materno, grupos_encargado))
        
        # Obtener el ID del orientador recién insertado
        orientador_id = cursor.lastrowid
        
        # Generar contraseña de 8 dígitos
        password = generar_password_8digitos()
        
        # Crear usuario automáticamente
        nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
        cursor.execute("""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, perfil_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, password, 'orientador', nombre_completo, orientador_id))
        
        conexion.commit()
        flash(f"Orientador agregado correctamente. Usuario: {no_empleado}, Contraseña: {password}", "success")
        
    except Exception as e:
        conexion.rollback()
        flash(f"Error al agregar orientador: {str(e)}", "error")
    finally:
        cursor.close()
    
    return redirect(url_for("orientadores"))


@app.route("/orientadores/editar/<int:id>", methods=["GET", "POST"])
def editar_orientador(id):
    cursor = conexion.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE orientadores SET nombre=%s, apellido_paterno=%s, apellido_materno=%s,
            telefono=%s, correo=%s WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["apellido_paterno"],
            request.form["apellido_materno"],
            request.form["telefono"],
            request.form["correo"],
            id
        ))
        conexion.commit()
        cursor.close()
        flash("Orientador actualizado correctamente")
        return redirect(url_for("orientadores"))

    cursor.execute("SELECT * FROM orientadores WHERE id=%s", (id,))
    orientador = cursor.fetchone()
    cursor.close()
    return render_template("editar_orientador.html", orientador=orientador)


@app.route("/orientadores/eliminar/<int:id>")
def eliminar_orientador(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM orientadores WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()
    flash("Orientador eliminado correctamente")
    return redirect(url_for("orientadores"))


# ==============================================================
#                      CRUD: DIRECTIVOS
# ==============================================================
@app.route("/directivos", methods=["GET"])
def directivos():
    query = request.args.get('q', '').strip()
    cursor = conexion.cursor(dictionary=True)

    if query:
        cursor.execute("""
            SELECT * FROM directivos
            WHERE nombre LIKE %s OR apellido_paterno LIKE %s OR apellido_materno LIKE %s OR cargo LIKE %s
        """, tuple(['%' + query + '%'] * 4))
    else:
        cursor.execute("SELECT * FROM directivos")

    directivos = cursor.fetchall()
    cursor.close()
    return render_template("directivos.html", directivos=directivos, query=query)


@app.route("/directivos/agregar", methods=["POST"])
def agregar_directivo():
    no_empleado = request.form["no_empleado"]
    nombre = request.form["nombre"]
    apellido_paterno = request.form["apellido_paterno"]
    apellido_materno = request.form["apellido_materno"]
    puesto = request.form["puesto"]
    
    cursor = conexion.cursor()
    
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (no_empleado,))
        if cursor.fetchone():
            flash("El número de empleado ya existe como usuario", "error")
            cursor.close()
            return redirect(url_for("directivos"))
        
        # Insertar en tabla directivos
        cursor.execute("""
            INSERT INTO directivos (no_empleado, nombre, apellido_paterno, apellido_materno, puesto)
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, nombre, apellido_paterno, apellido_materno, puesto))
        
        # Obtener el ID del directivo recién insertado
        directivo_id = cursor.lastrowid
        
        # Generar contraseña de 8 dígitos
        password = generar_password_8digitos()
        
        # Crear usuario automáticamente
        nombre_completo = f"{nombre} {apellido_paterno} {apellido_materno}"
        cursor.execute("""
            INSERT INTO usuarios (usuario, password, rol, nombre_completo, perfil_id) 
            VALUES (%s, %s, %s, %s, %s)
        """, (no_empleado, password, 'directivo', nombre_completo, directivo_id))
        
        conexion.commit()
        flash(f"Directivo agregado correctamente. Usuario: {no_empleado}, Contraseña: {password}", "success")
        
    except Exception as e:
        conexion.rollback()
        flash(f"Error al agregar directivo: {str(e)}", "error")
    finally:
        cursor.close()
    
    return redirect(url_for("directivos"))


@app.route("/directivos/editar/<int:id>", methods=["GET", "POST"])
def editar_directivo(id):
    cursor = conexion.cursor(dictionary=True)
    if request.method == "POST":
        cursor.execute("""
            UPDATE directivos SET nombre=%s, apellido_paterno=%s, apellido_materno=%s,
            cargo=%s, correo=%s WHERE id=%s
        """, (
            request.form["nombre"],
            request.form["apellido_paterno"],
            request.form["apellido_materno"],
            request.form["cargo"],
            request.form["correo"],
            id
        ))
        conexion.commit()
        cursor.close()
        flash("Directivo actualizado correctamente")
        return redirect(url_for("directivos"))

    cursor.execute("SELECT * FROM directivos WHERE id=%s", (id,))
    directivo = cursor.fetchone()
    cursor.close()
    return render_template("editar_directivo.html", directivo=directivo)


@app.route("/directivos/eliminar/<int:id>")
def eliminar_directivo(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM directivos WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()
    flash("Directivo eliminado correctamente")
    return redirect(url_for("directivos"))


# ==============================================================
#                      CRUD: MATERIAS
# ==============================================================
@app.route("/materias", methods=["GET", "POST"])
def materias():
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        busqueda = request.form["busqueda"]
        cursor.execute("""
            SELECT * FROM materias
            WHERE no_empleado LIKE %s OR docente LIKE %s OR materia LIKE %s
        """, (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%"))
    else:
        cursor.execute("SELECT * FROM materias")

    materias = cursor.fetchall()
    cursor.close()
    return render_template("materias.html", materias=materias)


# ✅ AGREGAR
@app.route("/materias/agregar", methods=["POST"])
def agregar_materia():
    no_empleado = request.form["no_empleado"]
    docente = request.form["docente"]
    materia = request.form["materia"]

    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO materias (no_empleado, docente, materia)
        VALUES (%s, %s, %s)
    """, (no_empleado, docente, materia))
    conexion.commit()
    cursor.close()

    flash("Materia agregada correctamente", "info")
    return redirect(url_for("materias"))


# ✅ EDITAR
@app.route("/materias/editar/<int:id>", methods=["GET", "POST"])
def editar_materia(id):
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        no_empleado = request.form["no_empleado"]
        docente = request.form["docente"]
        materia = request.form["materia"]

        cursor.execute("""
            UPDATE materias
            SET no_empleado=%s, docente=%s, materia=%s
            WHERE id=%s
        """, (no_empleado, docente, materia, id))
        conexion.commit()
        cursor.close()
        flash("Materia actualizada correctamente", "info")
        return redirect(url_for("materias"))

    cursor.execute("SELECT * FROM materias WHERE id=%s", (id,))
    materia = cursor.fetchone()
    cursor.close()

    return render_template("editar_materia.html", materia=materia)


# ✅ ELIMINAR
@app.route("/materias/eliminar/<int:id>")
def eliminar_materia(id):
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM materias WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()

    flash("Materia eliminada correctamente", "info")
    return redirect(url_for("materias"))


from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import mysql.connector
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

# ==============================================================
#                      CRUD: RECURSOS
# ==============================================================
@app.route("/recursos", methods=["GET", "POST"])
def recursos():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    rol = session["rol"]
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        busqueda = request.form["busqueda"]
        cursor.execute("""
            SELECT * FROM recursos 
            WHERE nombre LIKE %s
            OR materia LIKE %s
            OR tipo LIKE %s
        """, (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%"))
    else:
        # Si es alumno, filtrar recursos por su grupo, semestre y turno
        if rol == "alumno":
            # Obtener el perfil del alumno
            perfil_id = session.get("perfil_id")
            if perfil_id:
                cursor.execute("SELECT grupo, semestre, turno FROM alumnos WHERE id=%s", (perfil_id,))
                alumno = cursor.fetchone()
                
                if alumno:
                    # Filtrar recursos: mostrar los que coincidan O los que no tienen filtros (generales)
                    cursor.execute("""
                        SELECT * FROM recursos 
                        WHERE (grupo IS NULL OR grupo = '' OR grupo = %s)
                        AND (semestre IS NULL OR semestre = '' OR semestre = %s)
                        AND (turno IS NULL OR turno = '' OR turno = %s)
                    """, (alumno['grupo'], alumno['semestre'], alumno['turno']))
                else:
                    cursor.execute("SELECT * FROM recursos")
            else:
                cursor.execute("SELECT * FROM recursos")
        else:
            # Para otros roles, mostrar todos los recursos
            cursor.execute("SELECT * FROM recursos")

    recursos = cursor.fetchall()
    
    # Obtener materias asignadas del docente si es docente
    materias_docente = []
    if rol == "docente":
        perfil_id = session.get("perfil_id")
        if perfil_id:
            # Primero obtener el no_empleado del docente
            cursor.execute("SELECT no_empleado FROM docentes WHERE id = %s", (perfil_id,))
            docente_data = cursor.fetchone()
            if docente_data and docente_data['no_empleado']:
                # Luego obtener las materias asignadas usando no_empleado
                cursor.execute("""
                    SELECT DISTINCT nombre_materia 
                    FROM materias_asignadas 
                    WHERE no_empleado = %s
                    ORDER BY nombre_materia
                """, (docente_data['no_empleado'],))
                materias_docente = [m['nombre_materia'] for m in cursor.fetchall()]
    
    cursor.close()
    
    if rol == "alumno":
        return render_template("recursos_alumno.html", recursos=recursos)
    else:
        return render_template("recursos.html", recursos=recursos, rol=rol, materias_docente=materias_docente)


    # Solo admin, directivo, orientador y docente pueden agregar
@app.route("/recursos/agregar", methods=["POST"])
def agregar_recurso():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    if session["rol"] == "alumno":
        flash("No tienes permisos para agregar recursos", "error")
        return redirect(url_for("recursos"))
    
    nombre = request.form["nombre"]
    materia = request.form["materia"]
    tipo = request.form["tipo"]
    grupo = request.form.get("grupo", "") or None  # Empty string becomes None
    semestre = request.form.get("semestre", "") or None
    turno = request.form.get("turno", "") or None
    
    fecha = datetime.now()  # 👈 FECHA AUTOMÁTICA
    
    if 'archivo' not in request.files:
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('recursos'))
    
    archivo = request.files['archivo']
    
    if archivo.filename == '':
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('recursos'))
        
    filename = secure_filename(archivo.filename)
    archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO recursos (fecha, nombre, materia, tipo, archivo, grupo, semestre, turno)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (fecha, nombre, materia, tipo, filename, grupo, semestre, turno))
    
    conexion.commit()
    cursor.close()

    flash("Recurso agregado correctamente", "info")
    return redirect(url_for("recursos"))



@app.route("/recursos/editar/<int:id>", methods=["GET", "POST"])
def editar_recurso(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    if session["rol"] == "alumno":
        flash("No tienes permisos para editar recursos", "error")
        return redirect(url_for("recursos"))
    
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        nombre = request.form["nombre"]
        materia = request.form["materia"]
        tipo = request.form["tipo"]
        grupo = request.form.get("grupo", "") or None
        semestre = request.form.get("semestre", "") or None
        turno = request.form.get("turno", "") or None
        
        archivo = request.files.get('archivo')
        
        if archivo and archivo.filename != '':
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            cursor.execute("""
                UPDATE recursos
                SET nombre=%s, materia=%s, tipo=%s, archivo=%s, grupo=%s, semestre=%s, turno=%s
                WHERE id=%s
            """, (nombre, materia, tipo, filename, grupo, semestre, turno, id))
        else:
            cursor.execute("""
                UPDATE recursos
                SET nombre=%s, materia=%s, tipo=%s, grupo=%s, semestre=%s, turno=%s
                WHERE id=%s
            """, (nombre, materia, tipo, grupo, semestre, turno, id))
            
        conexion.commit()
        cursor.close()
        flash("Recurso actualizado correctamente", "info")
        return redirect(url_for("recursos"))

    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()
    
    # Obtener materias asignadas del docente si es docente
    materias_docente = []
    if session["rol"] == "docente":
        perfil_id = session.get("perfil_id")
        if perfil_id:
            # Primero obtener el no_empleado del docente
            cursor.execute("SELECT no_empleado FROM docentes WHERE id = %s", (perfil_id,))
            docente_data = cursor.fetchone()
            if docente_data and docente_data['no_empleado']:
                # Luego obtener las materias asignadas usando no_empleado
                cursor.execute("""
                    SELECT DISTINCT nombre_materia 
                    FROM materias_asignadas 
                    WHERE no_empleado = %s
                    ORDER BY nombre_materia
                """, (docente_data['no_empleado'],))
                materias_docente = [m['nombre_materia'] for m in cursor.fetchall()]
    
    cursor.close()
    return render_template("editarrecursos.html", recurso=recurso, rol=session["rol"], materias_docente=materias_docente)



@app.route("/recursos/eliminar/<int:id>")
def eliminar_recurso(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    # Solo admin, directivo, orientador y docente pueden eliminar
    if session["rol"] == "alumno":
        flash("No tienes permisos para eliminar recursos", "error")
        return redirect(url_for("recursos"))
    
    cursor = conexion.cursor()
    cursor.execute("DELETE FROM recursos WHERE id=%s", (id,))
    conexion.commit()
    cursor.close()

    flash("Recurso eliminado correctamente", "info")
    return redirect(url_for("recursos"))


# ==============================================================
#                  DESCARGAR RECURSO (TODOS)
# ==============================================================
@app.route("/recursos/descargar/<int:id>")
def descargar_recurso(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    cursor = conexion.cursor(dictionary=True)
    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()
    cursor.close()
    
    if not recurso or not recurso['archivo']:
        flash("Recurso no encontrado o sin archivo adjunto", "error")
        return redirect(url_for("recursos"))
    
    # Descargar el archivo almacenado
    try:
        return send_file(os.path.join(app.config['UPLOAD_FOLDER'], recurso['archivo']), as_attachment=True)
    except FileNotFoundError:
        flash("El archivo físico no se encuentra en el servidor", "error")
        return redirect(url_for("recursos"))
    
#######################################################################
#                 VISUALIZAR RECURSO
########################################################################
import os  # Asegúrate de tener este import al inicio del archivo
from flask import render_template, redirect, url_for, session, abort, send_from_directory

@app.route("/recursos/visualizar/<int:id>")
def visualizar_recurso(id):
    """Muestra la página de visualización del recurso"""
    if "usuario" not in session:
        return redirect(url_for("login"))

    cursor = conexion.cursor(dictionary=True)

    # Obtener recurso
    cursor.execute("""
        SELECT id, fecha, nombre, estadisticas, materia, tipo,
               archivo, grupo, semestre, turno
        FROM recursos 
        WHERE id = %s
    """, (id,))
    recurso = cursor.fetchone()

    if not recurso:
        cursor.close()
        abort(404)

    # 🔹 REGISTRAR VISUALIZACIÓN (AQUÍ SE AGREGA)
    try:
        cursor.execute("""
            INSERT INTO visualizaciones (id_recurso, usuario)
            VALUES (%s, %s)
        """, (id, session["usuario"]))
        conexion.commit()
    except:
        # Si ya existe (por UNIQUE), no pasa nada
        pass

    cursor.close()

    nombre_archivo = recurso["archivo"]
    extension = os.path.splitext(nombre_archivo)[1].lower()

    return render_template(
        "visualizar_recurso.html",
        recurso=recurso,
        archivo=nombre_archivo,
        extension=extension,
        id=id
    )

@app.route("/ver_archivo/<filename>")
def ver_archivo(filename):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    uploads_path = os.path.join(base_dir, app.config['UPLOAD_FOLDER'])

    print(f"Buscando archivo en: {uploads_path}/{filename}")

    return send_from_directory(uploads_path, filename)


# ==============================================================
#           REPORTE GENERAL (SOLO DIRECTIVOS Y ADMIN)
# ==============================================================
@app.route("/recursos/reporte_general")
def reporte_general():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    # Solo admin y directivo pueden descargar el reporte general
    if session["rol"] not in ["admin", "directivo"]:
        flash("No tienes permisos para descargar el reporte general", "error")
        return redirect(url_for("recursos"))
    
    # Obtener todos los datos
    cursor = conexion.cursor(dictionary=True)
    
    # Recursos
    cursor.execute("SELECT * FROM recursos ORDER BY fecha DESC")
    recursos = cursor.fetchall()
    
    # Alumnos
    cursor.execute("SELECT COUNT(*) as total FROM alumnos")
    total_alumnos = cursor.fetchone()['total']
    
    # Docentes
    cursor.execute("SELECT COUNT(*) as total FROM docentes")
    total_docentes = cursor.fetchone()['total']
    
    # Materias
    cursor.execute("SELECT COUNT(*) as total FROM materias")
    total_materias = cursor.fetchone()['total']
    
    cursor.close()
    
    # Crear PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter)
    elements = []
    styles = getSampleStyleSheet()
    
    # Título principal
    title = Paragraph("<b>REPORTE GENERAL DEL SISTEMA</b>", styles['Title'])
    elements.append(title)
    elements.append(Spacer(1, 12))
    
    # Fecha del reporte
    fecha_reporte = Paragraph(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}", styles['Normal'])
    elements.append(fecha_reporte)
    elements.append(Spacer(1, 20))
    
    # Estadísticas generales
    stats_title = Paragraph("<b>ESTADÍSTICAS GENERALES</b>", styles['Heading2'])
    elements.append(stats_title)
    elements.append(Spacer(1, 12))
    
    stats_data = [
        ['Categoría', 'Total'],
        ['Alumnos', str(total_alumnos)],
        ['Docentes', str(total_docentes)],
        ['Materias', str(total_materias)],
        ['Recursos', str(len(recursos))]
    ]
    
    stats_table = Table(stats_data, colWidths=[250, 250])
    stats_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    
    elements.append(stats_table)
    elements.append(Spacer(1, 30))
    
    # Tabla de recursos
    recursos_title = Paragraph("<b>LISTADO DE RECURSOS</b>", styles['Heading2'])
    elements.append(recursos_title)
    elements.append(Spacer(1, 12))
    
    if recursos:
        recursos_data = [['ID', 'Nombre', 'Materia', 'Tipo', 'Fecha']]
        for r in recursos:
            recursos_data.append([
                str(r['id']),
                r['nombre'][:20],  # Limitar longitud
                r['materia'][:15],
                r['tipo'][:10],
                str(r['fecha'])
            ])
        
        recursos_table = Table(recursos_data, colWidths=[30, 70, 120, 90, 60, 70])
        recursos_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3498db')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#ecf0f1')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')])
        ]))
        
        elements.append(recursos_table)
    else:
        no_recursos = Paragraph("No hay recursos registrados", styles['Normal'])
        elements.append(no_recursos)
    
    doc.build(elements)
    buffer.seek(0)
    
    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"reporte_general_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype='application/pdf'
    )

if __name__ == "__main__":
    app.run(debug=True)