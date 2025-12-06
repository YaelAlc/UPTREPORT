from flask import Flask, request, render_template, redirect, url_for, session, flash, send_file
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from pymongo import MongoClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from itsdangerous import URLSafeTimedSerializer as Serializer
from bson.binary import Binary
from bson.objectid import ObjectId
from fpdf import FPDF
from PIL import Image
import os
import uuid



#inicializacion de la framework
app = Flask(__name__)
bcrypt = Bcrypt(app)

# Clave secreta para sesiones
app.secret_key = os.getenv("SECRET_KEY")

# Configuración de MongoDB Atlas
#kevin.cortes37
client = MongoClient(os.getenv("MONGO_URI"))#MAL = CONTRASEÑA NOSE
db = client['BD1'] #Nombre de tu base de datos aquí
collection = db['Usuarios'] #Nombre de tu colección aquí
collection_reports = db['Reportes']

# Configuración de SendGrid
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")

# Serializador para crear y verificar tokens
serializer = Serializer(app.secret_key, salt='password-reset-salt')

# Función para enviar correos
def enviar_email(destinatario, asunto, cuerpo):
    mensaje = Mail(
        from_email='kcg8377@gmail.com',  # Cambia esto por tu correo
        to_emails=destinatario,
        subject=asunto,
        html_content=cuerpo
    )
    try:
        sg = SendGridAPIClient(SENDGRID_API_KEY)  # Usa tu clave API de SendGrid directamente
        response = sg.send(mensaje)
        print(f"Correo enviado con éxito! Status code: {response.status_code}")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")

@app.route('/')
def home():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return (url_for('pagina_principal'))

