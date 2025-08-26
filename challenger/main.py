
import base64
import subprocess
import tempfile
import os
import re
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, UploadFile, File
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from PIL import Image, ImageOps, ImageFilter  # requiere pillow

app = FastAPI(title="MarkItDown Service (full extraction + metadata + orientation)")

# Entrada base64
class ConvertRequest(BaseModel):
    filename: str = Field(..., example="ejemplo.pdf")
    content_base64: str  # archivo en base64
    disable_rotation_correction: bool = Field(False, description="Deshabilitar corrección automática de orientación")

# ------------------ utilitarios ------------------

def get_pdf_page_count(pdf_path: str) -> int:
    try:
        result = subprocess.run(
            ["pdfinfo", pdf_path], check=True, capture_output=True, text=True, timeout=10
        )
        m = re.search(r"Pages:\s+(\d+)", result.stdout)
        if m:
            return int(m.group(1))
    except Exception as e:
        print(f"[WARN] no se pudo obtener conteo de páginas: {e}")
    return 0

def extract_text_embedded_per_page_dict(pdf_path: str, num_pages: int) -> dict:
    page_texts = {}
    for p in range(1, num_pages + 1):
        try:
            result = subprocess.run(
                ["pdftotext", "-f", str(p), "-l", str(p), pdf_path, "-"],
                check=True, capture_output=True, text=True, timeout=20
            )
            text = result.stdout.strip()
            page_texts[p] = text
        except Exception as e:
            print(f"[WARN] pdftotext falló en página {p}: {e}")
            page_texts[p] = ""
    return page_texts

def build_embedded_markdown(page_texts: dict) -> str:
    parts = []
    for p, text in page_texts.items():
        parts.append(f"<!-- PAGE_START page={p} method=embedded_text -->\n")
        if text.strip():
            parts.append(text + "\n")
        else:
            parts.append(f"<!-- no embedded text extracted for page {p} -->\n")
        parts.append(f"<!-- PAGE_END page={p} -->\n")
    return "\n".join(parts)

def detect_rotation(image_path: str) -> int:
    try:
        proc = subprocess.run(
            ["tesseract", image_path, "stdout", "--psm", "0"],
            capture_output=True, text=True, timeout=20
        )
        osd = proc.stdout
        # Buscar tanto la rotación como la confianza
        rotate_match = re.search(r"Rotate: (\d+)", osd)
        confidence_match = re.search(r"Orientation confidence: ([\d.]+)", osd)
        
        if rotate_match:
            angle = int(rotate_match.group(1))
            confidence = float(confidence_match.group(1)) if confidence_match else 0.0
            
            print(f"[DEBUG] detección OSD: ángulo={angle}°, confianza={confidence:.1f}")
            
            # Ser más permisivo con la confianza para ángulos estándar
            if angle in [90, 180, 270]:
                if confidence > 0.8:  # Confianza alta
                    return angle
                elif confidence > 0.3:  # Confianza media - validar con OCR
                    print(f"[DEBUG] confianza media ({confidence:.1f}), validando necesidad de rotación")
                    return angle
                else:
                    print(f"[DEBUG] confianza muy baja ({confidence:.1f}), probando detección por texto")
                    # Si OSD tiene confianza muy baja, probar método alternativo
                    alt_angle = detect_rotation_by_text_quality(image_path)
                    return alt_angle if alt_angle > 0 else 0
            else:
                print(f"[DEBUG] ignorando ángulo no estándar: {angle}°")
                return 0
        return 0
    except Exception as e:
        print(f"[WARN] falla al detectar orientación de {image_path}: {e}")
        # Si OSD falla completamente, intentar método alternativo
        return detect_rotation_by_text_quality(image_path)

