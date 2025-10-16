from pydantic import BaseModel
from typing import Optional

# Esquema para el formulario de contacto
class MensajeCreate(BaseModel):
    nombre: str
    correo: str
    telefono: Optional[str] = None
    mensaje: str

# Esquema para los vehículos
class Vehiculo(BaseModel):
    id: int
    marca: str
    modelo: str
    placa: str
    anio: int
    tipo: str
    capacidad: str
    observaciones: Optional[str] = None
    foto: Optional[str] = None

    model_config = {
        "from_attributes": True   # Pydantic v2 en lugar de orm_mode
    }
