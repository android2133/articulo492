"""
Tests para el SDK de Atlantis

Ejecutar con:
    pytest test_sdk.py -v
    
O para tests específicos:
    pytest test_sdk.py::test_bandejas -v
"""

import pytest
import asyncio
import os
import sys

# Agregar el directorio actual al path para importar el cliente
sys.path.append(os.path.dirname(__file__))

from client import (
    AtlantisClient,
    AtlantisConfig,
    AtlantisException,
    AtlantisAPIError,
    AtlantisConnectionError
)

# Configuración para tests
ATLANTIS_URL = os.getenv("ATLANTIS_TEST_URL", "http://localhost:8000")
ATLANTIS_TOKEN = os.getenv("ATLANTIS_TEST_TOKEN", None)


@pytest.fixture
async def client():
    """Fixture que proporciona un cliente configurado"""
    config = AtlantisConfig(
        base_url=ATLANTIS_URL,
        auth_token=ATLANTIS_TOKEN,
        timeout=10.0,
        max_retries=2
    )
    
    async with AtlantisClient(config=config) as client:
        # Verificar que Atlantis esté disponible
        if not await client.test_connection():
            pytest.skip(f"Atlantis no disponible en {ATLANTIS_URL}")
        
        yield client


@pytest.fixture
async def bandeja_test(client):
    """Fixture que crea una bandeja de prueba"""
    bandeja = await client.bandejas.crear(
        nombre="Test Bandeja SDK",
        descripcion="Bandeja creada para testing del SDK",
        grupo="test_sdk"
    )
    
    yield bandeja
    
    # Cleanup
    try:
        await client.bandejas.eliminar(bandeja["id"])
    except:
        pass  # Si ya fue eliminada, no importa


@pytest.fixture
async def estatus_test(client):
    """Fixture que crea un estatus de prueba"""
    estatus = await client.estatus.crear(
        codigo="TEST_SDK",
        nombre="Test SDK",
        descripcion="Estatus para testing del SDK",
        color="#ff6b6b"
    )
    
    yield estatus
    
    # Cleanup
    try:
        await client.estatus.eliminar(estatus["id"])
    except:
        pass


class TestConnection:
    """Tests de conexión y configuración"""
    
    @pytest.mark.asyncio
    async def test_connection_success(self, client):
        """Test conexión exitosa"""
        connected = await client.test_connection()
        assert connected is True
    
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        """Test health check"""
        health = await client.health.check()
        assert isinstance(health, dict)
    
    @pytest.mark.asyncio
    async def test_health_check_k8s(self, client):
        """Test health check Kubernetes"""
        health = await client.health.check_k8s()
        assert isinstance(health, dict)
    
    @pytest.mark.asyncio
    async def test_connection_failure(self):
        """Test manejo de conexión fallida"""
        client = AtlantisClient("http://localhost:99999")  # Puerto inexistente
        
        try:
            await client.start_session()
            connected = await client.test_connection()
            assert connected is False
        finally:
            await client.close_session()


class TestBandejas:
    """Tests para gestión de bandejas"""
    
    @pytest.mark.asyncio
    async def test_crear_bandeja(self, client):
        """Test crear bandeja"""
        bandeja = await client.bandejas.crear(
            nombre="Test Crear Bandeja",
            descripcion="Descripción de prueba",
            grupo="test_crear"
        )
        
        assert bandeja["nombre"] == "Test Crear Bandeja"
        assert bandeja["descripcion"] == "Descripción de prueba"
        assert bandeja["grupo"] == "test_crear"
        assert "id" in bandeja
        
        # Cleanup
        await client.bandejas.eliminar(bandeja["id"])
    
    @pytest.mark.asyncio
    async def test_listar_bandejas(self, client):
        """Test listar bandejas"""
        bandejas = await client.bandejas.listar()
        assert isinstance(bandejas, list)
    
    @pytest.mark.asyncio
    async def test_obtener_bandeja(self, client, bandeja_test):
        """Test obtener bandeja específica"""
        bandeja = await client.bandejas.obtener(bandeja_test["id"])
        
        assert bandeja["id"] == bandeja_test["id"]
        assert bandeja["nombre"] == bandeja_test["nombre"]
    
    @pytest.mark.asyncio
    async def test_actualizar_bandeja(self, client, bandeja_test):
        """Test actualizar bandeja"""
        nueva_descripcion = "Descripción actualizada"
        
        bandeja_actualizada = await client.bandejas.actualizar(
            bandeja_test["id"],
            descripcion=nueva_descripcion
        )
        
        assert bandeja_actualizada["descripcion"] == nueva_descripcion
    
    @pytest.mark.asyncio
    async def test_eliminar_bandeja(self, client):
        """Test eliminar bandeja"""
        # Crear bandeja temporal
        bandeja = await client.bandejas.crear(
            nombre="Test Eliminar",
            descripcion="Para eliminar"
        )
        
        # Eliminar
        resultado = await client.bandejas.eliminar(bandeja["id"])
        assert isinstance(resultado, dict)
        
        # Verificar que ya no existe
        with pytest.raises(AtlantisAPIError):
            await client.bandejas.obtener(bandeja["id"])


