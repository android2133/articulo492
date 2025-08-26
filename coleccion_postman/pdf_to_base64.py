#!/usr/bin/env python3
"""
Script para convertir archivos PDF a base64 para usar en las pruebas de Postman.
"""

import base64
import sys
import os
from pathlib import Path

def pdf_to_base64(pdf_path):
    """Convierte un archivo PDF a string base64."""
    try:
        with open(pdf_path, "rb") as pdf_file:
            base64_string = base64.b64encode(pdf_file.read()).decode('utf-8')
            return base64_string
    except FileNotFoundError:
        print(f"❌ Error: No se encontró el archivo {pdf_path}")
        return None
    except Exception as e:
        print(f"❌ Error procesando archivo: {e}")
        return None

def save_base64_to_file(base64_string, output_path):
    """Guarda el string base64 en un archivo."""
    try:
        with open(output_path, "w") as output_file:
            output_file.write(base64_string)
        return True
    except Exception as e:
        print(f"❌ Error guardando archivo: {e}")
        return False

def main():
    if len(sys.argv) < 2:
        print("🔧 Convertidor de PDF a Base64 para Postman")
        print("=" * 50)
        print("Uso: python3 pdf_to_base64.py <archivo.pdf> [archivo_salida.txt]")
        print()
        print("Ejemplos:")
        print("  python3 pdf_to_base64.py documento.pdf")
        print("  python3 pdf_to_base64.py documento.pdf base64_output.txt")
        print()
        print("Si no especificas archivo de salida, se imprime en pantalla.")
        return
    
    pdf_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    # Verificar que el archivo existe
    if not os.path.exists(pdf_path):
        print(f"❌ Error: El archivo {pdf_path} no existe")
        return
    
    # Verificar que es un PDF
    if not pdf_path.lower().endswith('.pdf'):
        print(f"⚠️  Advertencia: {pdf_path} no parece ser un archivo PDF")
        response = input("¿Continuar de todas formas? (y/N): ")
        if response.lower() != 'y':
            return
    
    print(f"🔄 Convirtiendo {pdf_path} a base64...")
    
    # Obtener tamaño del archivo
    file_size = os.path.getsize(pdf_path)
    file_size_mb = file_size / (1024 * 1024)
    
    print(f"📄 Tamaño del archivo: {file_size_mb:.2f} MB")
    
    if file_size_mb > 10:
        print("⚠️  Archivo grande (>10MB). Esto podría tardar...")
        response = input("¿Continuar? (y/N): ")
        if response.lower() != 'y':
            return
    
    # Convertir a base64
    base64_string = pdf_to_base64(pdf_path)
    
    if base64_string is None:
        return
    
    base64_size_mb = len(base64_string) / (1024 * 1024)
    print(f"✅ Conversión exitosa!")
    print(f"📊 Tamaño en base64: {base64_size_mb:.2f} MB")
    print(f"📊 Longitud del string: {len(base64_string):,} caracteres")
    
    if output_path:
        # Guardar en archivo
        if save_base64_to_file(base64_string, output_path):
            print(f"💾 Base64 guardado en: {output_path}")
            print()
            print("🚀 Para usar en Postman:")
            print(f"   1. Abre el archivo {output_path}")
            print("   2. Copia todo el contenido")
            print("   3. Pégalo en la variable 'pdf_base64' de tu Environment")
        else:
            print("❌ Error guardando archivo")
    else:
        # Imprimir en pantalla (truncado si es muy largo)
        print()
        print("📋 Base64 generado:")
        print("-" * 50)
        
        if len(base64_string) > 1000:
            print(f"{base64_string[:500]}...")
            print(f"... [truncado - {len(base64_string) - 1000:,} caracteres más] ...")
            print(f"...{base64_string[-500:]}")
            print()
            print("💡 Tip: Usa un archivo de salida para el string completo:")
            print(f"   python3 pdf_to_base64.py {pdf_path} output.txt")
        else:
            print(base64_string)
        
        print("-" * 50)
    
    print()
    print("🎯 Pasos siguientes:")
    print("   1. Importa la colección Postman: Async_Workflow_Execution.postman_collection.json")
    print("   2. Configura Environment con pdf_base64")
    print("   3. Ejecuta 'Listar Workflows' para obtener workflow_id")
    print("   4. Ejecuta 'Ejecutar Workflow Asíncrono'")
    print("   5. Monitorea con 'Consultar Estado Completo'")

if __name__ == "__main__":
    main()
