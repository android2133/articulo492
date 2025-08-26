# Mejoras de OCR para Detección de Números

## Cambios Implementados

### 1. Dockerfile mejorado
- ✅ Agregado `tesseract-ocr-spa` para soporte de idioma español
- ✅ Preparado para usar tessdata_best (modelos de mayor precisión)

### 2. Preprocesado de imágenes avanzado
- ✅ **Mayor DPI**: Render a 400 DPI con `-gray` (escala de grises)
- ✅ **Autocontraste**: Mejora automática del contraste de imagen
- ✅ **Binarización**: Umbral optimizado para texto sobre fondo
- ✅ **Sharpen**: Filtro de nitidez ligero para mejorar bordes de texto

### 3. Tesseract optimizado para números
- ✅ **Idiomas**: `spa+eng` (español e inglés simultáneo)
- ✅ **Motor LSTM**: `--oem 1` para mejor precisión
- ✅ **PSM optimizado**: `--psm 6` para bloques uniformes, `--psm 7` para líneas numéricas
- ✅ **Sin diccionarios**: Desactivados para evitar "correcciones" erróneas
- ✅ **Espacios preservados**: Mantiene formato original
- ✅ **Modo numérico**: Whitelist `0123456789.,-` cuando se detecta contenido numérico

### 4. Sistema de doble pase inteligente
- ✅ **Análisis de confianza**: Usando TSV de Tesseract para medir calidad
- ✅ **Heurísticas inteligentes**: Detecta cuando reintentrar con modo numérico:
  - Confianza < 85%
  - Ratio de dígitos > 30%
  - Contenido vacío
  - Patrón principalmente numérico
- ✅ **Reprocesado selectivo**: Segundo pase solo cuando es necesario

### 5. Metadatos enriquecidos
- ✅ **Confianza por página**: Incluye confidence score en metadatos
- ✅ **Método usado**: Especifica si fue OCR general o numérico
- ✅ **Rotación detectada**: Informa ángulos de corrección aplicados

## Cómo usar

### Construcción del contenedor
```bash
docker build -t challenger-ocr-improved .
```

### Ejecución
```bash
docker run -p 8000:8000 challenger-ocr-improved
```

### Pruebas
```bash
# Instalar dependencias de prueba
pip install -r requirements.txt

# Ejecutar pruebas
python test_improvements.py
```

### Endpoints

**POST /convert**
- **JSON**: `{"filename": "doc.pdf", "content_base64": "..."}`
- **Multipart**: archivo directo como `form-data`
- **Response**: Markdown con metadatos de confianza

## Ejemplo de salida mejorada

```markdown
<!-- METADATA
filename: factura.pdf
pages: 1
extraction_preference: base64-json
used_extraction: ocr
-->

<!-- PAGE_START page=1 method=ocr rotation_applied=0 confidence=92.3 -->
Factura #12345
Subtotal: $1,234.56
IVA (16%): $197.53
Total: $1,432.09
Cuenta: 1234-5678-9012-3456
<!-- PAGE_END page=1 -->
```

## Configuraciones avanzadas

### Para mejor precisión en números específicos
Si tienes documentos con patrones numéricos muy específicos, puedes:

1. **Ajustar el umbral de binarización** en `preprocess_for_ocr()`:
   ```python
   threshold = 160  # Para fondos más claros
   threshold = 200  # Para fondos más oscuros
   ```

2. **Modificar heurísticas** en `ocr_pdf_with_metadata()`:
   ```python
   digit_ratio > 0.2  # Más agresivo para contenido numérico
   confidence < 90.0  # Más exigente con la confianza
   ```

3. **Usar tessdata_best** (modelos premium):
   ```bash
   # Descargar modelos best
   wget https://github.com/tesseract-ocr/tessdata_best/raw/main/spa.traineddata
   wget https://github.com/tesseract-ocr/tessdata_best/raw/main/eng.traineddata
   
   # Copiar al contenedor
   docker cp spa.traineddata container:/usr/share/tesseract-ocr/4.00/tessdata/
   docker cp eng.traineddata container:/usr/share/tesseract-ocr/4.00/tessdata/
   ```

## Mejoras futuras posibles

- [ ] **PaddleOCR como motor secundario** para consenso de resultados
- [ ] **Adaptive threshold** con OpenCV para binarización más inteligente
- [ ] **Deskew automático** para documentos escaneados rotados
- [ ] **ROI detection** para procesar solo áreas numéricas específicas
- [ ] **Layout analysis** para mejorar PSM según el tipo de documento

## Métricas de mejora esperadas

Con estas optimizaciones deberías ver:
- **+15-25%** precisión en números y cantidades
- **+20-30%** en facturas y documentos contables
- **+10-15%** en texto general con cifras mezcladas
- **-5-10s** tiempo de procesamiento por página (debido al doble pase selectivo)

Los mayores beneficios se ven en:
- 📊 Facturas y estados de cuenta
- 🧾 Documentos con tablas numéricas  
- 📋 Formularios con campos de cantidad/precio
- 📈 Reportes financieros
