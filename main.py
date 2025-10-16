from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List, Optional
import shutil
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

import database
import models
import schemas

# ------------------------------
# Cargar variables de entorno
# ------------------------------
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")

# ------------------------------
# Inicialización de la app
# ------------------------------
app = FastAPI(title="API Vehículos", version="1.0")

# ------------------------------
# Configuración de CORS
# ------------------------------
origins = [
    "http://localhost:3000",  # Frontend React local
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------
# Crear tablas si no existen
# ------------------------------
try:
    database.Base.metadata.create_all(bind=database.engine)
    print("✅ Tablas creadas correctamente")
except Exception as e:
    print("❌ Error al crear tablas:", e)

# ------------------------------
# Dependencia de sesión DB
# ------------------------------
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ------------------------------
# Directorio público de imágenes
# ------------------------------
IMAGES_DIR = os.path.join(os.getcwd(), "public", "vehiculosimg")
os.makedirs(IMAGES_DIR, exist_ok=True)
app.mount("/vehiculosimg", StaticFiles(directory=IMAGES_DIR), name="vehiculosimg")

# ------------------------------
# Endpoints
# ------------------------------
# Contacto
@app.post("/contacto/")
def enviar_mensaje(mensaje: schemas.MensajeCreate, db: Session = Depends(get_db)):
    nuevo_mensaje = models.Mensaje(**mensaje.dict())
    db.add(nuevo_mensaje)
    db.commit()
    db.refresh(nuevo_mensaje)
    return {"mensaje": "Mensaje enviado correctamente", "id": nuevo_mensaje.id}

# Listar vehículos
@app.get("/vehiculos/", response_model=List[schemas.Vehiculo])
def listar_vehiculos(db: Session = Depends(get_db)):
    return db.query(models.Vehiculo).all()

# Agregar vehículo
@app.post("/vehiculos/agregar/")
def agregar_vehiculo(
    marca: str = Form(...),
    modelo: str = Form(...),
    placa: str = Form(...),
    anio: int = Form(...),
    tipo: str = Form(...),
    capacidad: str = Form(...),
    observaciones: str = Form(None),
    foto: UploadFile = File(None),
    db: Session = Depends(get_db)
):
    foto_path = None

    if foto:
        ext = os.path.splitext(foto.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(IMAGES_DIR, unique_name)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)
        foto_path = f"/vehiculosimg/{unique_name}"

    nuevo = models.Vehiculo(
        marca=marca,
        modelo=modelo,
        placa=placa,
        anio=anio,
        tipo=tipo,
        capacidad=capacidad,
        observaciones=observaciones,
        foto=foto_path
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    # URL absoluta para Render
    image_url = f"{BACKEND_URL}{foto_path}" if foto_path else None

    return {
        "mensaje": "✅ Vehículo agregado correctamente",
        "id": nuevo.id,
        "foto_url": image_url
    }

# ------------------------------
# Función para enviar correo HTML
# ------------------------------
def enviar_correo_cotizacion(datos: dict):
    try:
        if not GMAIL_USER or not GMAIL_APP_PASSWORD:
            print("⚠️ Falta GMAIL_USER o GMAIL_APP_PASSWORD en .env")
            return

        # Preparar foto HTML
        foto_html = f'<img src="{datos["foto_url"]}" alt="Foto del vehículo" style="max-width:100%;border-radius:8px;margin-top:10px;" />' \
                    if datos.get("foto_url") else "<p style='color:#888;'>Sin foto disponible</p>"

        # Crear mensaje
        msg = MIMEMultipart("alternative")
        msg["From"] = GMAIL_USER
        msg["To"] = GMAIL_USER
        msg["Subject"] = f"📩 Nueva cotización: {datos['nombre']}"

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width:650px; margin:20px auto; border:1px solid #e0e0e0; border-radius:12px; overflow:hidden; box-shadow:0 4px 20px rgba(0,0,0,0.1); background:white;">
            <div style="background: linear-gradient(120deg, #1976D2, #0D47A1); color:white; padding:24px; text-align:center;">
                <h2>Nueva Solicitud de Cotización</h2>
            </div>
            <div style="padding:24px;">
                <h3 style="color:#1976D2;">👤 Datos del Cliente</h3>
                <p><strong>Nombre:</strong> {datos['nombre']}</p>
                <p><strong>Teléfono:</strong> {datos['telefono']}</p>
                <p><strong>Fecha de servicio:</strong> {datos['fecha']}</p>
                <p><strong>Comentario:</strong> {datos.get('comentario', '—')}</p>
            </div>
            <div style="padding:24px; background:#f5f9ff;">
                <h3>🚛 Información del Vehículo</h3>
                <p><strong>Marca:</strong> {datos['marca']}</p>
                <p><strong>Modelo:</strong> {datos['modelo']}</p>
                <p><strong>Año:</strong> {datos['anio']}</p>
                <p><strong>Placa:</strong> {datos['placa']}</p>
                <p><strong>Tipo:</strong> {datos['tipo']}</p>
                <h4>📸 Foto del vehículo:</h4>
                {foto_html}
            </div>
            <div style="text-align:center; padding:16px; background:#e3f2fd;">
                ID del vehículo: <strong>{datos['vehiculo_id']}</strong>
            </div>
        </div>
        """

        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())

        print("✅ Correo HTML con datos del vehículo enviado")
    except Exception as e:
        print("❌ Error al enviar correo:", e)

# ------------------------------
# Endpoint: Agregar cotización
# ------------------------------
class CotizacionRequest(BaseModel):
    vehiculo_id: int
    nombre: str
    telefono: str
    fecha: str
    comentario: Optional[str] = None

@app.post("/cotizaciones/agregar/")
def agregar_cotizacion(cotizacion: CotizacionRequest, db: Session = Depends(get_db)):
    vehiculo = db.query(models.Vehiculo).filter(models.Vehiculo.id == cotizacion.vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")

    # URL de la foto para Render
    if vehiculo.foto:
        foto_url = f"{BACKEND_URL}{vehiculo.foto}"
    else:
        foto_url = None

    datos_correo = cotizacion.dict()
    datos_correo.update({
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "placa": vehiculo.placa,
        "tipo": vehiculo.tipo,
        "foto_url": foto_url
    })

    enviar_correo_cotizacion(datos_correo)
    return {"mensaje": "Cotización enviada correctamente"}
