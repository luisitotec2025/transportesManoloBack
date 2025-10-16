from fastapi import FastAPI, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from typing import List
import shutil
import os
import uuid

import database
import models
import schemas

# -----------------------------------
# Inicialización de la aplicación
# -----------------------------------
app = FastAPI(title="API Vehículos", version="1.0")

# -----------------------------------
# Configuración de CORS
# -----------------------------------
origins = [
    "http://localhost:3000",  # URL del frontend React
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------------
# Crear tablas si no existen
# -----------------------------------
try:
    database.Base.metadata.create_all(bind=database.engine)
    print("✅ Tablas creadas correctamente")
except Exception as e:
    print("❌ Error al crear tablas:", e)

# -----------------------------------
# Dependencia de sesión de base de datos
# -----------------------------------
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# -----------------------------------
# Directorio público para imágenes
# -----------------------------------
IMAGES_DIR = os.path.join(os.getcwd(), "public", "vehiculosimg")
os.makedirs(IMAGES_DIR, exist_ok=True)

# Hacer accesible la carpeta desde el navegador
app.mount("/vehiculosimg", StaticFiles(directory=IMAGES_DIR), name="vehiculosimg")

# -----------------------------------
# Endpoint: Formulario de contacto
# -----------------------------------
@app.post("/contacto/")
def enviar_mensaje(mensaje: schemas.MensajeCreate, db: Session = Depends(get_db)):
    nuevo_mensaje = models.Mensaje(**mensaje.dict())
    db.add(nuevo_mensaje)
    db.commit()
    db.refresh(nuevo_mensaje)
    return {"mensaje": "Mensaje enviado correctamente", "id": nuevo_mensaje.id}

# -----------------------------------
# Endpoint: Listar vehículos
# -----------------------------------
@app.get("/vehiculos/", response_model=List[schemas.Vehiculo])
def listar_vehiculos(db: Session = Depends(get_db)):
    return db.query(models.Vehiculo).all()

# -----------------------------------
# Endpoint: Agregar vehículo
# -----------------------------------
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

    # ✅ Guardar imagen solo una vez con nombre único
    if foto:
        ext = os.path.splitext(foto.filename)[1]
        unique_name = f"{uuid.uuid4().hex}{ext}"
        file_path = os.path.join(IMAGES_DIR, unique_name)

        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(foto.file, buffer)

        foto_path = f"/vehiculosimg/{unique_name}"

    # ✅ Crear registro en la base de datos
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

    # ✅ URL absoluta para mostrar en el frontend
    image_url = f"http://127.0.0.1:8000{foto_path}" if foto_path else None

    return {
        "mensaje": "✅ Vehículo agregado correctamente",
        "id": nuevo.id,
        "foto_url": image_url
    }


# -----------------------------------
# FUNCIÓN PARA ENVIAR CORREO POR GMAIL (HTML ESTILIZADO)
# -----------------------------------
# -----------------------------------
# FUNCIÓN PARA ENVIAR CORREO POR GMAIL (HTML ESTILIZADO CON DATOS DEL VEHÍCULO)
# -----------------------------------
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from fastapi import HTTPException

load_dotenv()

def enviar_correo_cotizacion(datos: dict):
    try:
        user = os.getenv("GMAIL_USER")
        pwd = os.getenv("GMAIL_APP_PASSWORD")
        if not user or not pwd:
            print("⚠️ Falta GMAIL_USER o GMAIL_APP_PASSWORD en .env")
            return

        msg = MIMEMultipart("alternative")
        msg["From"] = user
        msg["To"] = user
        msg["Subject"] = f"📩 Nueva cotización: {datos['nombre']}"

        foto_html = f'<img src="{datos["foto_url"]}" alt="Foto del vehículo" style="max-width: 100%; border-radius: 8px; margin-top: 10px;" />' if datos.get("foto_url") else "<p style='color: #888;'>Sin foto disponible</p>"

        html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 650px; margin: 20px auto; border: 1px solid #e0e0e0; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.1); background: white;">
            <div style="background: linear-gradient(120deg, #1976D2, #0D47A1); color: white; padding: 24px; text-align: center;">
                <h2 style="margin: 0; font-size: 24px; font-weight: 600;">Nueva Solicitud de Cotización</h2>
            </div>

            <div style="padding: 24px;">
                <h3 style="color: #1976D2; border-bottom: 2px solid #eee; padding-bottom: 10px;">👤 Datos del Cliente</h3>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Nombre:</strong> {datos['nombre']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Teléfono:</strong> {datos['telefono']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Fecha de servicio:</strong> {datos['fecha']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Comentario:</strong></p>
                <div style="background: #f8f9fa; padding: 14px; border-radius: 8px; border-left: 4px solid #1976D2; color: #444;">
                    {datos.get('comentario', '—') or '—'}
                </div>
            </div>

            <div style="padding: 24px; background: #f5f9ff;">
                <h3 style="color: #0D47A1; border-bottom: 2px solid #bbdefb; padding-bottom: 10px;">🚛 Información del Vehículo</h3>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Marca:</strong> {datos['marca']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Modelo:</strong> {datos['modelo']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Año:</strong> {datos['anio']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Placa:</strong> {datos['placa']}</p>
                <p style="margin: 10px 0; font-size: 16px;"><strong>Tipo:</strong> {datos['tipo']}</p>

                <h4 style="margin-top: 16px; color: #0D47A1;">📸 Foto del vehículo:</h4>
                {foto_html}
            </div>

            <div style="text-align: center; padding: 16px; background: #e3f2fd; color: #0D47A1; font-size: 14px;">
                ID del vehículo: <strong>{datos['vehiculo_id']}</strong>
            </div>
        </div>
        """

        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(user, pwd)
            server.sendmail(user, user, msg.as_string())
        print("✅ Correo HTML con datos del vehículo enviado")
    except Exception as e:
        print("❌ Error al enviar correo:", e)


# -----------------------------------
# Endpoint: Agregar cotización (mejorado con datos del vehículo)
# -----------------------------------
from pydantic import BaseModel
from typing import Optional

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

    datos_correo = cotizacion.dict()
    datos_correo.update({
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "placa": vehiculo.placa,
        "tipo": vehiculo.tipo,
        "foto_url": f"http://127.0.0.1:8000{vehiculo.foto}" if vehiculo.foto else None
    })

    enviar_correo_cotizacion(datos_correo)

    return {"mensaje": "Cotización enviada correctamente"}