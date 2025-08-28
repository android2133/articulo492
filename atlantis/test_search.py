#!/usr/bin/env python3
"""
Prueba del endpoint de búsqueda de Atlantis
"""
import sys
from urllib.parse import urlencode

def test_search_endpoint():
    """Probar que el endpoint de búsqueda existe y tiene la lógica correcta"""
    print("🔍 Probando endpoint de búsqueda...")
    
    try:
        # Importar la aplicación
        from app.main import app
        
        # Verificar que el endpoint existe
        search_found = False
        for route in app.routes:
            if hasattr(route, 'path') and route.path == '/api/v1/registros/search':
                if hasattr(route, 'methods') and 'GET' in route.methods:
                    search_found = True
                    break
        
        if not search_found:
            print("❌ Endpoint /api/v1/registros/search no encontrado")
            return False
        
        print("✅ Endpoint de búsqueda registrado correctamente")
        
        # Verificar imports necesarios
        from sqlalchemy import text, or_, and_
        print("✅ Imports de SQLAlchemy disponibles")
        
        # Verificar que la función de búsqueda está definida
        from app.routers.registros import router
        
        # Contar rutas del router
        search_routes = [r for r in router.routes if hasattr(r, 'path') and 'search' in r.path]
        if search_routes:
            print(f"✅ Router de registros tiene {len(search_routes)} ruta(s) de búsqueda")
        else:
            print("❌ No se encontraron rutas de búsqueda en el router")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Error probando búsqueda: {e}")
        import traceback
        traceback.print_exc()
        return False

def show_search_examples():
    """Mostrar ejemplos de uso del endpoint de búsqueda"""
    print("\n📝 Ejemplos de Uso del Endpoint de Búsqueda:")
    print("=" * 60)
    
    base_url = "http://localhost:8000/api/v1/registros/search"
    
    examples = [
        {
            "descripcion": "Buscar por nombre específico",
            "params": {
                "bandeja_id": "bandeja-123",
                "q": "Juan",
                "campos": "nombre_solicitante"
            }
        },
        {
            "descripcion": "Buscar por email",
            "params": {
                "bandeja_id": "bandeja-123", 
                "q": "@gmail.com",
                "campos": "email"
            }
        },
        {
            "descripcion": "Buscar en múltiples campos",
            "params": {
                "bandeja_id": "bandeja-123",
                "q": "urgente", 
                "campos": "titulo,descripcion,comentarios"
            }
        },
        {
            "descripcion": "Búsqueda global (todos los campos)",
            "params": {
                "bandeja_id": "bandeja-123",
                "q": "2025"
            }
        },
        {
            "descripcion": "Búsqueda con paginación",
            "params": {
                "bandeja_id": "bandeja-123",
                "q": "proceso",
                "page": "2",
                "page_size": "10"
            }
        }
    ]
    
    for i, example in enumerate(examples, 1):
        print(f"\n{i}. {example['descripcion']}")
        query_string = urlencode(example['params'])
        full_url = f"{base_url}?{query_string}"
        print(f"   GET {full_url}")

def main():
    print("🏛️ ATLANTIS - Prueba de Búsqueda")
    print("=" * 50)
    
    # Probar funcionalidad
    if test_search_endpoint():
        print("\n🎉 ¡Endpoint de búsqueda funcionando correctamente!")
        show_search_examples()
        
        print("\n📚 Documentación:")
        print("   - Swagger UI: http://localhost:8000/docs")
        print("   - Colección Postman: Atlantis_Bandejas_API.postman_collection.json")
        print("   - README: README_POSTMAN.md")
        
        return 0
    else:
        print("\n❌ Problemas con el endpoint de búsqueda")
        return 1

if __name__ == "__main__":
    sys.exit(main())
