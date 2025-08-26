#!/usr/bin/env python3
"""
Script para probar la corrección de orientación mejorada
"""
import requests
import base64
import json
import sys
import subprocess

def create_rotated_test_pdf():
    """Crea un PDF de prueba con contenido rotado usando reportlab"""
    try:
        from reportlab.pdfgen import canvas
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.utils import ImageReader
        from PIL import Image, ImageDraw, ImageFont
        import io
        
        # Crear imagen con texto rotado
        img = Image.new('RGB', (400, 300), 'white')
        draw = ImageDraw.Draw(img)
        
        # Texto que debería estar rotado 90 grados
        text = "DOCUMENTO ROTADO 90 GRADOS\nEste texto está mal orientado\n12345 67890\nFactura: $1,234.56"
        
        try:
            # Intentar usar fuente del sistema
            font = ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", 24)
        except:
            font = ImageFont.load_default()
        
        # Escribir texto normal primero
        draw.text((20, 50), text, fill='black', font=font)
        
        # Rotar la imagen 90 grados (simular documento mal escaneado)
        rotated_img = img.rotate(90, expand=True)
        
        # Crear PDF con imagen rotada
        test_pdf = "/tmp/test_rotated_document.pdf"
        c = canvas.Canvas(test_pdf, pagesize=letter)
        
        # Convertir PIL a formato que reportlab pueda usar
        img_buffer = io.BytesIO()
        rotated_img.save(img_buffer, format='PNG')
        img_buffer.seek(0)
        
        c.drawImage(ImageReader(img_buffer), 50, 400, width=300, height=400)
        c.save()
        
        # Convertir a base64
        with open(test_pdf, "rb") as f:
            pdf_content = f.read()
            pdf_b64 = base64.b64encode(pdf_content).decode()
        
        print(f"✅ PDF de prueba creado con contenido rotado: {test_pdf}")
        return pdf_b64, "test_rotated_document.pdf"
        
    except ImportError:
        print("⚠️  reportlab/PIL no disponible para crear PDF de prueba")
        # Usar PDF base64 simple como fallback
        return "JVBERi0xLjMKJcTl8uXrp/Og0MTGCjQgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAzIDAgUgo+PgplbmRvYmoKCjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFs0IDAgUl0KL0NvdW50IDEKL01lZGlhQm94IFswIDAgNjEyIDc5Ml0KPj4KZW5kb2JqCgoxIDAgb2JqCjw8Ci9UeXBlIC9DYXRhbG9nCi9QYWdlcyAzIDAgUgo+PgplbmRvYmoKCnhyZWYKMCA0CjAwMDAwMDAwMDAgNjU1MzUgZiAKMDAwMDAwMDE0OSAwMDAwMCBuIAowMDAwMDAwMDk0IDAwMDAwIG4gCjAwMDAwMDAxNzMgMDAwMDAgbiAKdHJhaWxlcgo8PAovU2l6ZSA0Ci9Sb290IDEgMCBSCj4+CnN0YXJ0eHJlZgo3OTYKJSVFT0Y=", "simple_test.pdf"
    except Exception as e:
        print(f"❌ Error creando PDF de prueba: {e}")
        return None, None