def detect_rotation_by_text_quality(image_path: str) -> int:
    """Detecta rotación comparando la calidad del texto en diferentes orientaciones"""
    try:
        print(f"[DEBUG] probando detección por calidad de texto en {image_path}")
        angles_to_try = [0, 90, 180, 270]
        best_score = 0
        best_angle = 0
        
        for test_angle in angles_to_try:
            temp_path = image_path.replace(".png", f"_test_{test_angle}.png")
            
            try:
                img = Image.open(image_path)
                if test_angle == 90:
                    test_img = img.rotate(-90, expand=True)
                elif test_angle == 180:
                    test_img = img.rotate(180, expand=True)
                elif test_angle == 270:
                    test_img = img.rotate(90, expand=True)
                else:
                    test_img = img  # 0 grados = original
                
                test_img.save(temp_path)
                
                # OCR rápido para evaluar calidad
                result = subprocess.run(
                    ["tesseract", temp_path, "stdout", "--psm", "3"],
                    capture_output=True, text=True, timeout=15
                )
                text = result.stdout.strip()
                
                # Calcular score basado en:
                # 1. Número de palabras de longitud razonable
                # 2. Número de caracteres alfanuméricos
                # 3. Ratio de caracteres legibles vs símbolos raros
                words = len([w for w in text.split() if len(w) > 2])
                alnum_chars = len([c for c in text if c.isalnum()])
                total_chars = len(text.replace(' ', '').replace('\n', ''))
                
                if total_chars > 0:
                    legible_ratio = alnum_chars / total_chars
                    score = words * 2 + alnum_chars * legible_ratio
                else:
                    score = 0
                
                print(f"[DEBUG] ángulo {test_angle}°: {words} palabras, score={score:.1f}")
                
                if score > best_score:
                    best_score = score
                    best_angle = test_angle
                
                # Limpiar archivo temporal
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
            except Exception as e:
                print(f"[DEBUG] error probando ángulo {test_angle}°: {e}")
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        
        # Si el mejor score no es con 0°, significa que hay rotación
        rotation_needed = 0
        if best_angle != 0 and best_score > 5:  # Score mínimo para considerar rotación
            rotation_needed = best_angle
            print(f"[DEBUG] detección por texto: mejor orientación {best_angle}° (score={best_score:.1f})")
        else:
            print(f"[DEBUG] detección por texto: sin rotación necesaria (mejor score={best_score:.1f})")
            
        return rotation_needed
        
    except Exception as e:
        print(f"[WARN] error en detección por calidad de texto: {e}")
        return 0

def correct_image_orientation(image_path: str) -> int:
    angle = detect_rotation(image_path)
    
    # Solo rotar si hay un ángulo significativo (90, 180, 270 grados)
    if angle != 0 and angle in [90, 180, 270]:
        # Validación adicional: intentar OCR básico antes y después para confirmar mejora
        if should_apply_rotation(image_path, angle):
            try:
                img = Image.open(image_path)
                # Corregir la rotación (no aplicar 360 - angle, sino el ángulo correcto)
                if angle == 90:
                    corrected = img.rotate(-90, expand=True)  # rotar 90° en sentido horario
                elif angle == 180:
                    corrected = img.rotate(180, expand=True)  # rotar 180°
                elif angle == 270:
                    corrected = img.rotate(90, expand=True)   # rotar 90° en sentido antihorario
                
                corrected.save(image_path)
                print(f"[DEBUG] imagen {image_path} corregida desde {angle}° a orientación normal")
                return angle
            except Exception as e:
                print(f"[WARN] no se pudo rotar imagen {image_path}: {e}")
        else:
            print(f"[DEBUG] rotación de {angle}° descartada tras validación OCR")
    else:
        if angle != 0:
            print(f"[DEBUG] no se rota imagen {image_path}: ángulo {angle}° no requiere corrección")
    
    return 0