#--------------------------GUIA--------------------------------#
@app.route('/registro', methods=['GET', 'POST'])
def registro():
    if request.method == 'POST':
        usuario = request.form['usuario']
        email = request.form['email']
        contrasena = request.form['contrasena']

        # Verificar si el correo ya está registrado
        if collection.find_one({'email': email}):
            flash("El correo electrónico ya está registrado.")
            return redirect(url_for('registro'))

        # Hashear la contraseña
        hashed_password = bcrypt.generate_password_hash(contrasena).decode('utf-8')

        # Insertar usuario en la base de datos
        collection.insert_one({
            'usuario': usuario,
            'email': email,
            'contrasena': hashed_password,
            'rol':"usuario"
        })
        
        session['usuario'] = usuario
        return redirect(url_for('pagina_principal'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']

        # Buscar al usuario en la base de datos
        user = collection.find_one({'usuario': usuario})
        
        # Verificar si las credenciales son correctas
        if user and bcrypt.check_password_hash(user['contrasena'], contrasena):
            session['usuario'] = usuario
            return redirect(url_for('pagina_principal'))
        else:
            flash("Usuario o contraseña incorrectos.")
            return render_template('login.html')

    return render_template('login.html')
#/////
# ///////////////////////////////////////---////////////////////////////////////////////////////////////////////////////////////////////////////////////////-----/////////

@app.route('/pagina_principal', methods=['GET', 'POST'])
def pagina_principal():
    if request.method == 'POST':
        nombre = request.form['nombre']
        matricula = request.form['matricula']
        grupo = request.form['grupo']
        edificio = request.form['pais']
        salon = request.form['ciudad']
        incidencia = request.form['incidencia']
        descripcion = request.form['descripcion']
        evidencia = request.files['evidencia']
        fecha = request.form['fecha']

        if not evidencia or evidencia.filename == '':
            return "Imagen requerida", 400

        ALLOWED_EXTENSIONS = {'jpg', 'jpeg'}

        def extension_valida(nombre_archivo):
            return '.' in nombre_archivo and \
                nombre_archivo.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

        if not extension_valida(evidencia.filename):
            return "Solo se permiten imágenes en formato JPG/JPEG", 400

        # Obtener extensión original
        extension = evidencia.filename.rsplit('.', 1)[1].lower()
        nombre_imagen = f"temp_{uuid.uuid4().hex}.{extension}"
        path_imagen = os.path.join('static', secure_filename(nombre_imagen))

        # Guardar imagen temporalmente
        evidencia.save(path_imagen)

        # Leer imagen como binario para MongoDB
        with open(path_imagen, 'rb') as img_file:
            imagen_binaria = Binary(img_file.read())

        # Insertar en MongoDB
        collection_reports.insert_one({
            'usuario': session['usuario'],
            'nombre': nombre,
            'matricula': matricula,
            'grupo': grupo,
            'pais': edificio,
            'ciudad': salon,
            'incidencia': incidencia,
            'descripcion': descripcion,
            'evidencia': imagen_binaria,
            'fecha' : fecha
        })

        # Crear PDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", size=12)
        pdf.cell(200, 10, txt="Reporte de Incidencia", ln=True, align='C')
        pdf.ln(10)
        pdf.cell(200, 10, txt=f"Nombre: {nombre}", ln=True)
        pdf.cell(200, 10, txt=f"Matrícula: {matricula}", ln=True)
        pdf.cell(200, 10, txt=f"Grupo: {grupo}", ln=True)
        pdf.cell(200, 10, txt=f"Edificio: {edificio}", ln=True)
        pdf.cell(200, 10, txt=f"Salón: {salon}", ln=True)
        pdf.cell(200, 10, txt=f"Tipo de Incidencia: {incidencia}", ln=True)
        pdf.multi_cell(0, 10, txt=f"Descripción: {descripcion}")
        pdf.cell(200, 10, txt=f"Fecha: {fecha}", ln=True)
        pdf.ln(10)

        # Agregar imagen JPG al PDF
        try:
            with Image.open(path_imagen) as img:
                img_width, img_height = img.size
                aspect_ratio = img_height / img_width
                pdf_width = 100
                pdf_height = pdf_width * aspect_ratio

            pdf.image(path_imagen, x=10, y=pdf.get_y(), w=pdf_width, h=pdf_height)
        except:
            pdf.cell(200, 10, txt=" Error al cargar la imagen", ln=True)

        # Guardar PDF
        nombre_pdf = f"reporte_{uuid.uuid4().hex}.pdf"
        path_pdf = os.path.join('static', nombre_pdf)
        pdf.output(path_pdf)

        # Eliminar imagen temporal
        os.remove(path_imagen)

        return send_file(path_pdf, as_attachment=True)

    else:
        if 'usuario' not in session:
            return redirect(url_for('login'))
        return render_template('index.html', usuario=session['usuario'])



#///////////////////////////////////////////////////////////////////////
@app.route('/mi_perfil') #Creo que tambien se modifica esto si se quiere en perfilÑ
def mi_perfil():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    usuario = session['usuario']
    user_data = collection.find_one({'usuario': usuario})
    return render_template('mi_perfil.html', usuario=user_data['usuario'], email=user_data['email'])

@app.route('/notificaciones')
def notificaciones():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    usuario = session['usuario']
    user_data =collection.find_one({'usuario': usuario})
    if user_data.get('rol') == 'admin':
        incidencias = list(collection_reports.find({}, {
        '_id': 0, 
        'incidencia': 1, 
        'estado': 1
    }))
    else:
        incidencias = list(collection_reports.find({'usuario':usuario}, {
        '_id': 0, 
        'incidencia': 1, 
        'estado': 1
    }))
    
    return render_template('notificaciones.html', usuario=session['usuario'], incidencias=incidencias)

@app.route('/login_admin', methods=['GET','POST'])
def login_admin():
    if request.method == 'POST':
        usuario = request.form['usuario']
        contrasena = request.form['contrasena']

        # Buscar al usuario en la base de datos
        user = collection.find_one({'usuario': usuario})
        
        # Verificar si las credenciales son correctas
        if user and bcrypt.check_password_hash(user['contrasena'], contrasena):
            if user.get('rol') == 'admin':
                session['usuario'] = usuario
                return redirect(url_for('pagina_principal_admin'))
            else:
                flash("No tienes permisos de administrador.", "error")
                return render_template('login_admin.html')
        else:
            flash("Usuario o contraseña incorrectos .")
            return render_template('login_admin.html')

    return render_template('login_admin.html')

@app.route('/pagina_principal_admin', methods=['GET','POST'])
def pagina_principal_admin():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        id_incidencia = request.form['id']
        nuevo_estado = request.form['estado']

        collection_reports.update_one(
            {'_id': ObjectId(id_incidencia)},
            {'$set': {'estado': nuevo_estado}}
        )
        return redirect(url_for('pagina_principal_admin'))

    incidencias = list(collection_reports.find({}, {
        '_id': 1,
        'incidencia': 1,
        'estado': 1
    }))
    return render_template('pagina_principal_admin.html', usuario=session['usuario'],incidencias=incidencias)

@app.route('/recuperar_contrasena', methods=['GET', 'POST'])
def recuperar_contrasena():
    if request.method == 'POST':
        email = request.form['email']
        usuario = collection.find_one({'email': email})

        if usuario:
            token = serializer.dumps(email, salt='password-reset-salt')
            enlace = url_for('restablecer_contrasena', token=token, _external=True)
            asunto = "Recuperación de contraseña"
            cuerpo = f"""
            <p>Hola, hemos recibido una solicitud para restablecer tu contraseña.</p>
            <p>Si no has solicitado este cambio, ignora este mensaje.</p>
            <p>Para restablecer tu contraseña, haz clic en el siguiente enlace:</p>
            <a href="{enlace}">Restablecer contraseña</a>
            """
            enviar_email(email, asunto, cuerpo)
            flash("Te hemos enviado un correo para recuperar tu contraseña.", "success")
        else:
            flash("El correo electrónico no está registrado.", "error")

    return render_template('recuperar_contrasena.html')

@app.route('/restablecer_contrasena/<token>', methods=['GET', 'POST'])
def restablecer_contrasena(token):
    try:
        email = serializer.loads(token, salt='password-reset-salt', max_age=3600)
    except:
        flash("El enlace de restablecimiento ha caducado o es inválido.", "error")
        return redirect(url_for('recuperar_contrasena'))

    if request.method == 'POST':
        nueva_contrasena = request.form['nueva_contrasena']
        hashed_password = bcrypt.generate_password_hash(nueva_contrasena).decode('utf-8')
        collection.update_one({'email': email}, {'$set': {'contrasena': hashed_password}})
        flash("Tu contraseña ha sido restablecida con éxito.", "success")
        return redirect(url_for('login'))

    return render_template('restablecer_contrasena.html')

@app.route('/logout')
def logout():
    session.pop('usuario', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run()
