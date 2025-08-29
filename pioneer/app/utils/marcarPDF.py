from datetime import datetime
import io
import tempfile
import os
from google.cloud import storage
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.colors import red
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import logging

logger = logging.getLogger(__name__)

class MarcadorPDF:
    def __init__(self, bucket_name: str = "perdidas-totales-pruebas"):
        """
        Inicializa el marcador de PDF con el bucket de GCS.
        
        Args:
            bucket_name: Nombre del bucket de GCS
        """
        self.bucket_name = bucket_name
        self.client = storage.Client()
        self.bucket = self.client.bucket(bucket_name)
    
    def generar_marca_validacion(self) -> str:
        """
        Genera la marca de validación con fecha y hora actual.
        
        Returns:
            str: Texto de la marca de validación
        """
        now = datetime.now()
        fecha_hora = now.strftime("%d %B %Y %I:%M%p")
        marcaValidacion = f"SE VALIDO EN QUIEN ES QUIEN E INTERNET, VALIDO MIRAI {fecha_hora.upper()}"
        return marcaValidacion
    
    def crear_overlay_marca(self, texto_marca: str, page_width: float, page_height: float) -> bytes:
        """
        Crea un PDF overlay con la marca de validación.
        
        Args:
            texto_marca: Texto de la marca a agregar
            page_width: Ancho de la página
            page_height: Alto de la página
            
        Returns:
            bytes: PDF overlay como bytes
        """
        # Crear un buffer en memoria para el overlay
        overlay_buffer = io.BytesIO()
        
        # Crear canvas con el tamaño de la página
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        
        # Configurar el texto
        c.setFillColor(red)
        c.setFont("Helvetica-Bold", 10)
        
        # Posicionar el texto en la parte superior (90% de la altura de la página)
        x_position = 50  # Margen izquierdo
        y_position = page_height - 50  # Parte superior con margen
        
        # Agregar el texto
        c.drawString(x_position, y_position, texto_marca)
        
        # Finalizar el canvas
        c.save()
        
        # Obtener los bytes del overlay
        overlay_buffer.seek(0)
        return overlay_buffer.getvalue()
    
    def crear_overlay_parrafo_derecha(self, texto_parrafo: str, page_width: float, page_height: float, 
                                     font_size: int = 9, color=red, max_width: float = None) -> bytes:
        """
        Crea un PDF overlay con un párrafo de texto en el lado derecho, centrado verticalmente.
        
        Args:
            texto_parrafo: Texto del párrafo a agregar
            page_width: Ancho de la página
            page_height: Alto de la página
            font_size: Tamaño de la fuente (default: 9)
            color: Color del texto (default: red)
            max_width: Ancho máximo del texto en puntos (default: 1/3 del ancho de página)
            
        Returns:
            bytes: PDF overlay como bytes
        """
        # Crear un buffer en memoria para el overlay
        overlay_buffer = io.BytesIO()
        
        # Crear canvas con el tamaño de la página
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        
        # Configurar el texto
        c.setFillColor(color)
        c.setFont("Helvetica", font_size)
        
        # Calcular dimensiones y posición
        if max_width is None:
            max_width = page_width / 3  # Un tercio del ancho de la página
        
        margin_right = 20  # Margen desde el borde derecho
        x_start = page_width - max_width - margin_right
        
        # Dividir el texto en líneas que quepan en el ancho máximo
        lines = self._wrap_text(c, texto_parrafo, max_width, font_size)
        
        # Calcular la altura total del bloque de texto
        line_height = font_size + 2  # Espaciado entre líneas
        total_text_height = len(lines) * line_height
        
        # Centrar verticalmente
        y_start = (page_height + total_text_height) / 2
        
        # Dibujar cada línea
        for i, line in enumerate(lines):
            y_position = y_start - (i * line_height)
            c.drawString(x_start, y_position, line)
        
        # Finalizar el canvas
        c.save()
        
        # Obtener los bytes del overlay
        overlay_buffer.seek(0)
        return overlay_buffer.getvalue()
    
    def _wrap_text(self, canvas, text: str, max_width: float, font_size: int) -> list:
        """
        Divide el texto en líneas que quepan en el ancho máximo especificado.
        
        Args:
            canvas: Canvas de reportlab
            text: Texto a dividir
            max_width: Ancho máximo en puntos
            font_size: Tamaño de la fuente
            
        Returns:
            list: Lista de líneas de texto
        """
        words = text.split()
        lines = []
        current_line = ""
        
        for word in words:
            # Probar agregando la palabra a la línea actual
            test_line = current_line + " " + word if current_line else word
            
            # Medir el ancho del texto
            text_width = canvas.stringWidth(test_line, "Helvetica", font_size)
            
            if text_width <= max_width:
                current_line = test_line
            else:
                # Si la línea actual no está vacía, agregarla y empezar nueva línea
                if current_line:
                    lines.append(current_line)
                    current_line = word
                else:
                    # Si una sola palabra es muy larga, agregarla de todos modos
                    lines.append(word)
                    current_line = ""
        
        # Agregar la última línea si no está vacía
        if current_line:
            lines.append(current_line)
        
        return lines
    
    def marcar_pdf_con_validacion(self, gcs_uri: str, destino_folder: str = None) -> dict:
        """
        Marca un PDF con la validación en la primera página y lo sube de vuelta a GCS.
        
        Args:
            gcs_uri: URI del PDF en GCS (gs://bucket/path/file.pdf)
            destino_folder: Carpeta de destino (opcional)
            
        Returns:
            dict: Resultado con la URI del PDF marcado y metadata
        """
        try:
            # Generar la marca de validación
            marca_validacion = self.generar_marca_validacion()
            logger.info(f"Marca generada: {marca_validacion}")
            
            # Extraer información del GCS URI
            if not gcs_uri.startswith("gs://"):
                raise ValueError(f"URI inválida: {gcs_uri}")
            
            # Parsear la URI: gs://bucket/path/file.pdf
            uri_parts = gcs_uri.replace("gs://", "").split("/", 1)
            source_bucket_name = uri_parts[0]
            source_blob_path = uri_parts[1]
            
            # Cliente para el bucket fuente (puede ser diferente al de destino)
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_path)
            
            # Verificar que el archivo existe
            if not source_blob.exists():
                raise FileNotFoundError(f"El archivo no existe en GCS: {gcs_uri}")
            
            # Descargar el PDF a memoria
            logger.info(f"Descargando PDF desde: {gcs_uri}")
            pdf_content = source_blob.download_as_bytes()
            
            # Leer el PDF
            input_pdf = PdfReader(io.BytesIO(pdf_content))
            output_pdf = PdfWriter()
            
            # Procesar cada página
            for page_num, page in enumerate(input_pdf.pages):
                if page_num == 0:  # Solo marcar la primera página
                    # Obtener dimensiones de la página
                    page_box = page.mediabox
                    page_width = float(page_box.width)
                    page_height = float(page_box.height)
                    
                    # Crear overlay con la marca
                    overlay_bytes = self.crear_overlay_marca(marca_validacion, page_width, page_height)
                    
                    # Leer el overlay
                    overlay_pdf = PdfReader(io.BytesIO(overlay_bytes))
                    overlay_page = overlay_pdf.pages[0]
                    
                    # Combinar la página original con el overlay
                    page.merge_page(overlay_page)
                
                # Agregar la página al PDF de salida
                output_pdf.add_page(page)
            
            # Guardar el PDF modificado en memoria
            output_buffer = io.BytesIO()
            output_pdf.write(output_buffer)
            output_buffer.seek(0)
            
            # Generar nombre para el archivo marcado
            base_name = os.path.splitext(os.path.basename(source_blob_path))[0]
            extension = os.path.splitext(source_blob_path)[1]
            
            # Construir la ruta de destino
            if destino_folder:
                destino_path = f"{destino_folder}/{base_name}_marcado{extension}"
            else:
                # Si no se especifica carpeta, usar la misma carpeta que el original
                source_folder = os.path.dirname(source_blob_path)
                destino_path = f"{source_folder}/{base_name}_marcado{extension}" if source_folder else f"{base_name}_marcado{extension}"
            
            # Subir el PDF marcado al bucket de destino
            destino_blob = self.bucket.blob(destino_path)
            
            logger.info(f"Subiendo PDF marcado a: gs://{self.bucket_name}/{destino_path}")
            
            # Subir con metadata
            destino_blob.upload_from_file(
                output_buffer,
                content_type='application/pdf',
                rewind=True
            )
            
            # Establecer metadata personalizada
            destino_blob.metadata = {
                'marca_validacion': marca_validacion,
                'archivo_original': gcs_uri,
                'fecha_marcado': datetime.now().isoformat(),
                'procesado_por': 'pioneer_marcar_pdf'
            }
            destino_blob.patch()
            
            # Construir URI de destino
            destino_uri = f"gs://{self.bucket_name}/{destino_path}"
            
            logger.info(f"PDF marcado exitosamente: {destino_uri}")
            
            return {
                "success": True,
                "uri_original": gcs_uri,
                "uri_marcado": destino_uri,
                "marca_aplicada": marca_validacion,
                "fecha_procesamiento": datetime.now().isoformat(),
                "metadata": {
                    "pages_processed": len(input_pdf.pages),
                    "pages_marked": 1,
                    "file_size_bytes": len(output_buffer.getvalue())
                }
            }
            
        except Exception as e:
            logger.error(f"Error marcando PDF: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "uri_original": gcs_uri if 'gcs_uri' in locals() else None
            }
    
    def marcar_pdf_local(self, input_path: str, output_path: str) -> dict:
        """
        Marca un PDF local con la validación (útil para testing).
        
        Args:
            input_path: Ruta del PDF de entrada
            output_path: Ruta del PDF de salida
            
        Returns:
            dict: Resultado del procesamiento
        """
        try:
            # Generar la marca de validación
            marca_validacion = self.generar_marca_validacion()
            
            # Leer el PDF de entrada
            with open(input_path, 'rb') as file:
                input_pdf = PdfReader(file)
                output_pdf = PdfWriter()
                
                # Procesar cada página
                for page_num, page in enumerate(input_pdf.pages):
                    if page_num == 0:  # Solo marcar la primera página
                        # Obtener dimensiones de la página
                        page_box = page.mediabox
                        page_width = float(page_box.width)
                        page_height = float(page_box.height)
                        
                        # Crear overlay con la marca
                        overlay_bytes = self.crear_overlay_marca(marca_validacion, page_width, page_height)
                        
                        # Leer el overlay
                        overlay_pdf = PdfReader(io.BytesIO(overlay_bytes))
                        overlay_page = overlay_pdf.pages[0]
                        
                        # Combinar la página original con el overlay
                        page.merge_page(overlay_page)
                    
                    # Agregar la página al PDF de salida
                    output_pdf.add_page(page)
                
                # Guardar el PDF modificado
                with open(output_path, 'wb') as output_file:
                    output_pdf.write(output_file)
            
            return {
                "success": True,
                "input_path": input_path,
                "output_path": output_path,
                "marca_aplicada": marca_validacion,
                "fecha_procesamiento": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error marcando PDF local: {str(e)}")
    def marcar_pagina_especifica(self, input_path: str, output_path: str, 
                                 pagina_numero: int, texto_parrafo: str,
                                 posicion: str = "derecha_centro", font_size: int = 9,
                                 color=red, max_width: float = None) -> dict:
        """
        Marca una página específica del PDF con un párrafo de texto.
        
        Args:
            input_path: Ruta del PDF de entrada
            output_path: Ruta del PDF de salida
            pagina_numero: Número de página a marcar (1-indexado)
            texto_parrafo: Texto del párrafo a agregar
            posicion: Posición del texto ("derecha_centro", "superior_izquierda", "superior_derecha")
            font_size: Tamaño de la fuente
            color: Color del texto
            max_width: Ancho máximo del texto en puntos
            
        Returns:
            dict: Resultado del procesamiento
        """
        try:
            # Leer el PDF de entrada
            with open(input_path, 'rb') as file:
                input_pdf = PdfReader(file)
                output_pdf = PdfWriter()
                
                total_pages = len(input_pdf.pages)
                
                # Validar que el número de página existe
                if pagina_numero < 1 or pagina_numero > total_pages:
                    raise ValueError(f"Página {pagina_numero} no existe. El PDF tiene {total_pages} páginas.")
                
                # Procesar cada página
                for page_num, page in enumerate(input_pdf.pages):
                    current_page_number = page_num + 1  # Convertir a 1-indexado
                    
                    if current_page_number == pagina_numero:
                        # Obtener dimensiones de la página
                        page_box = page.mediabox
                        page_width = float(page_box.width)
                        page_height = float(page_box.height)
                        
                        # Crear overlay según la posición solicitada
                        if posicion == "derecha_centro":
                            overlay_bytes = self.crear_overlay_parrafo_derecha(
                                texto_parrafo, page_width, page_height, font_size, color, max_width
                            )
                        elif posicion == "superior_izquierda":
                            overlay_bytes = self.crear_overlay_superior_izquierda(
                                texto_parrafo, page_width, page_height, font_size, color, max_width
                            )
                        elif posicion == "superior_derecha":
                            overlay_bytes = self.crear_overlay_superior_derecha(
                                texto_parrafo, page_width, page_height, font_size, color, max_width
                            )
                        else:
                            # Por defecto usar derecha_centro
                            overlay_bytes = self.crear_overlay_parrafo_derecha(
                                texto_parrafo, page_width, page_height, font_size, color, max_width
                            )
                        
                        # Leer el overlay
                        overlay_pdf = PdfReader(io.BytesIO(overlay_bytes))
                        overlay_page = overlay_pdf.pages[0]
                        
                        # Combinar la página original con el overlay
                        page.merge_page(overlay_page)
                    
                    # Agregar la página al PDF de salida
                    output_pdf.add_page(page)
                
                # Guardar el PDF modificado
                with open(output_path, 'wb') as output_file:
                    output_pdf.write(output_file)
            
            return {
                "success": True,
                "input_path": input_path,
                "output_path": output_path,
                "pagina_marcada": pagina_numero,
                "texto_agregado": texto_parrafo[:100] + "..." if len(texto_parrafo) > 100 else texto_parrafo,
                "posicion": posicion,
                "total_paginas": total_pages,
                "fecha_procesamiento": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error marcando página específica: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "input_path": input_path if 'input_path' in locals() else None,
                "pagina_numero": pagina_numero if 'pagina_numero' in locals() else None
            }
    
    def crear_overlay_superior_izquierda(self, texto_parrafo: str, page_width: float, page_height: float,
                                       font_size: int = 9, color=red, max_width: float = None) -> bytes:
        """
        Crea un overlay con texto en la parte superior izquierda.
        """
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        c.setFillColor(color)
        c.setFont("Helvetica", font_size)
        
        if max_width is None:
            max_width = page_width / 2
        
        margin_left = 20
        margin_top = 50
        x_start = margin_left
        
        lines = self._wrap_text(c, texto_parrafo, max_width, font_size)
        line_height = font_size + 2
        y_start = page_height - margin_top
        
        for i, line in enumerate(lines):
            y_position = y_start - (i * line_height)
            c.drawString(x_start, y_position, line)
        
        c.save()
        overlay_buffer.seek(0)
        return overlay_buffer.getvalue()
    
    def crear_overlay_superior_derecha(self, texto_parrafo: str, page_width: float, page_height: float,
                                     font_size: int = 9, color=red, max_width: float = None) -> bytes:
        """
        Crea un overlay con texto en la parte superior derecha.
        """
        overlay_buffer = io.BytesIO()
        c = canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        c.setFillColor(color)
        c.setFont("Helvetica", font_size)
        
        if max_width is None:
            max_width = page_width / 2
        
        margin_right = 20
        margin_top = 50
        x_start = page_width - max_width - margin_right
        
        lines = self._wrap_text(c, texto_parrafo, max_width, font_size)
        line_height = font_size + 2
        y_start = page_height - margin_top
        
        for i, line in enumerate(lines):
            y_position = y_start - (i * line_height)
            c.drawString(x_start, y_position, line)
        
        c.save()
        overlay_buffer.seek(0)
        return overlay_buffer.getvalue()


    def marcar_pagina_especifica_gcs(self, gcs_uri: str, pagina_numero: int, texto_parrafo: str,
                                    posicion: str = "derecha_centro", font_size: int = 9,
                                    color=red, max_width: float = None, destino_folder: str = None) -> dict:
        """
        Marca una página específica del PDF desde GCS con un párrafo de texto.
        
        Args:
            gcs_uri: URI del PDF en GCS
            pagina_numero: Número de página a marcar (1-indexado)
            texto_parrafo: Texto del párrafo a agregar
            posicion: Posición del texto ("derecha_centro", "superior_izquierda", "superior_derecha")
            font_size: Tamaño de la fuente
            color: Color del texto
            max_width: Ancho máximo del texto en puntos
            destino_folder: Carpeta de destino (opcional)
            
        Returns:
            dict: Resultado del procesamiento
        """
        try:
            # Extraer información del GCS URI
            if not gcs_uri.startswith("gs://"):
                raise ValueError(f"URI inválida: {gcs_uri}")
            
            uri_parts = gcs_uri.replace("gs://", "").split("/", 1)
            source_bucket_name = uri_parts[0]
            source_blob_path = uri_parts[1]
            
            # Cliente para el bucket fuente
            source_bucket = self.client.bucket(source_bucket_name)
            source_blob = source_bucket.blob(source_blob_path)
            
            # Verificar que el archivo existe
            if not source_blob.exists():
                raise FileNotFoundError(f"El archivo no existe en GCS: {gcs_uri}")
            
            # Descargar el PDF a memoria
            logger.info(f"Descargando PDF desde: {gcs_uri}")
            pdf_content = source_blob.download_as_bytes()
            
            # Leer el PDF
            input_pdf = PdfReader(io.BytesIO(pdf_content))
            output_pdf = PdfWriter()
            
            total_pages = len(input_pdf.pages)
            
            # Validar que el número de página existe
            if pagina_numero < 1 or pagina_numero > total_pages:
                raise ValueError(f"Página {pagina_numero} no existe. El PDF tiene {total_pages} páginas.")
            
            # Procesar cada página
            for page_num, page in enumerate(input_pdf.pages):
                current_page_number = page_num + 1  # Convertir a 1-indexado
                
                if current_page_number == pagina_numero:
                    # Obtener dimensiones de la página
                    page_box = page.mediabox
                    page_width = float(page_box.width)
                    page_height = float(page_box.height)
                    
                    # Crear overlay según la posición solicitada
                    if posicion == "derecha_centro":
                        overlay_bytes = self.crear_overlay_parrafo_derecha(
                            texto_parrafo, page_width, page_height, font_size, color, max_width
                        )
                    elif posicion == "superior_izquierda":
                        overlay_bytes = self.crear_overlay_superior_izquierda(
                            texto_parrafo, page_width, page_height, font_size, color, max_width
                        )
                    elif posicion == "superior_derecha":
                        overlay_bytes = self.crear_overlay_superior_derecha(
                            texto_parrafo, page_width, page_height, font_size, color, max_width
                        )
                    else:
                        # Por defecto usar derecha_centro
                        overlay_bytes = self.crear_overlay_parrafo_derecha(
                            texto_parrafo, page_width, page_height, font_size, color, max_width
                        )
                    
                    # Leer el overlay
                    overlay_pdf = PdfReader(io.BytesIO(overlay_bytes))
                    overlay_page = overlay_pdf.pages[0]
                    
                    # Combinar la página original con el overlay
                    page.merge_page(overlay_page)
                
                # Agregar la página al PDF de salida
                output_pdf.add_page(page)
            
            # Guardar el PDF modificado en memoria
            output_buffer = io.BytesIO()
            output_pdf.write(output_buffer)
            output_buffer.seek(0)
            
            # Generar nombre para el archivo marcado
            base_name = os.path.splitext(os.path.basename(source_blob_path))[0]
            extension = os.path.splitext(source_blob_path)[1]
            
            # Construir la ruta de destino
            if destino_folder:
                destino_path = f"{destino_folder}/{base_name}_pagina{pagina_numero}_marcado{extension}"
            else:
                source_folder = os.path.dirname(source_blob_path)
                destino_path = f"{source_folder}/{base_name}_pagina{pagina_numero}_marcado{extension}" if source_folder else f"{base_name}_pagina{pagina_numero}_marcado{extension}"
            
            # Subir el PDF marcado al bucket de destino
            destino_blob = self.bucket.blob(destino_path)
            
            logger.info(f"Subiendo PDF marcado a: gs://{self.bucket_name}/{destino_path}")
            
            # Subir con metadata
            destino_blob.upload_from_file(
                output_buffer,
                content_type='application/pdf',
                rewind=True
            )
            
            # Establecer metadata personalizada
            destino_blob.metadata = {
                'texto_agregado': texto_parrafo[:200],  # Primeros 200 caracteres
                'pagina_marcada': str(pagina_numero),
                'posicion': posicion,
                'archivo_original': gcs_uri,
                'fecha_marcado': datetime.now().isoformat(),
                'procesado_por': 'pioneer_marcar_pdf_pagina'
            }
            destino_blob.patch()
            
            # Construir URI de destino
            destino_uri = f"gs://{self.bucket_name}/{destino_path}"
            
            logger.info(f"PDF marcado exitosamente: {destino_uri}")
            
            return {
                "success": True,
                "uri_original": gcs_uri,
                "uri_marcado": destino_uri,
                "pagina_marcada": pagina_numero,
                "texto_agregado": texto_parrafo[:100] + "..." if len(texto_parrafo) > 100 else texto_parrafo,
                "posicion": posicion,
                "total_paginas": total_pages,
                "fecha_procesamiento": datetime.now().isoformat(),
                "metadata": {
                    "pages_processed": total_pages,
                    "pages_marked": 1,
                    "file_size_bytes": len(output_buffer.getvalue())
                }
            }
            
        except Exception as e:
            logger.error(f"Error marcando página específica en GCS: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "uri_original": gcs_uri if 'gcs_uri' in locals() else None,
                "pagina_numero": pagina_numero if 'pagina_numero' in locals() else None
            }
# Funciones de conveniencia para uso directo
def marcar_pdf_validacion(gcs_uri: str, bucket_destino: str = "perdidas-totales-pruebas", 
                         destino_folder: str = None) -> dict:
    """
    Función de conveniencia para marcar un PDF con validación.
    
    Args:
        gcs_uri: URI del PDF en GCS
        bucket_destino: Bucket de destino
        destino_folder: Carpeta de destino (opcional)
        
    Returns:
        dict: Resultado del procesamiento
    """
    marcador = MarcadorPDF(bucket_destino)
    return marcador.marcar_pdf_con_validacion(gcs_uri, destino_folder)


def marcar_pagina_con_parrafo(gcs_uri: str, pagina_numero: int, texto_parrafo: str,
                             posicion: str = "derecha_centro", font_size: int = 9,
                             bucket_destino: str = "perdidas-totales-pruebas",
                             destino_folder: str = None) -> dict:
    """
    Función de conveniencia para marcar una página específica con un párrafo.
    
    Args:
        gcs_uri: URI del PDF en GCS
        pagina_numero: Número de página a marcar (1-indexado)
        texto_parrafo: Texto del párrafo a agregar
        posicion: Posición del texto ("derecha_centro", "superior_izquierda", "superior_derecha")
        font_size: Tamaño de la fuente
        bucket_destino: Bucket de destino
        destino_folder: Carpeta de destino (opcional)
        
    Returns:
        dict: Resultado del procesamiento
    """
    marcador = MarcadorPDF(bucket_destino)
    return marcador.marcar_pagina_especifica_gcs(
        gcs_uri, pagina_numero, texto_parrafo, posicion, font_size, 
        destino_folder=destino_folder
    )


# Ejemplo de uso
if __name__ == "__main__":
    # Ejemplo básico: marcar primera página con validación
    print("=== Ejemplo 1: Marcado con validación ===")
    marcador = MarcadorPDF()
    
    resultado = marcador.marcar_pdf_con_validacion(
        gcs_uri="gs://perdidas-totales-pruebas/procesos/ejemplo/documento.pdf",
        destino_folder="procesos/ejemplo/marcados"
    )
    print(f"Resultado validación: {resultado}")
    
    print("\n=== Ejemplo 2: Marcado de página específica ===")
    # Ejemplo: marcar página 2 con un párrafo de información del INE
    texto_ine = """DATOS DE VALIDACIÓN INE:
    Nombre: JUAN PÉREZ GONZÁLEZ
    CURP: PEGJ850315HDFRZN01
    Vigencia: 2025
    Estado: VÁLIDO
    Fecha validación: 28 AGOSTO 2025"""
    
    resultado_pagina = marcador.marcar_pagina_especifica_gcs(
        gcs_uri="gs://perdidas-totales-pruebas/procesos/ejemplo/documento.pdf",
        pagina_numero=2,
        texto_parrafo=texto_ine,
        posicion="derecha_centro",
        font_size=8,
        destino_folder="procesos/ejemplo/marcados"
    )
    print(f"Resultado página específica: {resultado_pagina}")
    
    print("\n=== Ejemplo 3: Usando funciones de conveniencia ===")
    # Usando las funciones de conveniencia
    resultado_conv = marcar_pagina_con_parrafo(
        gcs_uri="gs://perdidas-totales-pruebas/procesos/ejemplo/documento.pdf",
        pagina_numero=3,
        texto_parrafo="ESTE DOCUMENTO HA SIDO VALIDADO AUTOMÁTICAMENTE",
        posicion="superior_derecha",
        font_size=10
    )
    print(f"Resultado conveniencia: {resultado_conv}")