class TestCampos:
    """Tests para gestión de campos"""
    
    @pytest.mark.asyncio
    async def test_crear_campo_string(self, client, bandeja_test):
        """Test crear campo tipo string"""
        campo = await client.campos.crear(
            bandeja_id=bandeja_test["id"],
            nombre="test_campo",
            etiqueta="Campo de Prueba",
            tipo="string",
            requerido=True
        )
        
        assert campo["nombre"] == "test_campo"
        assert campo["etiqueta"] == "Campo de Prueba"
        assert campo["tipo"] == "string"
        assert campo["requerido"] is True
    
    @pytest.mark.asyncio
    async def test_crear_campo_enum(self, client, bandeja_test):
        """Test crear campo tipo enum"""
        opciones = ["opcion1", "opcion2", "opcion3"]
        
        campo = await client.campos.crear(
            bandeja_id=bandeja_test["id"],
            nombre="test_enum",
            etiqueta="Campo Enum",
            tipo="enum",
            opciones_enum=opciones
        )
        
        assert campo["tipo"] == "enum"
        assert campo["opciones_enum"] == opciones
    
    @pytest.mark.asyncio
    async def test_listar_campos(self, client, bandeja_test):
        """Test listar campos de bandeja"""
        # Crear un campo
        await client.campos.crear(
            bandeja_id=bandeja_test["id"],
            nombre="campo_lista",
            etiqueta="Campo Lista",
            tipo="string"
        )
        
        campos = await client.campos.listar(bandeja_test["id"])
        assert isinstance(campos, list)
        assert len(campos) >= 1
    
    @pytest.mark.asyncio
    async def test_schema_tabla(self, client, bandeja_test):
        """Test obtener schema de tabla"""
        schema = await client.campos.obtener_schema_tabla(bandeja_test["id"])
        assert isinstance(schema, dict)


class TestEstatus:
    """Tests para gestión de estatus"""
    
    @pytest.mark.asyncio
    async def test_crear_estatus(self, client):
        """Test crear estatus"""
        estatus = await client.estatus.crear(
            codigo="TEST_CREAR",
            nombre="Test Crear",
            descripcion="Estatus de prueba",
            color="#00ff00"
        )
        
        assert estatus["codigo"] == "TEST_CREAR"
        assert estatus["nombre"] == "Test Crear"
        assert estatus["color"] == "#00ff00"
        
        # Cleanup
        await client.estatus.eliminar(estatus["id"])
    
    @pytest.mark.asyncio
    async def test_listar_estatus(self, client):
        """Test listar estatus"""
        estatus_lista = await client.estatus.listar()
        assert isinstance(estatus_lista, list)
    
    @pytest.mark.asyncio
    async def test_actualizar_estatus(self, client, estatus_test):
        """Test actualizar estatus"""
        nuevo_nombre = "Test SDK Actualizado"
        
        estatus_actualizado = await client.estatus.actualizar(
            estatus_test["id"],
            nombre=nuevo_nombre
        )
        
        assert estatus_actualizado["nombre"] == nuevo_nombre


class TestRegistros:
    """Tests para gestión de registros"""
    
    @pytest.fixture
    async def bandeja_con_campos(self, client):
        """Fixture que crea bandeja con campos configurados"""
        # Crear bandeja
        bandeja = await client.bandejas.crear(
            nombre="Test Registros",
            descripcion="Bandeja para tests de registros"
        )
        
        # Crear campos
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="nombre",
            etiqueta="Nombre",
            tipo="string",
            requerido=True
        )
        
        await client.campos.crear(
            bandeja_id=bandeja["id"],
            nombre="email",
            etiqueta="Email",
            tipo="email",
            requerido=True
        )
        
        yield bandeja
        
        # Cleanup
        try:
            await client.bandejas.eliminar(bandeja["id"])
        except:
            pass
    
    @pytest.mark.asyncio
    async def test_crear_registro(self, client, bandeja_con_campos, estatus_test):
        """Test crear registro"""
        datos = {
            "nombre": "Juan Test",
            "email": "juan.test@example.com"
        }
        
        registro = await client.registros.crear(
            bandeja_id=bandeja_con_campos["id"],
            estatus_id=estatus_test["id"],
            datos=datos
        )
        
        assert registro["bandeja_id"] == bandeja_con_campos["id"]
        assert registro["estatus_id"] == estatus_test["id"]
        assert registro["datos"]["nombre"] == "Juan Test"
    
    @pytest.mark.asyncio
    async def test_listar_registros(self, client, bandeja_con_campos):
        """Test listar registros con paginación"""
        resultado = await client.registros.listar(
            bandeja_id=bandeja_con_campos["id"],
            page=1,
            page_size=10
        )
        
        assert "total" in resultado
        assert "items" in resultado
        assert "page" in resultado
        assert "page_size" in resultado
        assert isinstance(resultado["items"], list)
    
    @pytest.mark.asyncio
    async def test_buscar_registros(self, client, bandeja_con_campos, estatus_test):
        """Test búsqueda de registros"""
        # Crear registro para buscar
        await client.registros.crear(
            bandeja_id=bandeja_con_campos["id"],
            estatus_id=estatus_test["id"],
            datos={
                "nombre": "María Búsqueda Test",
                "email": "maria.busqueda@example.com"
            }
        )
        
        # Buscar
        resultado = await client.registros.buscar(
            bandeja_id=bandeja_con_campos["id"],
            query="María",
            campos=["nombre"]
        )
        
        assert "total" in resultado
        assert "items" in resultado
        assert isinstance(resultado["items"], list)
    
    @pytest.mark.asyncio
    async def test_actualizar_registro(self, client, bandeja_con_campos, estatus_test):
        """Test actualizar registro"""
        # Crear registro
        registro = await client.registros.crear(
            bandeja_id=bandeja_con_campos["id"],
            estatus_id=estatus_test["id"],
            datos={
                "nombre": "Test Actualizar",
                "email": "test.actualizar@example.com"
            }
        )
        
        # Actualizar
        nuevos_datos = {"nombre": "Test Actualizado"}
        registro_actualizado = await client.registros.actualizar(
            registro["id"],
            datos=nuevos_datos
        )
        
        assert registro_actualizado["datos"]["nombre"] == "Test Actualizado"