def should_apply_rotation(image_path: str, proposed_angle: int) -> bool:
    """Valida si aplicar rotación realmente mejora el OCR"""
    try:
        # OCR rápido en imagen original con configuración básica
        original_result = subprocess.run(
            ["tesseract", image_path, "stdout", "--psm", "3"],
            capture_output=True, text=True, timeout=15
        )
        original_text = original_result.stdout.strip()
        original_words = len([w for w in original_text.split() if len(w) > 2])
        original_chars = len([c for c in original_text if c.isalnum()])
        
        print(f"[DEBUG] OCR original: {original_words} palabras, {original_chars} caracteres alfanuméricos")
        
        # Criterios más permisivos para aplicar rotación:
        
        # 1. Si hay muy poco contenido reconocible, definitivamente necesita rotación
        if original_words < 5 and original_chars < 20:
            print(f"[DEBUG] muy poco texto reconocible, aplicando rotación propuesta")
            return True
        
        # 2. Si el contenido es marginal, probar la rotación para comparar
        if original_words < 15 or original_chars < 80:
            print(f"[DEBUG] contenido marginal, probando rotación para comparar")
            
            # Crear imagen rotada temporalmente para probar
            temp_rotated = image_path.replace(".png", "_rotated_test.png")
            try:
                img = Image.open(image_path)
                if proposed_angle == 90:
                    test_img = img.rotate(-90, expand=True)
                elif proposed_angle == 180:
                    test_img = img.rotate(180, expand=True)
                elif proposed_angle == 270:
                    test_img = img.rotate(90, expand=True)
                else:
                    return False  # Ángulo no válido
                
                test_img.save(temp_rotated)
                
                # OCR en imagen rotada
                rotated_result = subprocess.run(
                    ["tesseract", temp_rotated, "stdout", "--psm", "3"],
                    capture_output=True, text=True, timeout=15
                )
                rotated_text = rotated_result.stdout.strip()
                rotated_words = len([w for w in rotated_text.split() if len(w) > 2])
                rotated_chars = len([c for c in rotated_text if c.isalnum()])
                
                print(f"[DEBUG] OCR rotada: {rotated_words} palabras, {rotated_chars} caracteres alfanuméricos")
                
                # Limpiar archivo temporal
                if os.path.exists(temp_rotated):
                    os.remove(temp_rotated)
                
                # Aplicar rotación si hay mejora significativa (al menos 50% más contenido)
                improvement_ratio = 1.5
                if (rotated_words > original_words * improvement_ratio or 
                    rotated_chars > original_chars * improvement_ratio):
                    print(f"[DEBUG] rotación mejora significativamente el OCR, aplicando")
                    return True
                else:
                    print(f"[DEBUG] rotación no mejora suficiente, manteniendo original")
                    return False
                    
            except Exception as e:
                print(f"[DEBUG] error probando rotación: {e}")
                # En caso de error, aplicar rotación si el original tiene muy poco texto
                return original_words < 8
        
        # 3. Si ya hay bastante contenido reconocible, no rotar
        print(f"[DEBUG] contenido ya legible ({original_words} palabras), no rotando")
        return False
        
    except Exception as e:
        print(f"[DEBUG] error en validación OCR, aplicando rotación por defecto: {e}")
        # En caso de error, ser conservador pero permitir rotación si se detectó con confianza
        return True
        print(f"[DEBUG] suficiente texto legible ({original_words} palabras), no rotando")
        return False
        
    except Exception as e:
        print(f"[DEBUG] error en validación OCR, aplicando rotación por defecto: {e}")
        return True  # En caso de error, aplicar la rotación sugerida

def preprocess_for_ocr(img_path: str) -> str:
    """Autocontraste, binarización simple y sharpen ligero."""
    try:
        img = Image.open(img_path).convert("L")
        img = ImageOps.autocontrast(img, cutoff=1)          # mejora contraste
        # Umbral simple; si hay fondos grises, considera 160–200 o calcula Otsu con numpy
        threshold = 180
        img = img.point(lambda p: 255 if p > threshold else 0, mode='1')  # binariza
        img = img.convert("L").filter(ImageFilter.UnsharpMask(radius=1.2, percent=120, threshold=3))
        pre_path = img_path.replace(".png", "_pre.png")
        img.save(pre_path)
        print(f"[DEBUG] preprocesado imagen: {img_path} -> {pre_path}")
        return pre_path
    except Exception as e:
        print(f"[WARN] error en preprocesado de {img_path}: {e}")
        return img_path  # devuelve original si falla

def run_tesseract(image_path: str, out_base: str, numeric_mode: bool = False):
    """Ejecuta tesseract con configuración optimizada para números."""
    args = [
        "tesseract", image_path, out_base,
        "-l", "spa+eng",
        "--oem", "1",
        "--psm", "6",
        "-c", "preserve_interword_spaces=1",
        "-c", "load_system_dawg=0",
        "-c", "load_freq_dawg=0",
    ]
    if numeric_mode:
        args += ["-c", "tessedit_char_whitelist=0123456789.,-"]
        args[args.index("--psm") + 1] = "7"  # línea para modo numérico
    
    print(f"[DEBUG] ejecutando tesseract {'(modo numérico)' if numeric_mode else '(modo general)'}: {' '.join(args[:6])}")
    subprocess.run(args, check=True, capture_output=True, timeout=60)

