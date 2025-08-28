"""
Script de pruebas básicas para el microservicio Atlantis
"""
import asyncio
import sys
import os
from pathlib import Path

# Agregar el directorio padre al path para importar módulos
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configurar variables de entorno para pruebas
os.environ["DATABASE_URL"] = "postgresql+asyncpg://postgres:postgres@localhost:5432/atlantis_test"

try:
    from app.database import engine, Base, SessionLocal
    from app import models
    from core.config import database_settings
    from core.logging_config import log_info
    imports_ok = True
except ImportError as e:
    print(f"❌ Error de importación: {e}")
    imports_ok = False


async def crear_tablas():
    """Crear todas las tablas de la base de datos"""
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        log_info("Tablas creadas exitosamente")
        return True
    except Exception as e:
        log_info("Error creando tablas", error=str(e))
        return False


async def verificar_conexion_bd():
    """Verificar que la conexión a la base de datos funciona"""
    try:
        async with SessionLocal() as session:
            result = await session.execute("SELECT 1")
            if result.scalar() == 1:
                log_info("Conexión a base de datos exitosa")
                return True
    except Exception as e:
        log_info("Error conectando a base de datos", error=str(e))
        return False


async def crear_datos_prueba():
    """Crear datos de prueba"""
    try:
        async with SessionLocal() as session:
            # Crear estatus de prueba
            estatus_activo = models.Estatus(
                codigo="ACTIVO",
                nombre="Activo",
                descripcion="Registro activo",
                color="#28a745"
            )
            session.add(estatus_activo)
            
            estatus_pendiente = models.Estatus(
                codigo="PENDIENTE",
                nombre="Pendiente",
                descripcion="Registro pendiente de revisión",
                color="#ffc107"
            )
            session.add(estatus_pendiente)
            
            # Crear bandeja de prueba
            bandeja_test = models.Bandeja(
                clave="TEST_BANDEJA",
                nombre="Bandeja de Prueba",
                descripcion="Bandeja para pruebas del sistema",
                grupo="TESTING",
                orden=1
            )
            session.add(bandeja_test)
            
            await session.commit()
            await session.refresh(bandeja_test)
            
            # Crear campos de prueba
            campo_nombre = models.BandejaCampo(
                bandeja_id=bandeja_test.id,
                nombre="nombre",
                etiqueta="Nombre",
                tipo="string",
                requerido=True,
                mostrar_en_tabla=True,
                posicion=1
            )
            session.add(campo_nombre)
            
            campo_email = models.BandejaCampo(
                bandeja_id=bandeja_test.id,
                nombre="email",
                etiqueta="Email",
                tipo="email",
                requerido=True,
                mostrar_en_tabla=True,
                posicion=2
            )
            session.add(campo_email)
            
            campo_estado = models.BandejaCampo(
                bandeja_id=bandeja_test.id,
                nombre="estado",
                etiqueta="Estado",
                tipo="enum",
                requerido=False,
                mostrar_en_tabla=True,
                opciones_enum=["nuevo", "en_proceso", "completado"],
                posicion=3
            )
            session.add(campo_estado)
            
            await session.commit()
            
            # Crear registro de prueba
            registro_test = models.Registro(
                bandeja_id=bandeja_test.id,
                estatus_id=estatus_activo.id,
                datos={
                    "nombre": "Juan Pérez",
                    "email": "juan.perez@test.com",
                    "estado": "nuevo"
                },
                creado_por="sistema",
                referencia_externa="TEST-001"
            )
            session.add(registro_test)
            
            await session.commit()
            await session.refresh(registro_test)
            
            # Crear movimiento inicial
            movimiento_inicial = models.Movimiento(
                registro_id=registro_test.id,
                desde_bandeja_id=None,
                hacia_bandeja_id=bandeja_test.id,
                estatus_id=estatus_activo.id,
                motivo="CREACION",
                movido_por="sistema"
            )
            session.add(movimiento_inicial)
            
            await session.commit()
            
            log_info("Datos de prueba creados exitosamente", 
                    bandeja_id=str(bandeja_test.id),
                    registro_id=str(registro_test.id))
            
            return {
                "bandeja_id": str(bandeja_test.id),
                "registro_id": str(registro_test.id),
                "estatus_activo_id": str(estatus_activo.id),
                "estatus_pendiente_id": str(estatus_pendiente.id)
            }
            
    except Exception as e:
        log_info("Error creando datos de prueba", error=str(e))
        return None


