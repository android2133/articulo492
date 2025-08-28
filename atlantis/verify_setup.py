#!/usr/bin/env python3
"""
Script de pruebas básicas simplificado para el microservicio Atlantis
"""
import os
import sys
from pathlib import Path


def verificar_estructura_archivos():
    """Verificar que todos los archivos necesarios existen"""
    print("🔍 Verificando estructura de archivos...")
    
    archivos_requeridos = [
        "app/__init__.py",
        "app/main.py",
        "app/database.py",
        "app/models.py",
        "app/schemas.py",
        "app/utils.py",
        "app/validators.py",
        "app/routers/bandejas.py",
        "app/routers/campos.py",
        "app/routers/estatus.py",
        "app/routers/registros.py",
        "app/routers/movimientos.py",
        "core/__init__.py",
        "core/config.py",
        "core/logging_config.py",
        "core/middleware.py",
        "config.properties",
        ".env",
        "requirements.txt",
        "Dockerfile",
        "docker-compose.yml"
    ]
    
    archivos_faltantes = []
    for archivo in archivos_requeridos:
        if not Path(archivo).exists():
            archivos_faltantes.append(archivo)
    
    if archivos_faltantes:
        print("❌ Archivos faltantes:")
        for archivo in archivos_faltantes:
            print(f"   - {archivo}")
        return False
    
    print("✅ Todos los archivos necesarios están presentes")
    return True


def verificar_configuracion():
    """Verificar que el archivo de configuración es válido"""
    print("🔍 Verificando configuración...")
    
    try:
        import configparser
        config = configparser.ConfigParser()
        config.read('config.properties')
        
        # Verificar secciones requeridas
        secciones_requeridas = ['auth', 'database', 'secret_key', 'app', 'encryption']
        for seccion in secciones_requeridas:
            if seccion not in config:
                print(f"❌ Falta la sección [{seccion}] en config.properties")
                return False
        
        print("✅ Configuración válida")
        return True
        
    except Exception as e:
        print(f"❌ Error leyendo configuración: {e}")
        return False


def verificar_dependencias():
    """Verificar que las dependencias están instaladas"""
    print("🔍 Verificando dependencias...")
    
    dependencias_criticas = [
        "fastapi",
        "uvicorn",
        "pydantic",
        "sqlalchemy",
        "asyncpg"
    ]
    
    dependencias_faltantes = []
    for dep in dependencias_criticas:
        try:
            __import__(dep)
        except ImportError:
            dependencias_faltantes.append(dep)
    
    if dependencias_faltantes:
        print("❌ Dependencias faltantes:")
        for dep in dependencias_faltantes:
            print(f"   - {dep}")
        print("\n💡 Ejecuta: pip install -r requirements.txt")
        return False
    
    print("✅ Todas las dependencias críticas están instaladas")
    return True


def verificar_sintaxis_python():
    """Verificar que los archivos Python tienen sintaxis válida"""
    print("🔍 Verificando sintaxis de archivos Python...")
    
    archivos_python = [
        "app/main.py",
        "app/database.py", 
        "app/models.py",
        "app/schemas.py",
        "core/config.py"
    ]
    
    errores_sintaxis = []
    for archivo in archivos_python:
        if Path(archivo).exists():
            try:
                with open(archivo, 'r', encoding='utf-8') as f:
                    compile(f.read(), archivo, 'exec')
            except SyntaxError as e:
                errores_sintaxis.append(f"{archivo}: {e}")
    
    if errores_sintaxis:
        print("❌ Errores de sintaxis encontrados:")
        for error in errores_sintaxis:
            print(f"   - {error}")
        return False
    
    print("✅ Sintaxis de archivos Python correcta")
    return True


def mostrar_instrucciones():
    """Mostrar instrucciones para el siguiente paso"""
    print("\n" + "="*60)
    print("🎉 CONFIGURACIÓN BÁSICA COMPLETADA")
    print("="*60)
    print("\n📋 Próximos pasos:")
    print("   1. Configura tu base de datos PostgreSQL")
    print("   2. Ajusta la URL de BD en config.properties o .env")
    print("   3. Ejecuta el servidor:")
    print("      source venv/bin/activate")
    print("      uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    print("\n📚 Documentación disponible en:")
    print("   http://localhost:8000/docs")
    print("   http://localhost:8000/redoc")
    print("\n🔍 Health checks:")
    print("   http://localhost:8000/health")
    print("   http://localhost:8000/healthz")
    print("\n💾 Para usar con Docker:")
    print("   docker-compose up -d")
    print("\n" + "="*60)


def main():
    """Función principal"""
    print("🏛️ ATLANTIS - Verificación de Configuración")
    print("=" * 50)
    
    pruebas = [
        verificar_estructura_archivos,
        verificar_configuracion,
        verificar_dependencias,
        verificar_sintaxis_python
    ]
    
    todas_exitosas = True
    for prueba in pruebas:
        if not prueba():
            todas_exitosas = False
            print()
    
    print("\n" + "="*50)
    if todas_exitosas:
        print("✅ TODAS LAS VERIFICACIONES PASARON")
        mostrar_instrucciones()
        return 0
    else:
        print("❌ ALGUNAS VERIFICACIONES FALLARON")
        print("🔧 Revisa los errores anteriores y corrígelos")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