class TestErrorHandling:
    """Tests para manejo de errores"""
    
    @pytest.mark.asyncio
    async def test_api_error_404(self, client):
        """Test manejo de error 404"""
        with pytest.raises(AtlantisAPIError) as exc_info:
            await client.bandejas.obtener("id-inexistente")
        
        assert exc_info.value.status_code == 404
    
    @pytest.mark.asyncio
    async def test_validation_error(self, client):
        """Test manejo de error de validación"""
        with pytest.raises(AtlantisAPIError) as exc_info:
            # Intentar crear bandeja sin nombre requerido
            await client.bandejas.crear(nombre="")  # Nombre vacío
        
        # El error específico depende de la validación del servidor
        assert exc_info.value.status_code >= 400


class TestIntegration:
    """Tests de integración completa"""
    
    @pytest.mark.asyncio
    async def test_workflow_completo(self, client):
        """Test de workflow completo: bandeja -> campos -> estatus -> registros"""
        try:
            # 1. Crear bandeja
            bandeja = await client.bandejas.crear(
                nombre="Workflow Test",
                descripcion="Test workflow completo"
            )
            
            # 2. Crear campos
            campo_nombre = await client.campos.crear(
                bandeja_id=bandeja["id"],
                nombre="nombre",
                etiqueta="Nombre",
                tipo="string",
                requerido=True
            )
            
            campo_prioridad = await client.campos.crear(
                bandeja_id=bandeja["id"],
                nombre="prioridad",
                etiqueta="Prioridad",
                tipo="enum",
                opciones_enum=["alta", "media", "baja"]
            )
            
            # 3. Crear estatus
            estatus_nuevo = await client.estatus.crear(
                codigo="NUEVO_WF",
                nombre="Nuevo Workflow",
                color="#3498db"
            )
            
            estatus_procesando = await client.estatus.crear(
                codigo="PROC_WF",
                nombre="Procesando Workflow",
                color="#f39c12"
            )
            
            # 4. Crear registros
            registro1 = await client.registros.crear(
                bandeja_id=bandeja["id"],
                estatus_id=estatus_nuevo["id"],
                datos={
                    "nombre": "Proceso 1",
                    "prioridad": "alta"
                }
            )
            
            registro2 = await client.registros.crear(
                bandeja_id=bandeja["id"],
                estatus_id=estatus_nuevo["id"],
                datos={
                    "nombre": "Proceso 2",
                    "prioridad": "media"
                }
            )
            
            # 5. Actualizar estatus de un registro
            await client.registros.actualizar(
                registro1["id"],
                estatus_id=estatus_procesando["id"]
            )
            
            # 6. Buscar registros
            resultados = await client.registros.buscar(
                bandeja_id=bandeja["id"],
                query="Proceso",
                campos=["nombre"]
            )
            
            # Verificaciones
            assert bandeja["nombre"] == "Workflow Test"
            assert campo_nombre["nombre"] == "nombre"
            assert campo_prioridad["opciones_enum"] == ["alta", "media", "baja"]
            assert estatus_nuevo["codigo"] == "NUEVO_WF"
            assert registro1["datos"]["prioridad"] == "alta"
            assert resultados["total"] >= 2
            
            print("✅ Workflow completo ejecutado exitosamente")
            
        finally:
            # Cleanup (orden importante: registros -> campos -> bandeja -> estatus)
            try:
                await client.bandejas.eliminar(bandeja["id"])
                await client.estatus.eliminar(estatus_nuevo["id"])
                await client.estatus.eliminar(estatus_procesando["id"])
            except:
                pass


if __name__ == "__main__":
    # Ejecutar tests específicos
    pytest.main([__file__, "-v", "--tb=short"])