def test_rotation_detection():
    """Prueba la detección y corrección de rotación"""
    
    url = "http://localhost:8000/convert"
    
    # Crear PDF de prueba con contenido rotado
    print("📝 Creando PDF de prueba con contenido rotado...")
    pdf_b64, filename = create_rotated_test_pdf()
    
    if not pdf_b64:
        print("❌ No se pudo crear PDF de prueba")
        return
    
    # Prueba 1: Con corrección de orientación habilitada
    print("\n🔄 Prueba 1: Con corrección de orientación HABILITADA")
    payload1 = {
        "filename": filename,
        "content_base64": pdf_b64,
        "disable_rotation_correction": False
    }
    
    try:
        print("   Enviando documento con contenido rotado...")
        response1 = requests.post(url, json=payload1, timeout=60)
        if response1.status_code == 200:
            result1 = response1.text
            print("✅ Respuesta exitosa")
            
            # Analizar resultado
            if "rotation_applied=" in result1:
                rotation_lines = [line for line in result1.split('\n') if 'rotation_applied=' in line]
                for line in rotation_lines:
                    if 'rotation_applied=0' in line:
                        print("   ⚠️  No se aplicó rotación - podría ser problema")
                    else:
                        print(f"   ✅ Se aplicó rotación: {line.strip()}")
            
            # Verificar si se extrajo contenido
            content_lines = [line for line in result1.split('\n') if line.strip() and not line.startswith('<!--')]
            readable_content = ' '.join(content_lines).lower()
            
            if any(word in readable_content for word in ['documento', 'rotado', 'factura', '1234']):
                print("   ✅ Se extrajo contenido legible del documento")
            else:
                print("   ❌ No se detectó contenido esperado - posible fallo de OCR/rotación")
                print(f"   📝 Contenido extraído (primeros 200 chars): {readable_content[:200]}...")
            
        else:
            print(f"❌ Error HTTP: {response1.status_code}")
            print(f"   Detalle: {response1.text}")
    except Exception as e:
        print(f"❌ Error en prueba 1: {e}")
    
    # Prueba 2: Con corrección deshabilitada (para comparar)
    print("\n🚫 Prueba 2: Con corrección de orientación DESHABILITADA")
    payload2 = {
        "filename": f"no_rotation_{filename}",
        "content_base64": pdf_b64,
        "disable_rotation_correction": True
    }
    
    try:
        response2 = requests.post(url, json=payload2, timeout=60)
        if response2.status_code == 200:
            result2 = response2.text
            print("✅ Respuesta exitosa")
            
            # Verificar que no se aplicó rotación
            if "rotation_applied=0" in result2:
                print("   ✅ Rotación correctamente deshabilitada")
            else:
                print("   ⚠️  Se aplicó rotación cuando debería estar deshabilitada")
            
            # Comparar contenido extraído
            content_lines2 = [line for line in result2.split('\n') if line.strip() and not line.startswith('<!--')]
            readable_content2 = ' '.join(content_lines2).lower()
            
            if len(readable_content2) < 50:
                print("   ✅ Poco contenido extraído sin rotación (esperado)")
            else:
                print("   ⚠️  Se extrajo mucho contenido sin rotación - revisar documento")
            
        else:
            print(f"❌ Error HTTP: {response2.status_code}")
    except Exception as e:
        print(f"❌ Error en prueba 2: {e}")

def test_service_status():
    """Verifica que el servicio esté funcionando"""
    try:
        response = requests.get("http://localhost:8000/docs", timeout=5)
        if response.status_code == 200:
            return True
        else:
            print(f"⚠️  Servicio responde con código: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"❌ Servicio no está disponible: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Probando detección y corrección de orientación mejorada")
    print("=" * 60)
    
    if not test_service_status():
        print("\n💡 Para iniciar el servicio:")
        print("   docker run -p 8000:8000 challenger-ocr-improved")
        print("   O: uvicorn main:app --host 0.0.0.0 --port 8000")
        sys.exit(1)
    
    print("✅ Servicio está ejecutándose\n")
    
    test_rotation_detection()
    
    print("\n� Análisis de mejoras:")
    print("   ✅ Detección OSD más flexible (umbral 1.0 vs 2.0)")
    print("   ✅ Validación OCR comparativa antes/después")
    print("   ✅ Detección alternativa por patrones de texto")
    print("   ✅ Prueba de rotación en 4 ángulos (0°, 90°, 180°, 270°)")
    print("   ✅ Scoring inteligente (palabras × 2 + caracteres)")
    print("\n🎯 El sistema ahora debería:")
    print("   • Detectar páginas que SÍ necesitan rotación")
    print("   • NO rotar páginas que ya están correctas")
    print("   • Aplicar la rotación correcta matemáticamente")
    print("   • Proporcionar logs detallados para debugging")
