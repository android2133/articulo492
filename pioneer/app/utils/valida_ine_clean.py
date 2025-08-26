from selenium import webdriver
from selenium.webdriver.chrome.options import Options

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import time
from twocaptcha import TwoCaptcha
import json
import uuid
from typing import Dict, Any, Optional

# --- CONFIGURACIÓN DE 2CAPTCHA ---
API_KEY = "bb81274dd275803a8dddfbf365cfbdb6" 
solver = TwoCaptcha(API_KEY)
# ------------------------------------

def get_chrome_driver():
    """Configura y retorna un driver de Chrome"""
    try:
        opts = Options()
        opts.add_argument("--headless=new")          # Headless moderno (Chrome 109+)
        opts.add_argument("--window-size=1920,1080") # Importante en headless
        opts.add_argument("--disable-gpu")           # (harmless en Linux)
        opts.add_argument("--no-sandbox")            # Útil en Docker/CI
        opts.add_argument("--disable-dev-shm-usage") # Evita /dev/shm pequeño en contenedores
        opts.add_argument("--disable-extensions")    # Deshabilitar extensiones
        opts.add_argument("--disable-plugins")       # Deshabilitar plugins
        opts.add_argument("--disable-images")        # No cargar imágenes (más rápido)
        opts.add_argument("--single-process")        # Usar un solo proceso
        opts.add_argument("--disable-background-timer-throttling")
        opts.add_argument("--disable-renderer-backgrounding")
        opts.add_argument("--disable-backgrounding-occluded-windows")
        
        driver = webdriver.Chrome(options=opts)
        driver.maximize_window()
        return driver
    except Exception as e:
        print(f"❌ Error configurando Chrome driver: {e}")
        raise Exception(f"Chrome driver no disponible: {e}")

# --- FUNCIÓN PARA RESOLVER EL CAPTCHA ---
def solve_captcha(driver, form_element):
    """
    Encuentra el reCAPTCHA dentro de un formulario, lo resuelve usando 2Captcha
    e inyecta la solución.
    """
    try:
        print("🔍 Buscando el sitekey del reCAPTCHA...")
        # 2. Encontrar el sitekey dentro del div g-recaptcha del formulario actual
        sitekey = form_element.find_element(By.CLASS_NAME, "g-recaptcha").get_attribute("data-sitekey")
        page_url = driver.current_url
        
        print(f"✅ Sitekey encontrado: {sitekey}")
        print("⏳ Enviando CAPTCHA a 2Captcha para resolución... (esto puede tardar)")

        # 3. Enviar la petición a 2Captcha
        result = solver.recaptcha(
            sitekey=sitekey,
            url=page_url
        )

        # 4. Obtener el token de respuesta
        captcha_response_token = result['code']
        print("✅ CAPTCHA resuelto. Token recibido.")

        # 5. Inyectar el token en el textarea oculto (g-recaptcha-response)
        # Usamos JavaScript porque el elemento está oculto y send_keys no funcionaría.
        response_textarea = form_element.find_element(By.CLASS_NAME, "g-recaptcha-response")
        driver.execute_script(f"arguments[0].innerHTML = '{captcha_response_token}';", response_textarea)
        print("💉 Token inyectado en el formulario.")
        return True

    except Exception as e:
        print(f"❌ Error al resolver el CAPTCHA: {e}")
        return False
# -----------------------------------------

