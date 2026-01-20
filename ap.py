from flask import Flask, render_template, request, redirect, url_for, session, flash
import mysql.connector
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file
import mysql.connector
import os
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
    password="admin",
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
        # Buscar usuario solo por nombre de usuario (sin rol)
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
        user = cursor.fetchone()
        cursor.close()

        if user and user["password"] == password:
            # Login exitoso - limpiar intentos fallidos
            clear_login_attempts(usuario)
            session["usuario"] = usuario
            session["rol"] = user["rol"]  # Obtener rol automáticamente de la base de datos
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
        usuario = request.form["usuario"]
        password = request.form["password"]
        rol = request.form["rol"]

        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
        if cursor.fetchone():
            flash("El usuario ya existe", "error")
        else:
            cursor.execute("INSERT INTO usuarios (usuario, password, rol) VALUES (%s, %s, %s)",
                           (usuario, password, rol))
            conexion.commit()
            flash("Cuenta creada correctamente", "info")
            return redirect(url_for("login"))
        cursor.close()

    return render_template("crear_cuenta.html")


@app.route("/recuperar_contrasena", methods=["GET", "POST"])
def recuperar_contrasena():
    if request.method == "POST":
        usuario = request.form["usuario"]
        new_password = request.form["new_password"]

        cursor = conexion.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE usuario=%s", (usuario,))
        if cursor.fetchone():
            cursor.execute("UPDATE usuarios SET password=%s WHERE usuario=%s", (new_password, usuario))
            conexion.commit()
            flash("Contraseña actualizada correctamente", "info")
            cursor.close()
            return redirect(url_for("login"))
        else:
            flash("El usuario no existe", "error")
            cursor.close()

    return render_template("recuperar_contrasena.html")


