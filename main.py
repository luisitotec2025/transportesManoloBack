from fastapi import FastAPI, Depends, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import uuid
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import socket
import sys
import logging

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

import database
import models
import schemas
from pydantic import BaseModel

import cloudinary
import cloudinary.uploader

# Cargar variables de entorno
load_dotenv()
BACKEND_URL = os.getenv("BACKEND_URL")
GMAIL_USER = os.getenv("GMAIL_USER")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD")
CLOUDINARY_CLOUD_NAME = os.getenv("CLOUDINARY_CLOUD_NAME")
CLOUDINARY_API_KEY = os.getenv("CLOUDINARY_API_KEY")
CLOUDINARY_API_SECRET = os.getenv("CLOUDINARY_API_SECRET")

# Debug: Verificar variables
print("✅ GMAIL_USER:", GMAIL_USER)
print("✅ GMAIL_APP_PASSWORD:", "***" if GMAIL_APP_PASSWORD else "❌ NO CONFIGURADO")

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
    print("🧪 TEST EMAIL: Iniciando prueba de correo...", flush=True)
    
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
        "resultado": "Exitoso" if resultado else "Fallido",
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
# FUNCIÓN MEJORADA PARA ENVIAR CORREO (CON LOGGING)
# ============================================================
def enviar_correo_cotizacion(datos: dict):
    """Envía correo con logging que se muestra en Render"""
    try:
        logger.info("=" * 60)
        logger.info("🧪 INICIANDO ENVÍO DE CORREO")
        logger.info("=" * 60)
        logger.info(f"GMAIL_USER: {GMAIL_USER}")
        logger.info(f"GMAIL_APP_PASSWORD configurada: {bool(GMAIL_APP_PASSWORD)}")
        logger.info(f"Nombre del cliente: {datos.get('nombre')}")
        
        if not GMAIL_USER or not GMAIL_APP_PASSWORD:
            logger.error("❌ FALTA GMAIL_USER O GMAIL_APP_PASSWORD")
            return False

        logger.info("✅ Variables de entorno detectadas")

        foto_html = f'<img src="{datos["foto_url"]}" alt="Foto del vehículo" style="max-width:100%;border-radius:8px;margin-top:10px;" />' \
                    if datos.get("foto_url") else "<p style='color:#888;'>Sin foto disponible</p>"

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

        logger.info("📧 Construyendo mensaje de correo...")
        logger.info("📧 Conectando a SMTP Gmail en puerto 587...")
        
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=15) as server:
            logger.info("📧 ✅ Conexión establecida")
            
            logger.info("📧 Iniciando TLS...")
            server.starttls()
            logger.info("📧 ✅ TLS iniciado")
            
            logger.info(f"📧 Intentando login con: {GMAIL_USER}")
            server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
            logger.info("📧 ✅ Login exitoso")
            
            logger.info(f"📧 Enviando correo a: {GMAIL_USER}...")
            result = server.sendmail(GMAIL_USER, GMAIL_USER, msg.as_string())
            
            logger.info(f"✅✅✅ ¡CORREO ENVIADO CORRECTAMENTE!")
            logger.info(f"✅ Resultado del envío: {result}")
            logger.info("=" * 60)
            return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error("=" * 60)
        logger.error("❌ ERROR DE AUTENTICACIÓN SMTP")
        logger.error(f"Detalles del error: {str(e)}")
        logger.error(f"Usuario usado: {GMAIL_USER}")
        logger.error("Verifica que:")
        logger.error("   1. GMAIL_USER sea correcto")
        logger.error("   2. GMAIL_APP_PASSWORD sea la contraseña de APLICACIÓN (16 caracteres)")
        logger.error("   3. La autenticación de 2 factores esté HABILITADA en Gmail")
        logger.error("   4. La contraseña de aplicación sea para 'Correo' en Google")
        logger.error("=" * 60)
        return False
        
    except socket.timeout:
        logger.error("=" * 60)
        logger.error("❌ TIMEOUT: No se pudo conectar a SMTP Gmail (timeout de 15 segundos)")
        logger.error("Posible problema de red o Gmail bloqueando a Render")
        logger.error("=" * 60)
        return False
        
    except smtplib.SMTPException as e:
        logger.error("=" * 60)
        logger.error(f"❌ ERROR SMTP GENERAL: {type(e).__name__}")
        logger.error(f"Detalles: {str(e)}")
        logger.error("=" * 60)
        return False
        
    except Exception as e:
        logger.error("=" * 60)
        logger.error(f"❌ ERROR INESPERADO: {type(e).__name__}")
        logger.error(f"Detalles: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        logger.error("=" * 60)
        return False

# ============================================================
# ENDPOINT: AGREGAR COTIZACIÓN (MEJORADO)
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

    # ✅ Enviar correo directamente (sin background para que veas los logs)
    enviar_correo_cotizacion(datos_correo)
    
    # ✅ Respuesta inmediata al cliente
    return {"mensaje": "✅ Cotización enviada correctamente", "status": "success"}