"""
Ejemplo de uso del SDK de Atlantis - Cliente para otros microservicios

Este ejemplo muestra cómo integrar el SDK de Atlantis en otros microservicios
para gestionar bandejas, campos, registros y procesos de forma programática.
"""

import asyncio
import logging
from typing import Dict, List

# Import desde el directorio local (para testing)
import sys
import os
sys.path.append(os.path.dirname(__file__))

from client import AtlantisClient, AtlantisConfig, AtlantisException

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MiMicroservicio:
    """Ejemplo de integración del SDK en un microservicio"""
    
    def __init__(self, atlantis_url: str, auth_token: str = None):
        # Configurar cliente de Atlantis
        config = AtlantisConfig(
            base_url=atlantis_url,
            auth_token=auth_token,
            timeout=30.0,
            max_retries=3
        )
        self.atlantis = AtlantisClient(config=config)
    
    async def inicializar(self):
        """Inicializar conexión con Atlantis"""
        await self.atlantis.start_session()
        
        # Verificar conexión
        if not await self.atlantis.test_connection():
            raise Exception("No se pudo conectar a Atlantis")
        
        logger.info("✅ Conectado a Atlantis")
    
    async def cerrar(self):
        """Cerrar conexión"""
        await self.atlantis.close_session()
    
    async def configurar_bandeja_solicitudes(self) -> dict:
        """Configurar bandeja de solicitudes con sus campos"""
        try:
            # Crear bandeja
            bandeja = await self.atlantis.bandejas.crear(
                nombre="Solicitudes de Crédito",
                descripcion="Procesos de solicitudes de crédito",
                grupo="creditos",
                color="#2ecc71"
            )
            
            logger.info(f"📁 Bandeja creada: {bandeja['nombre']} ({bandeja['id']})")
            
            # Crear campos de la bandeja
            campos = [
                {
                    "nombre": "numero_solicitud",
                    "etiqueta": "Número de Solicitud",
                    "tipo": "string",
                    "requerido": True,
                    "mostrar_en_tabla": True,
                    "posicion": 1
                },
                {
                    "nombre": "cliente_nombre",
                    "etiqueta": "Nombre del Cliente",
                    "tipo": "string",
                    "requerido": True,
                    "mostrar_en_tabla": True,
                    "posicion": 2
                },
                {
                    "nombre": "cliente_email",
                    "etiqueta": "Email",
                    "tipo": "email",
                    "requerido": True,
                    "mostrar_en_tabla": False,
                    "posicion": 3
                },
                {
                    "nombre": "monto_solicitado",
                    "etiqueta": "Monto Solicitado",
                    "tipo": "number",
                    "requerido": True,
                    "mostrar_en_tabla": True,
                    "posicion": 4
                },
                {
                    "nombre": "tipo_credito",
                    "etiqueta": "Tipo de Crédito",
                    "tipo": "enum",
                    "requerido": True,
                    "opciones_enum": ["personal", "hipotecario", "vehicular", "empresarial"],
                    "mostrar_en_tabla": True,
                    "posicion": 5
                },
                {
                    "nombre": "fecha_solicitud",
                    "etiqueta": "Fecha de Solicitud",
                    "tipo": "datetime",
                    "requerido": True,
                    "mostrar_en_tabla": True,
                    "posicion": 6
                },
                {
                    "nombre": "observaciones",
                    "etiqueta": "Observaciones",
                    "tipo": "text",
                    "requerido": False,
                    "mostrar_en_tabla": False,
                    "posicion": 7
                }
            ]
            
            for campo_data in campos:
                campo = await self.atlantis.campos.crear(
                    bandeja_id=bandeja["id"],
                    **campo_data
                )
                logger.info(f"📝 Campo creado: {campo['etiqueta']}")
            
            return bandeja
            
        except AtlantisException as e:
            logger.error(f"❌ Error configurando bandeja: {e}")
            raise
    
    async def configurar_estatus_workflow(self) -> List[dict]:
        """Configurar estatus del workflow de solicitudes"""
        estatus_configs = [
            {
                "codigo": "RECIBIDA",
                "nombre": "Recibida",
                "descripcion": "Solicitud recibida, pendiente de revisión",
                "color": "#3498db",
                "orden": 1
            },
            {
                "codigo": "EN_REVISION",
                "nombre": "En Revisión",
                "descripcion": "Solicitud en proceso de revisión",
                "color": "#f39c12",
                "orden": 2
            },
            {
                "codigo": "DOCUMENTOS_PENDIENTES",
                "nombre": "Documentos Pendientes",
                "descripcion": "Faltan documentos por entregar",
                "color": "#e74c3c",
                "orden": 3
            },
            {
                "codigo": "APROBADA",
                "nombre": "Aprobada",
                "descripcion": "Solicitud aprobada",
                "color": "#27ae60",
                "orden": 4
            },
            {
                "codigo": "RECHAZADA",
                "nombre": "Rechazada",
                "descripcion": "Solicitud rechazada",
                "color": "#c0392b",
                "orden": 5
            }
        ]
        
        estatus_creados = []
        for config in estatus_configs:
            try:
                estatus = await self.atlantis.estatus.crear(**config)
                estatus_creados.append(estatus)
                logger.info(f"📊 Estatus creado: {estatus['nombre']}")
            except AtlantisException as e:
                logger.warning(f"⚠️  Error creando estatus {config['codigo']}: {e}")
        
        return estatus_creados
    
    async def procesar_nueva_solicitud(
        self,
        bandeja_id: str,
        estatus_recibida_id: str,
        datos_solicitud: dict
    ) -> dict:
        """Procesar una nueva solicitud de crédito"""
        try:
            # Crear registro en Atlantis
            registro = await self.atlantis.registros.crear(
                bandeja_id=bandeja_id,
                estatus_id=estatus_recibida_id,
                datos=datos_solicitud
            )
            
            logger.info(f"📄 Nueva solicitud registrada: {registro['id']}")
            
            # Aquí puedes agregar lógica adicional de tu microservicio
            # - Validaciones de negocio
            # - Integraciones con otros sistemas
            # - Notificaciones
            
            return registro
            
        except AtlantisException as e:
            logger.error(f"❌ Error procesando solicitud: {e}")
            raise
    
    async def buscar_solicitudes_cliente(
        self,
        bandeja_id: str,
        nombre_cliente: str
    ) -> List[dict]:
        """Buscar solicitudes de un cliente específico"""
        try:
            resultado = await self.atlantis.registros.buscar(
                bandeja_id=bandeja_id,
                query=nombre_cliente,
                campos=["cliente_nombre", "cliente_email"]
            )
            
            logger.info(f"🔍 Encontradas {resultado['total']} solicitudes para '{nombre_cliente}'")
            return resultado["items"]
            
        except AtlantisException as e:
            logger.error(f"❌ Error buscando solicitudes: {e}")
            return []
    
    async def actualizar_estatus_solicitud(
        self,
        registro_id: str,
        nuevo_estatus_id: str,
        observaciones: str = ""
    ) -> dict:
        """Actualizar el estatus de una solicitud"""
        try:
            # Actualizar registro
            registro_actualizado = await self.atlantis.registros.actualizar(
                registro_id=registro_id,
                estatus_id=nuevo_estatus_id,
                datos={"observaciones": observaciones}
            )
            
            logger.info(f"🔄 Estatus actualizado para registro {registro_id}")
            return registro_actualizado
            
        except AtlantisException as e:
            logger.error(f"❌ Error actualizando estatus: {e}")
            raise
    
    async def obtener_historial_solicitud(self, registro_id: str) -> List[dict]:
        """Obtener historial completo de una solicitud"""
        try:
            movimientos = await self.atlantis.registros.obtener_movimientos(registro_id)
            logger.info(f"📚 Obtenido historial de {len(movimientos)} movimientos")
            return movimientos
            
        except AtlantisException as e:
            logger.error(f"❌ Error obteniendo historial: {e}")
            return []