def validar_ine_con_modelo_identificado(resultado_llm_modelo_ine: Dict[str, Any]) -> Dict[str, Any]:
    """
    Valida una INE en la página oficial basándose en el modelo identificado por el LLM.
    
    Args:
        resultado_llm_modelo_ine: Diccionario con el modelo identificado y datos extraídos
        
    Returns:
        Diccionario con el resultado de la validación
    """
    
    # Verificar si hay error en el resultado del LLM
    if "error" in resultado_llm_modelo_ine:
        return {
            "error": "No se pudo identificar el modelo de INE",
            "detalles": resultado_llm_modelo_ine.get("detalles", ""),
            "validacion_exitosa": False
        }
    
    modelo_identificado = resultado_llm_modelo_ine.get("modelo_identificado", "")
    datos_extraidos = resultado_llm_modelo_ine.get("datos_extraidos", {})
    
    print(f"[VALIDA_INE] Modelo identificado: {modelo_identificado}")
    print(f"[VALIDA_INE] Datos extraídos: {datos_extraidos}")
    
    # Determinar qué formulario usar basado en el modelo
    if "Modelo E, F, G o H" in modelo_identificado:
        modelo_form = "EFGH"
        campos_requeridos = ["CIC", "Identificador_Ciudadano"]
    elif "Modelo D" in modelo_identificado:
        modelo_form = "D"
        campos_requeridos = ["CIC", "OCR"]
    elif "Modelo A, B o C" in modelo_identificado:
        modelo_form = "C"
        campos_requeridos = ["Clave de Elector", "Número de Emisión", "Número OCR (Vertical)"]
    else:
        return {
            "error": "Modelo de INE no reconocido",
            "modelo_recibido": modelo_identificado,
            "validacion_exitosa": False
        }
    
    # Verificar que tenemos los campos requeridos
    campos_faltantes = []
    for campo in campos_requeridos:
        if campo not in datos_extraidos or not datos_extraidos[campo]:
            campos_faltantes.append(campo)
    
    if campos_faltantes:
        return {
            "error": "Faltan campos requeridos para la validación",
            "campos_faltantes": campos_faltantes,
            "validacion_exitosa": False
        }
    
    # VERIFICAR SI SELENIUM ESTÁ DISPONIBLE EN EL ENTORNO
    try:
        print("[VALIDA_INE] Verificando disponibilidad de Chrome/Selenium...")
        driver = get_chrome_driver()
        driver.quit()  # Test exitoso, cerrar inmediatamente
        print("[VALIDA_INE] ✅ Chrome/Selenium disponible")
    except Exception as selenium_error:
        print(f"[VALIDA_INE] ⚠️ Chrome/Selenium no disponible: {selenium_error}")
        return {
            "error": "Validación de INE no disponible en este entorno (Selenium/Chrome no configurado)",
            "detalles": str(selenium_error),
            "validacion_exitosa": False,
            "modo_desarrollo": True,
            "datos_procesados": {
                "modelo_form": modelo_form,
                "datos_extraidos": datos_extraidos
            }
        }
    
    driver = None
    try:
        # Configurar driver
        driver = get_chrome_driver()
        
        url = "https://listanominal.ine.mx/scpln/"
        driver.get(url)
        
        wait = WebDriverWait(driver, 20)
        
        # Seleccionar y llenar el formulario apropiado
        if modelo_form == "EFGH":
            form = wait.until(EC.visibility_of_element_located((By.ID, "formEFGH")))
            
            # Procesar CIC para modelo EFGH: remover "IDMEX" del inicio y último dígito
            cic_original = datos_extraidos["CIC"]
            cic_procesado = cic_original
            if cic_original.startswith("IDMEX"):
                # Remover "IDMEX" del inicio y último dígito del final
                cic_sin_prefijo = cic_original[5:]  # Quitar "IDMEX"
                cic_procesado = cic_sin_prefijo[:-1]  # Quitar último dígito
            
            # Procesar Identificador_Ciudadano para modelo EFGH: tomar últimos 9 dígitos
            id_ciudadano_original = datos_extraidos["Identificador_Ciudadano"]
            id_ciudadano_procesado = id_ciudadano_original[-9:]  # Últimos 9 dígitos
            
            print(f"[VALIDA_INE] CIC original: {cic_original} -> procesado: {cic_procesado}")
            print(f"[VALIDA_INE] ID Ciudadano original: {id_ciudadano_original} -> procesado: {id_ciudadano_procesado}")
            
            form.find_element(By.ID, "cic").send_keys(cic_procesado)
            form.find_element(By.ID, "idCiudadano").send_keys(id_ciudadano_procesado)
            
        elif modelo_form == "D":
            form = wait.until(EC.visibility_of_element_located((By.ID, "formD")))
            form.find_element(By.ID, "cic").send_keys(datos_extraidos["CIC"])
            form.find_element(By.ID, "ocr").send_keys(datos_extraidos["OCR"])
            
        elif modelo_form == "C":
            form = wait.until(EC.visibility_of_element_located((By.ID, "formC")))
            form.find_element(By.ID, "claveElector").send_keys(datos_extraidos["Clave de Elector"])
            form.find_element(By.ID, "numeroEmision").send_keys(datos_extraidos["Número de Emisión"])
            form.find_element(By.ID, "ocr").send_keys(datos_extraidos["Número OCR (Vertical)"])

        print("✅ Campos llenados.")
        
        # Resolver CAPTCHA y enviar formulario
        if solve_captcha(driver, form):
            print("🚀 Enviando formulario...")
            consultar_button = form.find_element(By.CSS_SELECTOR, "button[type='submit']")
            driver.execute_script("arguments[0].click();", consultar_button)
        else:
            return {
                "error": "No se pudo resolver el CAPTCHA",
                "validacion_exitosa": False
            }

        # Esperar y procesar resultados
        print("🔍 Esperando resultados...")
        
        contenedor_resultado = wait.until(EC.visibility_of_element_located((By.XPATH, "//section[.//table[contains(@class, 'table-bordered')]]")))
        print("✅ Página de resultados cargada.")

        # Tomar captura de pantalla
        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", contenedor_resultado)
            time.sleep(1)
            
            nombre_archivo = f"resultado_ine_{uuid.uuid4()}.png"
            contenedor_resultado.screenshot(nombre_archivo)
            print(f"✅ Captura guardada: {nombre_archivo}")
        except Exception as e:
            print(f"⚠️ No se pudo tomar captura: {e}")
            nombre_archivo = None

        # Procesar HTML de resultados
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # Buscar tabla de resultado
        tabla = soup.select_one("section.no-margin.no-padding .table.table-bordered")
        resultado = {}

        if tabla:
            for fila in tabla.find_all("tr"):
                celdas = fila.find_all("td")
                if len(celdas) == 2:
                    clave = celdas[0].get_text(strip=True)
                    valor = celdas[1].get_text(strip=True)
                    resultado[clave] = valor

        # Extraer estado y vigencia
        vigencia = soup.select_one("section.no-margin.no-padding h4 mark")
        estado = soup.select_one("section.no-margin.no-padding h4[style*='color']")

        if estado:
            resultado["Estado"] = estado.get_text(strip=True)
        if vigencia:
            resultado["Válida hasta"] = vigencia.get_text(strip=True)

        # Mapear claves para estandarizar
        key_mapping = {
            "CIC": "cic",
            "Clave de elector": "clave_elector",
            "Número de emisión": "numero_emision",
            "Distrito Federal": "distrito_federal",
            "Distrito Local": "distrito_local",
            "Número OCR": "numero_ocr",
            "Año de registro": "anio_de_registro",
            "Año de emisión": "anio_de_emision",
            "Estado": "estado",
            "Válida hasta": "valida_hasta"
        }

        resultado_estandarizado = {}
        for clave_original, valor in resultado.items():
            nueva_clave = key_mapping.get(clave_original, clave_original.lower().replace(' ', '_'))
            resultado_estandarizado[nueva_clave] = valor

        # Retornar resultado de validación
        validacion_exitosa = "estado" in resultado_estandarizado and resultado_estandarizado["estado"].upper() == "VIGENTE"
        
        return {
            "validacion_exitosa": validacion_exitosa,
            "modelo_usado": modelo_form,
            "datos_utilizados": datos_extraidos,
            "resultado_ine": resultado_estandarizado,
            "captura_pantalla": nombre_archivo,
            "timestamp": time.time()
        }

    except Exception as e:
        print(f"❌ Error durante la validación: {e}")
        return {
            "error": f"Error durante la validación: {str(e)}",
            "validacion_exitosa": False,
            "detalles_error": str(e)
        }
        
    finally:
        if driver:
            driver.quit()