async def verificar_datos_prueba(datos_ids):
    """Verificar que los datos de prueba se crearon correctamente"""
    try:
        async with SessionLocal() as session:
            # Verificar bandeja
            bandeja = await session.get(models.Bandeja, datos_ids["bandeja_id"])
            if not bandeja:
                log_info("Error: Bandeja de prueba no encontrada")
                return False
            
            # Verificar campos
            from sqlalchemy import select
            campos_query = await session.execute(
                select(models.BandejaCampo).where(
                    models.BandejaCampo.bandeja_id == bandeja.id
                ).order_by(models.BandejaCampo.posicion)
            )
            campos = campos_query.scalars().all()
            
            if len(campos) != 3:
                log_info("Error: No se encontraron todos los campos", campos_count=len(campos))
                return False
            
            # Verificar registro
            registro = await session.get(models.Registro, datos_ids["registro_id"])
            if not registro:
                log_info("Error: Registro de prueba no encontrado")
                return False
            
            # Verificar movimiento
            movimientos_query = await session.execute(
                select(models.Movimiento).where(
                    models.Movimiento.registro_id == registro.id
                )
            )
            movimientos = movimientos_query.scalars().all()
            
            if len(movimientos) != 1:
                log_info("Error: No se encontró el movimiento inicial", movimientos_count=len(movimientos))
                return False
            
            log_info("Verificación de datos de prueba exitosa",
                    bandeja_clave=bandeja.clave,
                    campos_count=len(campos),
                    movimientos_count=len(movimientos))
            
            return True
            
    except Exception as e:
        log_info("Error verificando datos de prueba", error=str(e))
        return False


async def limpiar_datos_prueba():
    """Limpiar datos de prueba"""
    try:
        async with SessionLocal() as session:
            from sqlalchemy import delete
            
            # Eliminar en orden correcto por las foreign keys
            await session.execute(delete(models.Movimiento))
            await session.execute(delete(models.Registro))
            await session.execute(delete(models.BandejaCampo))
            await session.execute(delete(models.Bandeja))
            await session.execute(delete(models.Estatus))
            
            await session.commit()
            
            log_info("Datos de prueba limpiados exitosamente")
            return True
            
    except Exception as e:
        log_info("Error limpiando datos de prueba", error=str(e))
        return False


async def main():
    """Función principal de pruebas"""
    print("=== Iniciando pruebas del microservicio Atlantis ===")
    
    if not imports_ok:
        print("❌ FALLO: Error en las importaciones")
        return False
    
    # Mostrar configuración
    print(f"Configuración de base de datos: {database_settings.POSTGRES_URL}")
    
    # 1. Verificar conexión a BD
    print("1. Verificando conexión a base de datos...")
    if not await verificar_conexion_bd():
        print("❌ FALLO: No se pudo conectar a la base de datos")
        print("💡 Asegúrate de que PostgreSQL esté ejecutándose")
        return False
    
    # 2. Crear tablas
    print("2. Creando tablas...")
    if not await crear_tablas():
        print("❌ FALLO: No se pudieron crear las tablas")
        return False
    
    # 3. Crear datos de prueba
    print("3. Creando datos de prueba...")
    datos_ids = await crear_datos_prueba()
    if not datos_ids:
        print("❌ FALLO: No se pudieron crear los datos de prueba")
        return False
    
    # 4. Verificar datos de prueba
    print("4. Verificando datos de prueba...")
    if not await verificar_datos_prueba(datos_ids):
        print("❌ FALLO: Los datos de prueba no son correctos")
        return False
    
    # 5. Limpiar datos de prueba
    print("5. Limpiando datos de prueba...")
    if not await limpiar_datos_prueba():
        print("⚠️ ADVERTENCIA: No se pudieron limpiar todos los datos de prueba")
    
    print("=== ✅ Todas las pruebas completadas exitosamente ===")
    return True


if __name__ == "__main__":
    # Ejecutar pruebas
    success = asyncio.run(main())
    
    if success:
        print("\n✅ Todas las pruebas pasaron correctamente")
        print("🚀 El microservicio Atlantis está listo para usar")
        print("\nPara iniciar el servidor:")
        print("  uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
        print("\nDocumentación disponible en:")
        print("  http://localhost:8000/docs")
        sys.exit(0)
    else:
        print("\n❌ Algunas pruebas fallaron")
        print("🔧 Revisa la configuración y los logs para más detalles")
        sys.exit(1)