async def ejemplo_integracion_completa():
    """Ejemplo completo de integración"""
    
    # Configurar microservicio
    microservicio = MiMicroservicio(
        atlantis_url="http://localhost:8000",
        auth_token=None  # Agregar token si es necesario
    )
    
    try:
        # Inicializar
        await microservicio.inicializar()
        
        # Configurar infraestructura
        logger.info("🏗️  Configurando infraestructura...")
        bandeja = await microservicio.configurar_bandeja_solicitudes()
        estatus_list = await microservicio.configurar_estatus_workflow()
        
        # Obtener estatus "RECIBIDA"
        estatus_recibida = next(
            (e for e in estatus_list if e["codigo"] == "RECIBIDA"),
            None
        )
        
        if not estatus_recibida:
            logger.error("❌ No se pudo crear estatus RECIBIDA")
            return
        
        # Procesar solicitudes de ejemplo
        logger.info("📋 Procesando solicitudes de ejemplo...")
        
        solicitudes_ejemplo = [
            {
                "numero_solicitud": "SOL-2024-001",
                "cliente_nombre": "Juan Pérez González",
                "cliente_email": "juan.perez@email.com",
                "monto_solicitado": 250000.00,
                "tipo_credito": "hipotecario",
                "fecha_solicitud": "2024-01-15T10:30:00Z",
                "observaciones": "Cliente recurrente, historial crediticio excelente"
            },
            {
                "numero_solicitud": "SOL-2024-002",
                "cliente_nombre": "María González López",
                "cliente_email": "maria.gonzalez@email.com",
                "monto_solicitado": 75000.00,
                "tipo_credito": "personal",
                "fecha_solicitud": "2024-01-15T14:20:00Z",
                "observaciones": "Primera solicitud de la cliente"
            },
            {
                "numero_solicitud": "SOL-2024-003",
                "cliente_nombre": "Carlos Rodríguez Martín",
                "cliente_email": "carlos.rodriguez@email.com",
                "monto_solicitado": 180000.00,
                "tipo_credito": "vehicular",
                "fecha_solicitud": "2024-01-16T09:15:00Z",
                "observaciones": "Compra de vehículo comercial para empresa"
            }
        ]
        
        registros_creados = []
        for solicitud in solicitudes_ejemplo:
            registro = await microservicio.procesar_nueva_solicitud(
                bandeja_id=bandeja["id"],
                estatus_recibida_id=estatus_recibida["id"],
                datos_solicitud=solicitud
            )
            registros_creados.append(registro)
        
        # Buscar solicitudes
        logger.info("🔍 Probando búsquedas...")
        solicitudes_juan = await microservicio.buscar_solicitudes_cliente(
            bandeja_id=bandeja["id"],
            nombre_cliente="Juan"
        )
        
        solicitudes_maria = await microservicio.buscar_solicitudes_cliente(
            bandeja_id=bandeja["id"],
            nombre_cliente="María"
        )
        
        # Actualizar estatus de una solicitud
        if registros_creados:
            logger.info("🔄 Actualizando estatus...")
            estatus_revision = next(
                (e for e in estatus_list if e["codigo"] == "EN_REVISION"),
                None
            )
            
            if estatus_revision:
                await microservicio.actualizar_estatus_solicitud(
                    registro_id=registros_creados[0]["id"],
                    nuevo_estatus_id=estatus_revision["id"],
                    observaciones="Iniciada revisión de documentos"
                )
        
        # Mostrar resultados
        logger.info("📊 Resumen de operaciones:")
        logger.info(f"  - Bandeja creada: {bandeja['nombre']}")
        logger.info(f"  - Estatus configurados: {len(estatus_list)}")
        logger.info(f"  - Solicitudes procesadas: {len(registros_creados)}")
        logger.info(f"  - Búsqueda 'Juan': {len(solicitudes_juan)} resultados")
        logger.info(f"  - Búsqueda 'María': {len(solicitudes_maria)} resultados")
        
    except Exception as e:
        logger.error(f"❌ Error en integración: {e}")
        raise
    
    finally:
        # Cerrar conexión
        await microservicio.cerrar()
        logger.info("👋 Conexión cerrada")


