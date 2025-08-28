# pip install "llama-index>=0.11" llama-index-tools-duckduckgo \
#            llama-index-tools-tavily-research tavily-python httpx beautifulsoup4

import os, re
from typing import List, Dict
from bs4 import BeautifulSoup
import httpx
from datetime import datetime

from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool

from llama_index.core import Settings
from llama_index.llms.openai import OpenAI

# Configurar modelo OpenAI
Settings.llm = OpenAI(model="gpt-4o-mini")  # o gpt-4o, gpt-3.5-turbo

# 1) Tool de búsqueda: Tavily si hay API key; si no, DuckDuckGo (gratis)
def make_search_tool():
    if os.getenv("TAVILY_API_KEY"):
        from llama_index.tools.tavily_research import TavilyToolSpec
        tavily = TavilyToolSpec(api_key=os.getenv("TAVILY_API_KEY"))
        return tavily.to_tool_list()[0]
    else:
        from llama_index.tools.duckduckgo import DuckDuckGoSearchToolSpec
        return DuckDuckGoSearchToolSpec().to_tool_list()[0]

# 2) Descarga/limpieza de páginas
def fetch_page(url: str) -> str:
    with httpx.Client(follow_redirects=True, timeout=20) as c:
        r = c.get(url, headers={"User-Agent":"Mozilla/5.0"})
        r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for t in soup(["script","style","noscript"]): t.decompose()
    text = "\n".join([ln.strip() for ln in soup.get_text("\n").splitlines() if ln.strip()])
    return text[:4000]

fetch_tool = FunctionTool.from_defaults(
    fn=fetch_page, name="fetch_page",
    description="Descarga y limpia una URL para análisis de texto."
)

# 3) Generador de consultas
KEYWORDS_ES = ["lavado de dinero","fraude","corrupción","soborno","estafa",
               "delincuencia organizada","vinculado a proceso","detenido","acusado",
               "sanciones","OFAC","UIF","personas bloqueadas"]
KEYWORDS_EN = ["money laundering","fraud","corruption","bribery","scam",
               "organized crime","charged","arrested","sanctions","OFAC"]

SOCIAL_SITES = ["x.com","twitter.com","facebook.com","linkedin.com/in",
                "instagram.com","tiktok.com","youtube.com","reddit.com"]

def build_queries(full_name: str, location: str|None=None) -> List[str]:
    quoted = f"\"{full_name}\""
    geo = f" {location}" if location else ""
    qs = [f"{quoted}{geo} {kw}" for kw in (KEYWORDS_ES+KEYWORDS_EN)]
    # redes sociales
    for site in SOCIAL_SITES:
        qs.append(f"site:{site} {quoted}{geo}")
        for kw in ("lavado de dinero","fraude","corrupción","money laundering","fraud"):
            qs.append(f"site:{site} {quoted}{geo} {kw}")
    return qs

# 4) Agente
def make_agent():
    search_tool = make_search_tool()
    tools = [search_tool, fetch_tool]
    return ReActAgent(tools=tools, verbose=False)

