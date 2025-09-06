import io
import os
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from typing import Tuple, Optional
import requests
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from PyPDF2 import PdfReader, PdfWriter
from google.cloud import storage
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def _get_gcs_client():
    """
    Devuelve un cliente de GCS intentando lo siguiente en orden:
      1. Archivo indicado en GOOGLE_APPLICATION_CREDENTIALS o GCP_CREDENTIALS_FILE
      2. Archivo 'credentials.json' en el directorio 'pioneer' relativo a este fichero
      3. Fallback a Application Default Credentials (ADC)

    Además: si encuentra un archivo de credenciales y la variable de entorno no está
    establecida, la pone en GOOGLE_APPLICATION_CREDENTIALS para compatibilidad con
    otras librerías que consultan esa variable.
    """
    checked_paths = []
    # 1) Variable de entorno
    creds_path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS') or os.getenv('GCP_CREDENTIALS_FILE')
    try:
        if creds_path:
            candidate = Path(creds_path)
            checked_paths.append(str(candidate))
            if candidate.exists() and os.access(candidate, os.R_OK):
                try:
                    from google.oauth2 import service_account
                except Exception as imp_e:
                    logger.error(f"No se pudo importar google.oauth2.service_account: {imp_e}")
                    raise
                creds = service_account.Credentials.from_service_account_file(str(candidate))
                logger.info(f"Usando credenciales GCP desde: {candidate}")
                # Asegurar variable de entorno para compatibilidad
                if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                    os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(candidate)
                    logger.debug(f"Seteada GOOGLE_APPLICATION_CREDENTIALS={candidate}")
                try:
                    return storage.Client(credentials=creds, project=creds.project_id)
                except Exception:
                    return storage.Client(credentials=creds)
            else:
                logger.warning(f"Archivo de credenciales indicado en variable de entorno no existe o no es legible: {candidate}")
        # 2) Buscar credentials.json relativo al paquete pioneer
        candidate = Path(__file__).resolve().parents[2] / 'credentials.json'
        checked_paths.append(str(candidate))
        if candidate.exists() and os.access(candidate, os.R_OK):
            try:
                from google.oauth2 import service_account
            except Exception as imp_e:
                logger.error(f"No se pudo importar google.oauth2.service_account: {imp_e}")
                raise
            creds = service_account.Credentials.from_service_account_file(str(candidate))
            logger.info(f"Usando credenciales GCP desde: {candidate}")
            # Setear variable de entorno si no existe para compatibilidad con otras librerías
            if not os.getenv('GOOGLE_APPLICATION_CREDENTIALS'):
                os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = str(candidate)
                logger.debug(f"Seteada GOOGLE_APPLICATION_CREDENTIALS={candidate}")
            try:
                return storage.Client(credentials=creds, project=creds.project_id)
            except Exception:
                return storage.Client(credentials=creds)
        else:
            logger.debug(f"No se encontró credentials.json en: {candidate} (checked_paths: {checked_paths})")
    except Exception as e:
        logger.warning(f"Error al cargar credenciales desde archivo: {e} (rutas comprobadas: {checked_paths})")

    # 3) Fallback: intentar ADC (puede lanzar DefaultCredentialsError)
    logger.warning('No se encontraron credenciales GCP locales; se intentará usar ADC (Application Default Credentials). Rutas comprobadas: %s' % checked_paths)
    try:
        return storage.Client()
    except Exception as e:
        logger.error(f"Error al inicializar storage.Client() con ADC: {e}")
        raise