async def ejemplo_uso_simple():
    """Ejemplo de uso simple del SDK"""
    
    # Uso con context manager (recomendado)
    async with AtlantisClient("http://localhost:8000") as client:
        
        # Verificar conexión
        if await client.test_connection():
            logger.info("✅ Conectado a Atlantis")
        else:
            logger.error("❌ No se pudo conectar")
            return
        
        # Listar bandejas existentes
        bandejas = await client.bandejas.listar()
        logger.info(f"📁 Bandejas disponibles: {len(bandejas)}")
        
        # Listar estatus disponibles
        estatus = await client.estatus.listar()
        logger.info(f"📊 Estatus disponibles: {len(estatus)}")
        
        # Si hay bandejas, mostrar registros de la primera
        if bandejas:
            primera_bandeja = bandejas[0]
            registros = await client.registros.listar(
                bandeja_id=primera_bandeja["id"],
                page=1,
                page_size=10
            )
            logger.info(f"📄 Registros en '{primera_bandeja['nombre']}': {registros['total']}")


if __name__ == "__main__":
    # Ejecutar ejemplo completo
    print("🚀 Ejecutando ejemplo completo de integración con Atlantis SDK")
    asyncio.run(ejemplo_integracion_completa())
    
    print("\n" + "="*60 + "\n")
    
    # Ejecutar ejemplo simple
    print("🔧 Ejecutando ejemplo simple")
    asyncio.run(ejemplo_uso_simple())