# Función de compatibilidad con el código anterior (mantener por si se necesita)
def validar_ine_manual(modelo: str, **datos) -> Dict[str, Any]:
    """
    Función de compatibilidad para validación manual.
    Se recomienda usar validar_ine_con_modelo_identificado()
    """
    
    if modelo == "EFGH":
        resultado_llm = {
            "modelo_identificado": "Modelo E, F, G o H",
            "datos_extraidos": {
                "CIC": datos.get("cic", ""),
                "Identificador_Ciudadano": datos.get("identificador_ciudadano", "")
            }
        }
    elif modelo == "D":
        resultado_llm = {
            "modelo_identificado": "Modelo D",
            "datos_extraidos": {
                "CIC": datos.get("cic", ""),
                "OCR": datos.get("ocr", "")
            }
        }
    elif modelo == "C":
        resultado_llm = {
            "modelo_identificado": "Modelo A, B o C",
            "datos_extraidos": {
                "Clave de Elector": datos.get("clave_elector", ""),
                "Número de Emisión": datos.get("numero_emision", ""),
                "Número OCR (Vertical)": datos.get("ocr", "")
            }
        }
    else:
        return {
            "error": "Modelo no reconocido",
            "validacion_exitosa": False
        }
    
    return validar_ine_con_modelo_identificado(resultado_llm)