def concatenar_pdf_con_imagen(pdf_uri: str, imagen_uri: str, pagina_insercion: int) -> Tuple[str, str]:
    """
    Concatena un PDF con una imagen después de una página específica.
    
    Args:
        pdf_uri (str): URI del PDF original
        imagen_uri (str): URI de la imagen a insertar
        pagina_insercion (int): Número de página después de la cual insertar la imagen (base 1)
    
    Returns:
        Tuple[str, str]: Nueva URI del PDF y URL firmada válida por un día
    
    Raises:
        Exception: Si hay errores en la descarga, procesamiento o carga del archivo
    """
    
    temp_files = []
    
    try:
        logger.info(f"Iniciando concatenación de PDF. URI: {pdf_uri}, Imagen: {imagen_uri}, Página: {pagina_insercion}")
        
        # Descargar el PDF original
        logger.info("Descargando PDF original...")
        try:
            parsed_pdf = urlparse(pdf_uri)
            if parsed_pdf.scheme == 'gs':
                # Descargar desde Google Cloud Storage
                client = _get_gcs_client()
                bucket = client.bucket(parsed_pdf.netloc)
                blob = bucket.blob(parsed_pdf.path.lstrip('/'))
                pdf_bytes = blob.download_as_bytes()
                logger.info(f"PDF descargado desde GCS. Tamaño: {len(pdf_bytes)} bytes")
            else:
                pdf_response = requests.get(pdf_uri, timeout=30)
                pdf_response.raise_for_status()
                pdf_bytes = pdf_response.content
                logger.info(f"PDF descargado. Tamaño: {len(pdf_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error al descargar PDF: {e}")
            # Normalizar la excepción para que el bloque de manejo superior la capture como RequestException
            raise requests.exceptions.RequestException(e)
        
        # Descargar la imagen
        logger.info("Descargando imagen...")
        try:
            parsed_img = urlparse(imagen_uri)
            if parsed_img.scheme == 'gs':
                client = _get_gcs_client()
                bucket = client.bucket(parsed_img.netloc)
                blob = bucket.blob(parsed_img.path.lstrip('/'))
                imagen_bytes = blob.download_as_bytes()
                logger.info(f"Imagen descargada desde GCS. Tamaño: {len(imagen_bytes)} bytes")
            else:
                imagen_response = requests.get(imagen_uri, timeout=30)
                imagen_response.raise_for_status()
                imagen_bytes = imagen_response.content
                logger.info(f"Imagen descargada. Tamaño: {len(imagen_bytes)} bytes")
        except Exception as e:
            logger.error(f"Error al descargar imagen: {e}")
            raise requests.exceptions.RequestException(e)
        
        # Crear archivos temporales
        with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
            temp_pdf.write(pdf_bytes)
            temp_pdf_path = temp_pdf.name
            temp_files.append(temp_pdf_path)
        logger.info(f"PDF temporal creado: {temp_pdf_path}")
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_imagen:
            temp_imagen.write(imagen_bytes)
            temp_imagen_path = temp_imagen.name
            temp_files.append(temp_imagen_path)
        logger.info(f"Imagen temporal creada: {temp_imagen_path}")
        
        # Convertir imagen a PDF
        logger.info("Convirtiendo imagen a PDF...")
        imagen_pdf_path = _convertir_imagen_a_pdf(temp_imagen_path)
        temp_files.append(imagen_pdf_path)
        logger.info(f"Imagen convertida a PDF: {imagen_pdf_path}")
        
        # Procesar concatenación del PDF
        logger.info("Iniciando concatenación de PDFs...")
        nuevo_pdf_path = _concatenar_pdfs(temp_pdf_path, imagen_pdf_path, pagina_insercion)
        temp_files.append(nuevo_pdf_path)
        logger.info(f"PDFs concatenados: {nuevo_pdf_path}")
        
        # Verificar que el archivo final existe y tiene contenido
        if os.path.exists(nuevo_pdf_path):
            size = os.path.getsize(nuevo_pdf_path)
            logger.info(f"PDF concatenado creado exitosamente. Tamaño: {size} bytes")
        else:
            raise Exception("El archivo PDF concatenado no fue creado")
        
        # Subir el nuevo PDF a Google Cloud Storage
        logger.info("Subiendo PDF concatenado a GCS...")
        nueva_uri, url_firmada = _subir_pdf_a_gcs(nuevo_pdf_path, pdf_uri)
        
        logger.info(f"Concatenación completada exitosamente. Nueva URI: {nueva_uri}")
        return nueva_uri, url_firmada
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error al descargar archivos: {e}")
        raise Exception(f"Error al descargar archivos: {e}")
    
    except Exception as e:
        logger.error(f"Error durante la concatenación: {e}")
        raise Exception(f"Error durante la concatenación de PDF: {e}")
    
    finally:
        # Limpiar archivos temporales
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.debug(f"Archivo temporal eliminado: {temp_file}")
            except Exception as e:
                logger.warning(f"No se pudo eliminar archivo temporal {temp_file}: {e}")


