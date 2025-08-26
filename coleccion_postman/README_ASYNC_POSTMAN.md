# 🚀 Guía de Uso: Colección Postman de Ejecución Asíncrona

## 📥 Importar la Colección

1. Abre Postman
2. Click en "Import" 
3. Selecciona el archivo: `Async_Workflow_Execution.postman_collection.json`
4. Importa la colección

## ⚙️ Configuración Inicial

### 1. Configurar Environment

Crea un nuevo Environment en Postman con estas variables:

```
discovery_base_url = http://localhost:8000
workflow_id = [obtendrás este de "Listar Workflows"]
pdf_base64 = [tu archivo PDF en base64]
execution_id = [se auto-configura al ejecutar workflows]
websocket_url = [se auto-configura al ejecutar workflows]
```

### 2. Obtener tu archivo PDF en Base64

**Opción A: Usando terminal (Linux/Mac)**
```bash
base64 -w 0 tu_archivo.pdf > archivo_base64.txt
```

**Opción B: Usando Python**
```python
import base64

with open("tu_archivo.pdf", "rb") as pdf_file:
    base64_string = base64.b64encode(pdf_file.read()).decode('utf-8')
    print(base64_string)
```

**Opción C: Usando sitio web**
- Ve a: https://base64.guru/converter/encode/pdf
- Sube tu PDF
- Copia el resultado

### 3. Obtener Workflow ID

1. Ejecuta: **"📋 Gestión de Workflows" > "Listar Workflows Disponibles"**
2. Copia el `id` del workflow que quieres usar
3. Pegalo en la variable `workflow_id` de tu environment

## 🎯 Flujo de Prueba Recomendado

### Paso 1: Verificar Sistema
```
📋 Gestión de Workflows > Listar Workflows Disponibles
```
- Verifica que haya workflows disponibles
- Copia un `workflow_id` para usar

### Paso 2: Ejecutar Workflow Asíncrono
```
🚀 Ejecución Asíncrona > Ejecutar Workflow Asíncrono (RESTful)
```
- **Esto devuelve inmediatamente** un `execution_id`
- Se auto-guardan las variables para siguientes requests
- El workflow se ejecuta en background

### Paso 3: Monitorear Progreso
```
📊 Seguimiento y Estado > Consultar Estado Completo
```
- Ejecuta múltiples veces para ver el progreso
- Ve el porcentaje completado
- Identifica en qué step está

### Paso 4: Ver Detalles
```
📊 Seguimiento y Estado > Historial de Steps Ejecutados
```
- Ve todos los steps que se han ejecutado
- Revisa tiempos de ejecución
- Identifica errores si los hay

## 🔍 Casos de Prueba

### Caso 1: Workflow Completo con Documento Real
1. Configura `pdf_base64` con tu archivo
2. Ejecuta "Ejecutar Workflow Asíncrono"
3. Monitorea con "Consultar Estado Completo"
4. Verifica resultado con "Historial de Steps"

### Caso 2: Comparar Síncrono vs Asíncrono
1. Ejecuta "Ejecutar Workflow Síncrono" - espera resultado
2. Ejecuta "Ejecutar Workflow Asíncrono" - devuelve inmediato
3. Usa "Consultar Estado" para seguir el asíncrono

### Caso 3: Múltiples Ejecuciones
1. Ejecuta varios workflows asíncronos
2. Usa diferentes `execution_id` para seguir cada uno
3. Ve historial con "Historial de Ejecuciones del Workflow"

## 📡 WebSocket (Opcional)

Para seguimiento en tiempo real, usa JavaScript en el navegador:

```javascript
// Usa el websocket_url que se guarda automáticamente
const ws = new WebSocket('ws://localhost:8000/ws/your-execution-id');

ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    console.log('Evento:', data.event);
    
    if (data.event === 'step_progress') {
        console.log(`Progreso: ${data.progress.percentage}%`);
    }
};
```

O abre el archivo HTML: `/discovery/monitor.html` en tu navegador.

## 🐛 Troubleshooting

### Error: "Workflow no encontrado"
- Verifica que `workflow_id` esté configurado correctamente
- Ejecuta "Listar Workflows" para ver IDs disponibles

### Error: "Ejecución no encontrada"
- Verifica que `execution_id` esté configurado
- Asegúrate de ejecutar primero "Ejecutar Workflow Asíncrono"

### Workflow no progresa
- Usa "Consultar Estado Completo" para ver detalles
- Revisa logs de Docker: `docker compose logs pioneer discovery`

### PDF no se procesa
- Verifica que `pdf_base64` sea válido
- Asegúrate de que sea un PDF real
- Verifica que no falten headers/footers en el base64

## 📊 Interpretando Respuestas

### Estado del Workflow
- `running`: En ejecución
- `completed`: Terminado exitosamente  
- `failed`: Falló por algún error
- `paused`: Pausado (modo manual)

### Progreso
- `percentage`: 0-100% completado
- `completed_steps`: Cuántos steps han terminado
- `total_steps`: Total de steps en el workflow
- `is_running`: Si está ejecutándose actualmente

### Steps
- `success`: Step completado exitosamente
- `failed`: Step falló
- `running`: Step ejecutándose actualmente
- `pending`: Step no iniciado aún

## 💡 Tips

1. **Siempre empieza con "Listar Workflows"** para obtener IDs válidos
2. **Guarda los `execution_id`** para poder consultar después
3. **Usa archivos PDF reales** para pruebas completas
4. **Monitorea logs de Docker** si hay problemas
5. **El sistema persiste todo** - puedes desconectarte y volver
6. **Cada ejecución es independiente** - múltiples usuarios pueden usar el mismo workflow

## 🎯 Beneficios del Sistema Asíncrono

- ✅ **Sin timeouts**: Workflows pueden durar horas
- ✅ **Seguimiento granular**: Ve exactamente dónde está
- ✅ **Progreso en tiempo real**: Steps reportan avance
- ✅ **Múltiples usuarios**: Varios pueden usar simultáneamente  
- ✅ **Recuperación**: Si se desconecta, puede reconectarse
- ✅ **Historial completo**: Todo se persiste en base de datos