# === EJEMPLO DE USO ===
if __name__ == "__main__":
    
    # Ejemplo 1: Modelo E, F, G o H
    resultado_llm_ejemplo_efgh = {
        "modelo_identificado": "Modelo E, F, G o H",
        "datos_extraidos": {
            "CIC": "IDMEX1993551274",
            "Identificador_Ciudadano": "5263015044716"
        }
    }
    
    # Ejemplo 2: Modelo D
    resultado_llm_ejemplo_d = {
        "modelo_identificado": "Modelo D",
        "datos_extraidos": {
            "CIC": "IDMEX1836577170",
            "OCR": "07471163758428007057M1812315MEX"
        }
    }
    
    # Ejemplo 3: Modelo A, B o C
    resultado_llm_ejemplo_abc = {
        "modelo_identificado": "Modelo A, B o C",
        "datos_extraidos": {
            "Clave de Elector": "GOMVMA83030301M100",
            "Número de Emisión": "01",
            "Número OCR (Vertical)": "123456789012"
        }
    }
    
    # Ejemplo 4: Error
    resultado_llm_ejemplo_error = {
        "error": "La imagen no es legible o no corresponde a una credencial para votar válida.",
        "detalles": "No se pudieron extraer los datos requeridos con precisión."
    }
    
    print("=== EJEMPLOS DE USO ===")
    print("\n1. Ejemplo Modelo E, F, G o H:")
    print(json.dumps(resultado_llm_ejemplo_efgh, indent=2, ensure_ascii=False))
    
    print("\n2. Ejemplo Modelo D:")
    print(json.dumps(resultado_llm_ejemplo_d, indent=2, ensure_ascii=False))
    
    print("\n3. Ejemplo Modelo A, B o C:")
    print(json.dumps(resultado_llm_ejemplo_abc, indent=2, ensure_ascii=False))
    
    print("\n4. Ejemplo con Error:")
    print(json.dumps(resultado_llm_ejemplo_error, indent=2, ensure_ascii=False))
    
    print("\n=== PARA USAR EN PRODUCCIÓN ===")
    print("# Importar la función:")
    print("# from app.utils.valida_ine import validar_ine_con_modelo_identificado")
    print("#")
    print("# Usar con el resultado del LLM:")
    print("# resultado_validacion = validar_ine_con_modelo_identificado(resultado_llm_modelo_ine)")
    print("#")
    print("# El resultado incluirá:")
    print("# - validacion_exitosa: bool")
    print("# - modelo_usado: str")
    print("# - datos_utilizados: dict")
    print("# - resultado_ine: dict (información de la INE desde la página oficial)")
    print("# - captura_pantalla: str (nombre del archivo de captura)")
    print("# - timestamp: float")
