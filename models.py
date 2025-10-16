import database
from sqlalchemy import Column, Integer, String, Text, DateTime
from datetime import datetime

class Mensaje(database.Base):
    __tablename__ = "mensajes"
    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    correo = Column(String(100), nullable=False)
    telefono = Column(String(20))
    mensaje = Column(Text, nullable=False)
    fecha = Column(DateTime, default=datetime.utcnow)



from sqlalchemy import Column, Integer, String
from database import Base

class Vehiculo(Base):
    __tablename__ = "vehiculos"

    id = Column(Integer, primary_key=True, index=True)
    marca = Column(String, nullable=False)
    modelo = Column(String, nullable=False)
    placa = Column(String, nullable=False)
    anio = Column(Integer, nullable=False)
    tipo = Column(String, nullable=False)
    capacidad = Column(String, nullable=False)
    observaciones = Column(String, nullable=True)
    foto = Column(String, nullable=True)  