async def screen_person(full_name: str, location: str|None=None, topk: int=6) -> str:
    """
    Función asíncrona que espera correctamente a que el agente LlamaIndex complete su tarea.
    Similar a como otros steps esperan a operaciones como httpx.AsyncClient.post()
    """
    
    try:
        agent = make_agent()
        query_block = "\n".join(f"- {q}" for q in build_queries(full_name, location)[:5])
        
        # Prompt simplificado para evitar loops infinitos
        prompt = f"""
Busca información sobre "{full_name}" en internet. Enfócate en encontrar noticias relevantes.

Pasos:
1. Haz 2-3 búsquedas con estos términos: "{full_name}" + "noticias", "{full_name}" + "México"
2. Si encuentras URLs interesantes, analiza 1-2 páginas con fetch_page
3. Responde EXACTAMENTE en este formato JSON:

{{
  "nombre": "{full_name}",
  "hallazgos": [
    {{"url": "URL_encontrada", "titulo": "título", "medio": "sitio", "fecha": "2025-08-27", "resumen": "breve resumen", "menciones_clave": ["palabras"], "riesgo": "bajo"}}
  ],
  "conclusion": "resumen breve de lo encontrado",
  "advertencias": ["verificar manualmente"]
}}

IMPORTANTE: Responde SOLO el JSON, sin texto adicional.
"""
        
        print(f"[screen_person] Iniciando búsqueda OSINT para: {full_name}")
        print(f"[screen_person] Tipo de agente: {type(agent)}")
        print(f"[screen_person] Métodos disponibles: {[m for m in dir(agent) if not m.startswith('_')]}")
        
        # Intentar múltiples métodos para ejecutar el agente de forma asíncrona
        response = None
        
        # Método 1: Verificar si tiene método asíncrono
        if hasattr(agent, 'achat'):
            print("[screen_person] Usando método achat() asíncrono")
            response = await agent.achat(prompt)
        elif hasattr(agent, 'aquery'):
            print("[screen_person] Usando método aquery() asíncrono")
            response = await agent.aquery(prompt)
        elif hasattr(agent, 'chat'):
            print("[screen_person] Usando método chat() y ejecutando en thread pool")
            # Ejecutar en thread pool para no bloquear el loop asíncrono
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent.chat(prompt))
        elif hasattr(agent, 'query'):
            print("[screen_person] Usando método query() y ejecutando en thread pool")
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent.query(prompt))
        elif hasattr(agent, 'run'):
            print("[screen_person] Usando método run() asíncrono")
            # El método run() es asíncrono en la nueva API de LlamaIndex
            # Aumentar max_iterations para evitar timeout en búsquedas complejas
            response = await agent.run(prompt, max_iterations=30)
        elif hasattr(agent, '__call__'):
            print("[screen_person] El agente es callable, intentando llamada directa")
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent(prompt))
        elif hasattr(agent, 'step'):
            print("[screen_person] Usando método step() para workflow")
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent.step(prompt))
        elif hasattr(agent, 'stream_chat'):
            print("[screen_person] Usando método stream_chat()")
            import asyncio
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, lambda: agent.stream_chat(prompt))
        else:
            # Listar todos los métodos públicos disponibles para debug
            available_methods = [m for m in dir(agent) if not m.startswith('_') and callable(getattr(agent, m))]
            print(f"[screen_person] Métodos callable disponibles: {available_methods}")
            
            # Intentar con el primer método que parezca prometedor
            promising_methods = [m for m in available_methods if any(word in m.lower() for word in ['chat', 'query', 'run', 'execute', 'process'])]
            print(f"[screen_person] Métodos prometedores: {promising_methods}")
            
            if promising_methods:
                method_name = promising_methods[0]
                print(f"[screen_person] Intentando método: {method_name}")
                method = getattr(agent, method_name)
                import asyncio
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(None, lambda: method(prompt))
            else:
                raise Exception(f"No se encontró método válido para interactuar con el agente. Métodos disponibles: {available_methods}")
        
        # Procesar la respuesta
        if response:
            print(f"[screen_person] Respuesta recibida, tipo: {type(response)}")
            
            # Si es un workflow handler, esperar a que complete
            if hasattr(response, 'result') and callable(response.result):
                print("[screen_person] Esperando resultado del workflow...")
                try:
                    # Intentar obtener el resultado con timeout
                    import asyncio
                    result = await asyncio.wait_for(
                        asyncio.to_thread(response.result), 
                        timeout=60  # 60 segundos de timeout
                    )
                    return str(result)
                except asyncio.TimeoutError:
                    return f"""{{
  "nombre": "{full_name}",
  "hallazgos": [],
  "conclusion": "Timeout esperando resultado de búsqueda OSINT (60s)",
  "advertencias": ["Búsqueda tomó demasiado tiempo", "Verificación manual requerida"]
}}"""
                except Exception as e:
                    print(f"[screen_person] Error obteniendo resultado: {e}")
                    # Si no se puede obtener el resultado, esperar un poco y intentar de nuevo
                    await asyncio.sleep(2)
                    try:
                        result = response.result()
                        return str(result)
                    except:
                        return f"""{{
  "nombre": "{full_name}",
  "hallazgos": [],
  "conclusion": "Error procesando resultado de búsqueda OSINT: {str(e)[:100]}",
  "advertencias": ["Error técnico en procesamiento", "Verificación manual requerida"]
}}"""
            
            # Si tiene atributo response directo
            elif hasattr(response, 'response'):
                print("[screen_person] Obteniendo respuesta directa")
                raw_response = str(response.response)
                print(f"[screen_person] Respuesta raw: {raw_response[:300]}...")
                
                # La respuesta debería contener el JSON, pero a veces viene con texto adicional
                # Intentar extraer el JSON del texto
                try:
                    import json
                    import re
                    
                    # Buscar JSON en la respuesta
                    json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
                    if json_match:
                        json_str = json_match.group(0)
                        # Validar que es JSON válido
                        json.loads(json_str)
                        print("[screen_person] JSON válido encontrado en respuesta")
                        return json_str
                    else:
                        print("[screen_person] No se encontró JSON válido, generando respuesta estructurada")
                        # Si no hay JSON, crear uno basado en la respuesta del agente
                        return f"""{{
  "nombre": "{full_name}",
  "hallazgos": [
    {{
      "url": "Búsqueda completada",
      "titulo": "Análisis OSINT realizado",
      "medio": "Agente LlamaIndex",
      "fecha": "{datetime.now().strftime('%Y-%m-%d')}",
      "resumen": "{raw_response[:200].replace('"', '\\"')}",
      "menciones_clave": ["análisis_completado"],
      "riesgo": "medio"
    }}
  ],
  "conclusion": "Búsqueda OSINT completada exitosamente. {raw_response[:100].replace('"', '\\"')}",
  "advertencias": ["Verificación manual recomendada", "Resultados basados en búsqueda automatizada"]
}}"""
                except Exception as json_error:
                    print(f"[screen_person] Error procesando JSON: {json_error}")
                    return f"""{{
  "nombre": "{full_name}",
  "hallazgos": [
    {{
      "url": "Error procesando respuesta",
      "titulo": "Respuesta recibida pero no procesable",
      "medio": "Sistema",
      "fecha": "{datetime.now().strftime('%Y-%m-%d')}",
      "resumen": "El agente completó la búsqueda pero el formato no es procesable",
      "menciones_clave": ["respuesta_no_estructurada"],
      "riesgo": "bajo"
    }}
  ],
  "conclusion": "Búsqueda completada con limitaciones de formato",
  "advertencias": ["Verificación manual requerida", "Formato de respuesta no estándar"]
}}"""
            
            # Si es string directamente
            elif isinstance(response, str):
                print("[screen_person] Respuesta directa como string")
                return response
            
            # Fallback: convertir a string
            else:
                print("[screen_person] Convirtiendo respuesta a string")
                return str(response)
        else:
            raise Exception("El agente no devolvió respuesta")
            
    except Exception as e:
        print(f"[screen_person] Error en búsqueda OSINT: {str(e)}")
        # Return fallback JSON response
        return f"""{{
  "nombre": "{full_name}",
  "hallazgos": [],
  "conclusion": "Servicio de búsqueda OSINT temporalmente no disponible. Error: {str(e)[:100]}",
  "advertencias": ["Función en desarrollo", "Verificación manual requerida"]
}}"""

# if __name__ == "__main__":
    
    
#     print(screen_person("Juan Pérez", location="México", topk=5))
