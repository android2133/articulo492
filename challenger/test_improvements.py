#!/usr/bin/env python3
"""
Script de prueba para verificar las mejoras en OCR de números
"""
import requests
import base64
import json
from pathlib import Path

def test_service():
    """Prueba básica del servicio mejorado"""
    
    # URL del servicio (asumiendo que está corriendo en el puerto 8000)
    url = "http://localhost:8000/convert"
    
    # Crear un PDF de prueba simple con números (requiere reportlab)
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        
        # Crear PDF de prueba con números
        test_pdf = "/tmp/test_numbers.pdf"
        c = canvas.Canvas(test_pdf, pagesize=letter)
        c.drawString(100, 750, "Factura #12345")
        c.drawString(100, 720, "Subtotal: $1,234.56")
        c.drawString(100, 690, "IVA (16%): $197.53")
        c.drawString(100, 660, "Total: $1,432.09")
        c.drawString(100, 630, "Cuenta: 1234-5678-9012-3456")
        c.drawString(100, 600, "Fecha: 06/08/2025")
        c.save()
        
        # Leer y codificar en base64
        with open(test_pdf, "rb") as f:
            pdf_bytes = f.read()
            pdf_b64 = base64.b64encode(pdf_bytes).decode()
        
        # Preparar request
        payload = {
            "filename": "test_numbers.pdf",
            "content_base64": pdf_b64
        }
        
        print("Enviando PDF de prueba con números al servicio...")
        response = requests.post(url, json=payload, timeout=60)
        
        if response.status_code == 200:
            result = response.text
            print("✅ Servicio respondió correctamente")
            print("\n--- Resultado del OCR mejorado ---")
            print(result[:1000] + ("..." if len(result) > 1000 else ""))
            
            # Análisis básico del resultado
            if "confidence=" in result:
                print("✅ Se incluyó información de confianza")
            if "método=ocr" in result or "method=ocr" in result:
                print("✅ Se usó OCR como esperado")
            if "spa+eng" in result or any(num in result for num in ["12345", "1,234.56", "197.53"]):
                print("✅ Se detectaron números correctamente")
                
        else:
            print(f"❌ Error del servicio: {response.status_code}")
            print(response.text)
            
    except ImportError:
        print("⚠️  reportlab no disponible, creando test manual")
        print("Para prueba completa, instala: pip install reportlab")
        print("O envía un PDF manualmente al endpoint /convert")
    except Exception as e:
        print(f"❌ Error en prueba: {e}")

def test_multipart():
    """Prueba con multipart/form-data"""
    url = "http://localhost:8000/convert"
    
    # Buscar algún PDF existente en el sistema
    test_files = [
        "/tmp/test.pdf",
        "/home/jose/Desktop/sample.pdf",
        "/usr/share/doc/*/examples/*.pdf"
    ]
    
    print("🔍 Buscando PDFs de prueba...")
    for pattern in test_files:
        if "*" in pattern:
            from glob import glob
            files = glob(pattern)
            if files:
                test_file = files[0]
                break
        elif Path(pattern).exists():
            test_file = pattern
            break
    else:
        print("⚠️  No se encontró PDF de prueba")
        print("Crea un PDF en /tmp/test.pdf para probar multipart")
        return
    
    try:
        with open(test_file, "rb") as f:
            files = {"file": (Path(test_file).name, f, "application/pdf")}
            print(f"📎 Enviando {test_file} como multipart...")
            response = requests.post(url, files=files, timeout=60)
            
        if response.status_code == 200:
            print("✅ Multipart funcionó correctamente")
            result = response.text
            if "confidence=" in result:
                print("✅ Confianza incluida")
        else:
            print(f"❌ Error multipart: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Error en test multipart: {e}")

if __name__ == "__main__":
    print("🧪 Probando mejoras de OCR para números")
    print("=" * 50)
    
    # Verificar que el servicio esté corriendo
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            print("✅ Servicio está corriendo en puerto 8000")
        else:
            print("⚠️  Servicio responde pero con código", response.status_code)
    except requests.exceptions.RequestException:
        print("❌ Servicio no está corriendo")
        print("   Ejecuta: docker-compose up o uvicorn main:app --host 0.0.0.0 --port 8000")
        exit(1)
    
    print("\n1. Probando con JSON/base64...")
    test_service()
    
    print("\n2. Probando con multipart...")
    test_multipart()
    
    print("\n🎉 Pruebas completadas")