def _convertir_imagen_a_pdf(imagen_path: str) -> str:
    """
    Convierte una imagen a PDF manteniendo las proporciones.
    
    Args:
        imagen_path (str): Ruta del archivo de imagen
    
    Returns:
        str: Ruta del PDF generado
    """
    
    # Crear archivo temporal para el PDF de la imagen
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_pdf:
        pdf_path = temp_pdf.name
    
    logger.info(f"Convirtiendo imagen {imagen_path} a PDF {pdf_path}")
    
    # Abrir y procesar la imagen
    with Image.open(imagen_path) as img:
        logger.info(f"Imagen abierta. Modo: {img.mode}, Tamaño: {img.size}")
        
        # Convertir a RGB si es necesario
        if img.mode != 'RGB':
            img = img.convert('RGB')
            logger.info("Imagen convertida a RGB")
        
        # Obtener dimensiones de la imagen
        img_width, img_height = img.size
        
        # Definir tamaño de página (A4)
        page_width, page_height = A4
        logger.info(f"Tamaño página A4: {page_width}x{page_height}")
        logger.info(f"Tamaño imagen: {img_width}x{img_height}")
        
        # Calcular escalado manteniendo proporciones
        scale_width = page_width / img_width
        scale_height = page_height / img_height
        scale = min(scale_width, scale_height) * 0.9  # 90% para dejar margen
        
        # Nuevas dimensiones
        new_width = img_width * scale
        new_height = img_height * scale
        
        # Centrar imagen en la página
        x_offset = (page_width - new_width) / 2
        y_offset = (page_height - new_height) / 2
        
        logger.info(f"Escalado: {scale:.2f}, Nueva dimensión: {new_width:.2f}x{new_height:.2f}")
        logger.info(f"Posición: x={x_offset:.2f}, y={y_offset:.2f}")
        
        # Crear PDF con la imagen
        c = canvas.Canvas(pdf_path, pagesize=A4)
        
        # Guardar imagen temporalmente para insertarla en el PDF
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as temp_img:
            img.save(temp_img.name, 'JPEG', quality=85)
            logger.info(f"Imagen temporal guardada: {temp_img.name}")
            
            # Insertar imagen en el PDF
            c.drawImage(temp_img.name, x_offset, y_offset, new_width, new_height)
            logger.info("Imagen insertada en el canvas PDF")
            
            # Limpiar imagen temporal
            os.unlink(temp_img.name)
        
        c.save()
        logger.info(f"PDF de imagen guardado: {pdf_path}")
    
    # Verificar que el archivo se creó correctamente
    if os.path.exists(pdf_path):
        size = os.path.getsize(pdf_path)
        logger.info(f"PDF de imagen creado exitosamente. Tamaño: {size} bytes")
    else:
        raise Exception("No se pudo crear el PDF de la imagen")
    
    return pdf_path


def _concatenar_pdfs(pdf_original_path: str, imagen_pdf_path: str, pagina_insercion: int) -> str:
    """
    Concatena el PDF original con la imagen convertida a PDF.
    
    Args:
        pdf_original_path (str): Ruta del PDF original
        imagen_pdf_path (str): Ruta del PDF de la imagen
        pagina_insercion (int): Página después de la cual insertar (base 1)
    
    Returns:
        str: Ruta del PDF concatenado
    """
    
    # Crear archivo temporal para el resultado
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_resultado:
        resultado_path = temp_resultado.name
    
    # Leer PDFs
    with open(pdf_original_path, 'rb') as pdf_file:
        pdf_reader = PdfReader(pdf_file)
        pdf_writer = PdfWriter()
        
        # Validar que la página de inserción sea válida
        total_paginas = len(pdf_reader.pages)
        logger.info(f"PDF original tiene {total_paginas} páginas, insertando después de página {pagina_insercion}")
        
        if pagina_insercion < 0 or pagina_insercion > total_paginas:
            raise ValueError(f"Página de inserción {pagina_insercion} no válida. El PDF tiene {total_paginas} páginas.")
        
        # Copiar páginas hasta la página de inserción
        logger.info(f"Copiando páginas 1 a {pagina_insercion}")
        for i in range(min(pagina_insercion, total_paginas)):
            pdf_writer.add_page(pdf_reader.pages[i])
            logger.debug(f"Copiada página {i+1}")
        
        # Insertar la imagen convertida a PDF
        logger.info("Insertando imagen convertida a PDF")
        with open(imagen_pdf_path, 'rb') as imagen_pdf_file:
            imagen_reader = PdfReader(imagen_pdf_file)
            paginas_imagen = len(imagen_reader.pages)
            logger.info(f"La imagen PDF tiene {paginas_imagen} páginas")
            for idx, page in enumerate(imagen_reader.pages):
                pdf_writer.add_page(page)
                logger.debug(f"Insertada página de imagen {idx+1}")
        
        # Copiar las páginas restantes del PDF original
        paginas_restantes = total_paginas - pagina_insercion
        logger.info(f"Copiando {paginas_restantes} páginas restantes (desde página {pagina_insercion+1})")
        for i in range(pagina_insercion, total_paginas):
            pdf_writer.add_page(pdf_reader.pages[i])
            logger.debug(f"Copiada página restante {i+1}")
        
        # Escribir el resultado
        total_paginas_final = len(pdf_writer.pages)
        logger.info(f"PDF final tendrá {total_paginas_final} páginas")
        with open(resultado_path, 'wb') as output_file:
            pdf_writer.write(output_file)
    
    return resultado_path


