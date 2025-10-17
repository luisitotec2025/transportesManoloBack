from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import logging
import sys
from dotenv import load_dotenv

# Sendgrid (reemplaza a Gmail)
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail

import database
import models
import schemas
from pydantic import BaseModel

import cloudinary
import cloudinary.uploader

# ✅ CONFIGURAR LOGGING CORRECTAMENTE
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.StreamHandler(sys.stderr)
    ]
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL")
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
FROM_EMAIL = os.getenv("FROM_EMAIL", "noreply@transportesmanolo.com")
TO_EMAIL = os.getenv("TO_EMAIL", "blancoluisalfredo778@gmail.com")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Debug: Verificar variables
print("✅ SENDGRID_API_KEY:", "***" if SENDGRID_API_KEY else "❌ NO CONFIGURADO")
print("✅ FROM_EMAIL:", FROM_EMAIL)
print("✅ TO_EMAIL:", TO_EMAIL)

# Configurar Cloudinary
cloudinary.config(
    cloud_name=CLOUDINARY_CLOUD_NAME,
    api_key=CLOUDINARY_API_KEY,
    api_secret=CLOUDINARY_API_SECRET,
    secure=True
)

# Inicialización de la app
app = FastAPI(title="API Vehículos", version="1.0")

# Configuración de CORS
origins = [
    "http://localhost:3000",
    "https://transportesmanolofront.onrender.com"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Crear tablas si no existen
try:
    database.Base.metadata.create_all(bind=database.engine)
    print("✅ Tablas creadas correctamente")
except Exception as e:
    print("❌ Error al crear tablas:", e)

# Dependencia de sesión DB
def get_db():
    db = database.SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Root
@app.get("/")
def root():
    return {"mensaje": "🚀 Backend de Transportes Manolo activo"}

# TEST: Endpoint para probar envío de correo
@app.get("/test-email/")
def test_email():
    """Endpoint de prueba para verificar que el envío de correo funciona"""
    logger.info("🧪 TEST EMAIL: Iniciando prueba de correo...")
    
    datos_prueba = {
        "nombre": "PRUEBA TEST",
        "telefono": "1234567890",
        "fecha": "2025-10-17",
        "comentario": "Este es un correo de prueba",
        "marca": "Toyota",
        "modelo": "Hiace",
        "anio": 2023,
        "placa": "TEST-123",
        "tipo": "Van",
        "vehiculo_id": 1,
        "foto_url": "https://via.placeholder.com/300"
    }
    
    resultado = enviar_correo_cotizacion(datos_prueba)
    
    return {
        "mensaje": "Prueba de correo completada",
        "resultado": "Exitoso ✅" if resultado else "Fallido ❌",
        "check_logs": "Revisa los logs de Render para ver los detalles"
    }

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
    foto_url = None

    if foto:
        try:
            result = cloudinary.uploader.upload(
                foto.file,
                folder="vehiculos",
                public_id=f"{uuid.uuid4().hex}",
                overwrite=True,
                resource_type="image"
            )
            foto_url = result.get("secure_url")
        except Exception as e:
            print("❌ Error al subir imagen a Cloudinary:", e)

    nuevo = models.Vehiculo(
        marca=marca,
        modelo=modelo,
        placa=placa,
        anio=anio,
        tipo=tipo,
        capacidad=capacidad,
        observaciones=observaciones,
        foto=foto_url
    )

    db.add(nuevo)
    db.commit()
    db.refresh(nuevo)

    return {"mensaje": "✅ Vehículo agregado correctamente", "id": nuevo.id, "foto_url": foto_url}

# Eliminar vehiculo
@app.delete("/vehiculos/eliminar/{vehiculo_id}", summary="Eliminar un vehículo por ID")
def eliminar_vehiculo(vehiculo_id: int, db: Session = Depends(get_db)):
    vehiculo = db.query(models.Vehiculo).filter(models.Vehiculo.id == vehiculo_id).first()
    if not vehiculo:
        raise HTTPException(status_code=404, detail="Vehículo no encontrado")
    
    db.delete(vehiculo)
    db.commit()
    return {"mensaje": "✅ Vehículo eliminado correctamente", "id": vehiculo_id}

# ============================================================
# FUNCIÓN PARA ENVIAR CORREO CON SENDGRID
# ============================================================
def enviar_correo_cotizacion(datos: dict):
    """Envía correo usando Sendgrid (funciona en Render)"""
    try:
        logger.info("=" * 70)
        logger.info("🧪 INICIANDO ENVÍO DE CORREO CON SENDGRID")
        logger.info("=" * 70)
        logger.info(f"SENDGRID_API_KEY configurada: {bool(SENDGRID_API_KEY)}")
        logger.info(f"FROM_EMAIL: {FROM_EMAIL}")
        logger.info(f"TO_EMAIL: {TO_EMAIL}")
        logger.info(f"Cliente: {datos.get('nombre')}")
        
        if not SENDGRID_API_KEY:
            logger.error("❌ FALTA SENDGRID_API_KEY en variables de entorno")
            return False

        logger.info("✅ Sendgrid API Key detectada")

        foto_html = f'<img src="{datos["foto_url"]}" alt="Foto del vehículo" style="max-width:100%;border-radius:8px;margin-top:10px;" />' \
                    if datos.get("foto_url") else "<p style='color:#888;'>Sin foto disponible</p>"

        html_content = f"""
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

        logger.info("📧 Construyendo mensaje de correo...")
        
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=TO_EMAIL,
            subject=f"📩 Nueva cotización: {datos['nombre']}",
            html_content=html_content
        )

        logger.info("📧 Inicializando cliente de Sendgrid...")
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        
        logger.info("📧 Enviando correo a través de Sendgrid...")
        response = sg.send(message)
        
        logger.info(f"✅✅✅ ¡CORREO ENVIADO CORRECTAMENTE!")
        logger.info(f"✅ Código de estado: {response.status_code}")
        logger.info("=" * 70)
        return True

    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"❌ ERROR AL ENVIAR CORREO: {type(e).__name__}")
        logger.error(f"Detalles: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("=" * 70)
        return False

# ============================================================
# ENDPOINT: AGREGAR COTIZACIÓN
# ============================================================
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

    foto_url = vehiculo.foto

    datos_correo = cotizacion.dict()
    datos_correo.update({
        "marca": vehiculo.marca,
        "modelo": vehiculo.modelo,
        "anio": vehiculo.anio,
        "placa": vehiculo.placa,
        "tipo": vehiculo.tipo,
        "foto_url": foto_url
    })

    # Enviar correo
    enviar_correo_cotizacion(datos_correo)
    
    return {"mensaje": "✅ Cotización enviada correctamente", "status": "success"}