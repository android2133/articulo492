# 🌐 Monitor HTML - Guía de Uso

## 📖 Descripción

El monitor HTML (`monitor.html`) es una interfaz web simple que te permite:

- ✅ Iniciar workflows asíncronos
- ✅ Conectarse a WebSocket para seguimiento en tiempo real  
- ✅ Ver progreso visual con barra de progreso
- ✅ Monitorear log de eventos en vivo
- ✅ Ver historial de steps ejecutados

## 🚀 Cómo Usar

### 1. Abrir el Monitor

```bash
# Opción A: Desde el navegador
open /home/jose/Desktop/into_the_unknown/discovery/monitor.html

# Opción B: Servir con Python (recomendado)
cd /home/jose/Desktop/into_the_unknown/discovery
python3 -m http.server 8080
# Luego ve a: http://localhost:8080/monitor.html
```

### 2. Configurar el Monitor

1. **Discovery URL**: Debería estar en `http://localhost:8000`
2. **Workflow ID**: Obtén uno válido usando Postman o:
   ```bash
   curl http://localhost:8000/workflows | jq '.[] | .id'
   ```
3. **Nombre documento**: Cualquier nombre para identificar tu prueba
4. **UUID Proceso**: Se auto-genera, pero puedes cambiarlo
5. **Base64**: Opcional, puedes dejarlo vacío para prueba básica

### 3. Iniciar Workflow

1. Click en **"🚀 Iniciar Workflow Asíncrono"**
2. El monitor automáticamente:
   - Guarda el execution_id
   - Conecta el WebSocket
   - Comienza a mostrar eventos en tiempo real

### 4. Monitorear Progreso

**En tiempo real verás:**
- 🚀 Workflow iniciado
- ▶️ Step iniciado: nombre_del_step
- 📈 Progreso: 25% - Mensaje de progreso
- ✅ Step completado: nombre_del_step
- 🎉 Workflow COMPLETADO

**La interfaz muestra:**
- **Barra de progreso visual** con porcentaje
- **Estado actual** (running/completed/failed)
- **Step actual** que se está ejecutando
- **Historial de steps** con estados
- **Log en tiempo real** de todos los eventos

## 🎯 Características

### WebSocket en Tiempo Real
- Conexión automática al iniciar workflow
- Eventos de progreso instantáneos
- Notificaciones de completado/error
- Log persistente de toda la sesión

### Interfaz Visual
- Barra de progreso animada
- Códigos de color por estado
- Timestamps en todos los eventos
- Scroll automático en el log

### Compatibilidad
- Endpoint RESTful nuevo
- Endpoint legacy para compatibilidad
- Auto-configuración de variables
- Manejo de errores y reconexión

## 🔧 Troubleshooting

### WebSocket no se conecta
```
❌ Error conectando WebSocket: Error message
```
**Solución:**
- Verifica que Discovery esté corriendo en puerto 8000
- Asegúrate de que el execution_id sea válido
- Revisa la consola del navegador para más detalles

### Workflow no inicia
```
❌ Error iniciando workflow: 404 - Workflow no encontrado
```
**Solución:**
- Usa el comando para obtener un workflow_id válido:
  ```bash
  curl http://localhost:8000/workflows
  ```
- Copia un ID de la respuesta y pégalo en el campo

### No hay progreso
```
⏳ Esperando eventos...
```
**Solución:**
- Verifica logs de Docker:
  ```bash
  docker compose logs -f discovery pioneer
  ```
- Asegúrate de que el PDF base64 sea válido si lo proporcionaste

## 💡 Tips de Uso

1. **Deja el WebSocket conectado** para ver todos los eventos
2. **Usa "Verificar Estado"** si quieres refrescar manualmente
3. **El log se puede limpiar** con el botón "🗑️ Limpiar Log"
4. **Puedes iniciar múltiples workflows** - cada uno tendrá su execution_id
5. **Si se desconecta**, reconecta con el execution_id

## 🔗 Integración con Postman

**El monitor HTML y Postman se complementan:**

- **Monitor HTML**: Para seguimiento visual en tiempo real
- **Postman**: Para APIs detalladas y automatización

**Flujo recomendado:**
1. Usa monitor HTML para iniciar y ver progreso general
2. Usa Postman para consultas detalladas de estado
3. Usa ambos para debugging completo

## 📊 Ejemplos de Eventos

### Inicio de Workflow
```
[10:30:15] 🚀 Workflow iniciado
[10:30:16] ▶️ Step iniciado: Carga Usuario
```

### Progreso de Step
```
[10:30:20] 📈 Carga Usuario: 25% - Preparando documento para análisis
[10:30:35] 📈 Carga Usuario: 60% - Procesando con modelo dinámico
[10:30:50] 📈 Carga Usuario: 85% - Subiendo archivos a GCS
```

### Completado
```
[10:31:00] ✅ Step completado: Carga Usuario
[10:31:01] ▶️ Step iniciado: Validación Usuario
[10:31:15] ✅ Step completado: Validación Usuario
[10:31:16] 🎉 Workflow COMPLETADO exitosamente!
```

### Error
```
[10:30:45] ❌ Workflow FALLÓ
[10:30:45] 💥 Error en workflow: Connection timeout to GCS
```

¡El monitor HTML te da una experiencia visual completa del progreso de tus workflows!