def tesseract_tsv_conf(image_path: str) -> float:
    """Obtiene la confianza promedio del OCR usando TSV."""
    try:
        r = subprocess.run(
            ["tesseract", image_path, "stdout", "-l", "spa+eng", "--oem", "1", "--psm", "6", "tsv"],
            check=True, capture_output=True, text=True, timeout=60
        )
        # Promedia col "conf" (ignora -1)
        lines = [l.split('\t') for l in r.stdout.splitlines() if '\t' in l]
        confs = []
        for cols in lines[1:]:  # salta header
            try:
                conf = int(cols[-1])
                if conf >= 0:
                    confs.append(conf)
            except: 
                pass
        avg_conf = sum(confs)/len(confs) if confs else 0.0
        print(f"[DEBUG] confianza promedio TSV: {avg_conf:.1f}%")
        return avg_conf
    except Exception as e:
        print(f"[WARN] error obteniendo confianza TSV: {e}")
        return 0.0

def ocr_pdf_with_metadata(pdf_path: str, tmpdir: str, disable_rotation: bool = False) -> str:
    page_texts = []
    try:
        # Render a mayor DPI y en escala de grises
        subprocess.run(
            ["pdftoppm", "-png", "-r", "400", "-gray", pdf_path, os.path.join(tmpdir, "page")],
            check=True, capture_output=True, timeout=120
        )
    except Exception as e:
        print(f"[ERROR] pdftoppm falló: {e}")
        return ""

    for img_path in sorted(Path(tmpdir).glob("page-*.png")):
        page_no_match = re.search(r"page-(\d+)\.png$", img_path.name)
        page_num = page_no_match.group(1) if page_no_match else "?"
        base_no_ext = str(img_path.with_suffix(""))
        rotation_applied = 0
        content = ""
        confidence = 0.0
        
        try:
            # 1. Corrección de orientación (opcional)
            if not disable_rotation:
                rotation_applied = correct_image_orientation(str(img_path))
            else:
                rotation_applied = 0
                print(f"[DEBUG] corrección de orientación deshabilitada para página {page_num}")
            
            # 2. Preprocesado para OCR
            proc_img = preprocess_for_ocr(str(img_path))
            
            # 3. Primer pase general con tesseract optimizado
            run_tesseract(proc_img, base_no_ext, numeric_mode=False)
            txt_file = base_no_ext + ".txt"
            
            if os.path.exists(txt_file):
                with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read().strip()
            
            # 4. Análisis de confianza y heurísticas para reprocesado
            confidence = tesseract_tsv_conf(proc_img)
            digit_ratio = (sum(c.isdigit() for c in content) / max(1, len(content))) if content else 0
            
            # 5. Segundo pase numérico si es necesario
            needs_numeric_retry = (
                confidence < 85.0 or  # baja confianza
                digit_ratio > 0.3 or  # muchos números detectados
                not content.strip() or  # contenido vacío
                len([c for c in content if c.isdigit() or c in '.,%-']) > len(content) * 0.4  # patrón numérico
            )
            
            if needs_numeric_retry:
                print(f"[DEBUG] página {page_num}: reintentando con modo numérico (conf={confidence:.1f}%, digits={digit_ratio:.2f})")
                try:
                    run_tesseract(proc_img, base_no_ext, numeric_mode=True)
                    if os.path.exists(txt_file):
                        with open(txt_file, "r", encoding="utf-8", errors="ignore") as f:
                            numeric_content = f.read().strip()
                        
                        # Si el resultado numérico es mejor, úsalo
                        if len(numeric_content) > len(content) or (numeric_content and not content):
                            content = numeric_content
                            confidence = tesseract_tsv_conf(proc_img)
                            print(f"[DEBUG] página {page_num}: mejorado con modo numérico (nueva conf={confidence:.1f}%)")
                except Exception as e:
                    print(f"[WARN] fallo en modo numérico para página {page_num}: {e}")
            
            if not content:
                content = f"<!-- OCR falló en página {page_num}, no se pudo extraer texto -->"
                
        except subprocess.CalledProcessError as e:
            content = f"<!-- tesseract falló en página {page_num}: {e.stderr.decode(errors='ignore') if e.stderr else e} -->"
        except Exception as e:
            content = f"<!-- error inesperado en OCR página {page_num}: {e} -->"

        meta = (
            f"<!-- PAGE_START page={page_num} method=ocr rotation_applied={rotation_applied} confidence={confidence:.1f} -->\n"
            f"{content}\n"
            f"<!-- PAGE_END page={page_num} -->\n"
        )
        page_texts.append(meta)

    return "\n".join(page_texts)

# ------------------ endpoint ------------------