def _subir_pdf_a_gcs(pdf_path: str, pdf_uri_original: str) -> Tuple[str, str]:
    """
    Sube el PDF concatenado a Google Cloud Storage y genera URL firmada.
    
    Args:
        pdf_path (str): Ruta del PDF a subir
        pdf_uri_original (str): URI original para extraer bucket y generar nuevo nombre
    
    Returns:
        Tuple[str, str]: Nueva URI y URL firmada
    """
    
    try:
        # Parsear la URI original para obtener bucket y nombre base
        parsed_uri = urlparse(pdf_uri_original)
        
        if parsed_uri.scheme == 'gs':
            # Formato: gs://bucket/path/file.pdf
            bucket_name = parsed_uri.netloc
            path_original = parsed_uri.path.lstrip('/')
        else:
            # Asumir formato de URL de GCS
            # https://storage.googleapis.com/bucket/path/file.pdf
            parts = parsed_uri.path.strip('/').split('/', 1)
            bucket_name = parts[0]
            path_original = parts[1] if len(parts) > 1 else ''
        
        # Generar nuevo nombre con timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        nombre_base = Path(path_original).stem
        extension = Path(path_original).suffix
        directorio = str(Path(path_original).parent) if Path(path_original).parent.name != '.' else ''
        
        nuevo_nombre = f"{nombre_base}_concatenado_{timestamp}{extension}"
        if directorio and directorio != '.':
            nueva_ruta = f"{directorio}/{nuevo_nombre}"
        else:
            nueva_ruta = nuevo_nombre
        
        # Inicializar cliente de GCS
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)
        
        # Subir archivo
        blob = bucket.blob(nueva_ruta)
        with open(pdf_path, 'rb') as pdf_file:
            blob.upload_from_file(pdf_file, content_type='application/pdf')
        
        # Generar URI y URL firmada
        nueva_uri = f"gs://{bucket_name}/{nueva_ruta}"
        
        # URL firmada válida por 24 horas
        url_firmada = blob.generate_signed_url(
            expiration=datetime.utcnow() + timedelta(days=1),
            method='GET'
        )
        
        logger.info(f"PDF subido exitosamente a GCS: {nueva_uri}")
        return nueva_uri, url_firmada
        
    except Exception as e:
        logger.error(f"Error al subir PDF a GCS: {e}")
        raise Exception(f"Error al subir PDF a Google Cloud Storage: {e}")


def validar_parametros(pdf_uri: str, imagen_uri: str, pagina_insercion: int) -> None:
    """
    Valida los parámetros de entrada.
    
    Args:
        pdf_uri (str): URI del PDF
        imagen_uri (str): URI de la imagen
        pagina_insercion (int): Página de inserción
    
    Raises:
        ValueError: Si algún parámetro no es válido
    """
    
    if not pdf_uri or not isinstance(pdf_uri, str):
        raise ValueError("PDF URI es requerido y debe ser una cadena válida")
    
    if not imagen_uri or not isinstance(imagen_uri, str):
        raise ValueError("Imagen URI es requerido y debe ser una cadena válida")
    
    if not isinstance(pagina_insercion, int) or pagina_insercion < 0:
        raise ValueError("Página de inserción debe ser un entero no negativo")
    
    # Validar que las URIs tengan formato válido
    try:
        urlparse(pdf_uri)
        urlparse(imagen_uri)
    except Exception:
        raise ValueError("Las URIs proporcionadas no tienen formato válido")