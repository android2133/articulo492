#!/usr/bin/env python3
"""
Prueba simplificada de configuración de Atlantis - Solo configuración
"""
import sys
import os

def test_config_loading():
    """Probar que la configuración se carga correctamente"""
    print("🔧 Probando carga de configuración...")
    
    try:
        # Importar la configuración
        from core.config import (
            database_settings, 
            auth_settings, 
            app_settings, 
            encryption_settings
        )
        
        print(f"✅ Database URL: {database_settings.postgres_url}")
        print(f"✅ API Title: {app_settings.api_title}")
        print(f"✅ API Version: {app_settings.api_version}")
        print(f"✅ Environment: {app_settings.ambiente}")
        print(f"✅ Auth Type: {auth_settings.auth_type}")
        print(f"✅ CORS Origins: {app_settings.cors_origins_list}")
        
        return True
    except Exception as e:
        print(f"❌ Error cargando configuración: {e}")
        return False

def test_app_creation():
    """Probar que la app FastAPI se puede crear"""
    print("\n🚀 Probando creación de la aplicación FastAPI...")
    
    try:
        from app.main import app
        
        print(f"✅ App creada: {type(app)}")
        print(f"✅ App title: {app.title}")
        print(f"✅ App version: {app.version}")
        print(f"✅ Routes count: {len(app.routes)}")
        
        # Mostrar algunas rutas
        print("📋 Rutas principales:")
        for route in app.routes[:5]:  # Primeras 5 rutas
            if hasattr(route, 'path'):
                print(f"   - {route.path}")
        
        return True
    except Exception as e:
        print(f"❌ Error creando app: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_schemas():
    """Probar que los schemas se pueden importar"""
    print("\n📝 Probando schemas...")
    
    try:
        from app import schemas
        
        # Verificar que las clases principales existen
        classes = ['BandejaCreate', 'BandejaRead', 'RegistroCreate', 'RegistroRead']
        for cls_name in classes:
            if hasattr(schemas, cls_name):
                print(f"✅ Schema {cls_name} disponible")
            else:
                print(f"❌ Schema {cls_name} no encontrado")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Error importando schemas: {e}")
        return False

def main():
    print("🏛️ ATLANTIS - Prueba de Configuración")
    print("=" * 50)
    
    tests = [
        test_config_loading,
        test_app_creation,
        test_schemas
    ]
    
    passed = 0
    for test in tests:
        if test():
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Resultado: {passed}/{len(tests)} pruebas exitosas")
    
    if passed == len(tests):
        print("🎉 ¡Todas las pruebas pasaron!")
        print("🏛️ El microservicio Atlantis está correctamente configurado")
        print("💡 Para usar con base de datos, ejecuta Docker Compose")
        return 0
    else:
        print("❌ Algunas pruebas fallaron")
        return 1

if __name__ == "__main__":
    sys.exit(main())