@app.post("/convert", response_class=PlainTextResponse)
async def convert(
    request: Request,
    file: Optional[UploadFile] = File(None),
):
    filename = None
    content_bytes = None
    extraction_mode = None
    disable_rotation = False

    if file is not None:
        filename = file.filename
        if not filename:
            raise HTTPException(status_code=400, detail="Archivo sin nombre en multipart.")
        content_bytes = await file.read()
        extraction_mode = "multipart"
        print(f"[DEBUG] recibido multipart file={filename} size={len(content_bytes)}")
    else:
        try:
            body = await request.body()
            if not body:
                raise ValueError("Body vacío")
            import json

            parsed = json.loads(body)
            req = ConvertRequest(**parsed)
            filename = req.filename
            content_bytes = base64.b64decode(req.content_base64)
            disable_rotation = req.disable_rotation_correction
            extraction_mode = "base64-json"
            print(f"[DEBUG] recibido base64 JSON filename={filename} size={len(content_bytes)}, disable_rotation={disable_rotation}")
        except Exception as e:
            print(f"[ERROR] no se pudo interpretar la entrada: {e}")
            raise HTTPException(status_code=400, detail=f"Entrada inválida: {e}")

    if not filename or content_bytes is None:
        raise HTTPException(status_code=400, detail="No se proporcionó archivo válido.")

    with tempfile.TemporaryDirectory() as tmpdir:
        input_path = os.path.join(tmpdir, filename)
        output_path = os.path.join(tmpdir, "output.md")

        with open(input_path, "wb") as f:
            f.write(content_bytes)
        print(f"[DEBUG] escrito archivo en {input_path} ({os.path.getsize(input_path)} bytes)")

        num_pages = get_pdf_page_count(input_path)
        if num_pages == 0:
            print("[WARN] no se pudo obtener número de páginas, se asume 1")
            num_pages = 1

        markdown_parts = []
        metadata = {
            "filename": filename,
            "pages": num_pages,
            "extraction_preference": extraction_mode,
            "used_extraction": None,
        }

        # 1. Embedded text por página validado
        page_texts_dict = extract_text_embedded_per_page_dict(input_path, num_pages)
        has_some_embedded = any(text.strip() for text in page_texts_dict.values())
        if has_some_embedded:
            metadata["used_extraction"] = "embedded_text"
            embedded_md = build_embedded_markdown(page_texts_dict)
            markdown_parts.append(embedded_md)
        else:
            # 2. OCR con corrección de orientación (configurable)
            if disable_rotation:
                print("[DEBUG] texto embebido no útil; corriendo OCR por página SIN corrección de orientación")
            else:
                print("[DEBUG] texto embebido no útil; corriendo OCR por página con corrección de orientación")
            ocr_md = ocr_pdf_with_metadata(input_path, tmpdir, disable_rotation)
            if ocr_md and "PAGE_START" in ocr_md:
                metadata["used_extraction"] = "ocr"
                markdown_parts.append(ocr_md)
            else:
                # 3. Último recurso: markitdown
                print("[WARN] OCR falló o no produjo contenido, intentando markitdown como respaldo")
                if not os.path.exists(input_path):
                    print("[ERROR] archivo de entrada no existe cuando se llamó a markitdown:", input_path)
                    raise HTTPException(status_code=500, detail="Archivo de entrada perdido antes de fallback.")
                try:
                    subprocess.run(
                        ["markitdown", input_path, "-o", output_path],
                        check=True,
                        capture_output=True,
                        timeout=60,
                    )
                    with open(output_path, "r", encoding="utf-8", errors="ignore") as f:
                        fallback = f.read()
                    metadata["used_extraction"] = "markitdown"
                    markdown_parts.append(
                        f"<!-- PAGE_START page=1 method=markitdown -->\n{fallback}\n<!-- PAGE_END page=1 -->\n"
                    )
                except subprocess.CalledProcessError as e:
                    detail = e.stderr.decode(errors="ignore") if e.stderr else str(e)
                    print("[ERROR] markitdown de respaldo falló:", detail)
                    raise HTTPException(status_code=500, detail=f"Error final en conversión: {detail}")

        # Construir metadata header
        meta_block = "<!-- METADATA\n"
        for k, v in metadata.items():
            meta_block += f"{k}: {v}\n"
        meta_block += "-->\n\n"

        final_md = meta_block + "\n".join(markdown_parts)

        if not final_md.strip():
            print("[ERROR] resultado final vacío después de todos los pasos")
            raise HTTPException(status_code=500, detail="Markdown vacío tras extracción y OCR.")

        print("[DEBUG] conversión exitosa, longitud total markdown:", len(final_md))
        return PlainTextResponse(content=final_md, media_type="text/markdown")