@app.route("/menu")
def menu():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    rol = session["rol"]
    
    # Redirigir a cada menú según el rol
    if rol == "admin":
        return render_template("menu_admin.html", usuario=session["usuario"], rol=rol)
    elif rol == "directivo":
        return render_template("menu_directivo.html", usuario=session["usuario"], rol=rol)
    elif rol == "orientador":
        return render_template("menu_orientador.html", usuario=session["usuario"], rol=rol)
    elif rol == "docente":
        return render_template("menu_docente.html", usuario=session["usuario"], rol=rol)
    elif rol == "alumno":
        return render_template("menu_alumnos.html", usuario=session["usuario"], rol=rol)
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
    data = (
        request.form['no_control'],
        request.form['curp'],
        request.form['nombre'],
        request.form['apellido_paterno'],
        request.form['apellido_materno'],
        request.form['grupo'],
        request.form['turno'],
        request.form['semestre']
    )
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO alumnos (no_control, curp, nombre, apellido_paterno, apellido_materno, grupo, turno, semestre)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
    """, data)
    conexion.commit()
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
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO docentes (no_empleado, nombre, apellido_paterno, apellido_materno, materia)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        request.form["no_empleado"],
        request.form["nombre"],
        request.form["apellido_paterno"],
        request.form["apellido_materno"],
        request.form["materia"]
    ))
    conexion.commit()
    cursor.close()
    flash("Docente agregado correctamente")
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
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO orientadores (nombre, apellido_paterno, apellido_materno, telefono, correo)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        request.form["nombre"],
        request.form["apellido_paterno"],
        request.form["apellido_materno"],
        request.form["telefono"],
        request.form["correo"]
    ))
    conexion.commit()
    cursor.close()
    flash("Orientador agregado correctamente")
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
    cursor = conexion.cursor()
    cursor.execute("""
        INSERT INTO directivos (nombre, apellido_paterno, apellido_materno, cargo, correo)
        VALUES (%s, %s, %s, %s, %s)
    """, (
        request.form["nombre"],
        request.form["apellido_paterno"],
        request.form["apellido_materno"],
        request.form["cargo"],
        request.form["correo"]
    ))
    conexion.commit()
    cursor.close()
    flash("Directivo agregado correctamente")
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
            WHERE no_control LIKE %s 
            OR nombre LIKE %s
            OR materia LIKE %s
            OR tipo LIKE %s
        """, (f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%", f"%{busqueda}%"))
    else:
        cursor.execute("SELECT * FROM recursos")

    recursos = cursor.fetchall()
    cursor.close()
    
    # Renderizar vista según el rol
    if rol == "alumno":
        return render_template("recursos_alumno.html", recursos=recursos, usuario=session["usuario"])
    else:
        return render_template("recursos.html", recursos=recursos, rol=rol)


@app.route("/recursos/agregar", methods=["POST"])
def agregar_recurso():
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    # Solo admin, directivo, orientador y docente pueden agregar
    if session["rol"] == "alumno":
        flash("No tienes permisos para agregar recursos", "error")
        return redirect(url_for("recursos"))
    
    no_control = request.form["no_control"]
    fecha = request.form["fecha"]
    nombre = request.form["nombre"]
    estadisticas = request.form["estadisticas"]
    materia = request.form["materia"]
    tipo = request.form["tipo"]
    
    # Manejo del archivo
    if 'archivo' not in request.files:
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('recursos'))
    
    archivo = request.files['archivo']
    
    if archivo.filename == '':
        flash('No se seleccionó ningún archivo', 'error')
        return redirect(url_for('recursos'))
        
    if archivo:
        filename = secure_filename(archivo.filename)
        archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        
        cursor = conexion.cursor()
        cursor.execute("""
            INSERT INTO recursos (no_control, fecha, nombre, estadisticas, materia, tipo, archivo)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (no_control, fecha, nombre, estadisticas, materia, tipo, filename))
        conexion.commit()
        cursor.close()

        flash("Recurso agregado correctamente", "info")
        return redirect(url_for("recursos"))


@app.route("/recursos/editar/<int:id>", methods=["GET", "POST"])
def editar_recurso(id):
    if "usuario" not in session:
        return redirect(url_for("login"))
    
    # Solo admin, directivo, orientador y docente pueden editar
    if session["rol"] == "alumno":
        flash("No tienes permisos para editar recursos", "error")
        return redirect(url_for("recursos"))
    
    cursor = conexion.cursor(dictionary=True)

    if request.method == "POST":
        no_control = request.form["no_control"]
        fecha = request.form["fecha"]
        nombre = request.form["nombre"]
        estadisticas = request.form["estadisticas"]
        materia = request.form["materia"]
        tipo = request.form["tipo"]
        
        # Verificar si se subió un nuevo archivo
        archivo = request.files.get('archivo')
        filename = None
        
        if archivo and archivo.filename != '':
            filename = secure_filename(archivo.filename)
            archivo.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            
            cursor.execute("""
                UPDATE recursos
                SET no_control=%s, fecha=%s, nombre=%s, estadisticas=%s, materia=%s, tipo=%s, archivo=%s
                WHERE id=%s
            """, (no_control, fecha, nombre, estadisticas, materia, tipo, filename, id))
        else:
            # Mantener el archivo anterior si no se sube uno nuevo
            cursor.execute("""
                UPDATE recursos
                SET no_control=%s, fecha=%s, nombre=%s, estadisticas=%s, materia=%s, tipo=%s
                WHERE id=%s
            """, (no_control, fecha, nombre, estadisticas, materia, tipo, id))
            
        conexion.commit()
        cursor.close()
        flash("Recurso actualizado correctamente", "info")
        return redirect(url_for("recursos"))

    cursor.execute("SELECT * FROM recursos WHERE id=%s", (id,))
    recurso = cursor.fetchone()
    cursor.close()
    return render_template("editarrecursos.html", recurso=recurso)


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
        recursos_data = [['ID', 'No. Control', 'Nombre', 'Materia', 'Tipo', 'Fecha']]
        for r in recursos:
            recursos_data.append([
                str(r['id']),
                r['no_control'],
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