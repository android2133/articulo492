#!/bin/bash

# Script de utilidades para Into the Unknown

set -e

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir con colores
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${BLUE}=== $1 ===${NC}"
}

# Función para verificar si Docker está corriendo
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker no está corriendo. Por favor inicia Docker primero."
        exit 1
    fi
}

# Función para mostrar el estado de los servicios
status() {
    print_header "Estado de los Servicios"
    docker-compose ps
}

# Función para iniciar todos los servicios
start() {
    print_header "Iniciando todos los servicios"
    check_docker
    docker-compose up -d
    print_status "Servicios iniciados. Usa './scripts.sh status' para verificar el estado."
    print_status "URLs disponibles:"
    echo "  - Discovery API: http://localhost:8000"
    echo "  - Pioneer Service: http://localhost:8001" 
    echo "  - Challenger Service: http://localhost:8002"
}

# Función para parar todos los servicios
stop() {
    print_header "Parando todos los servicios"
    docker-compose down
    print_status "Servicios parados."
}

# Función para ver logs
logs() {
    if [ -z "$1" ]; then
        print_header "Logs de todos los servicios"
        docker-compose logs -f
    else
        print_header "Logs del servicio: $1"
        docker-compose logs -f "$1"
    fi
}

# Función para reconstruir servicios
rebuild() {
    if [ -z "$1" ]; then
        print_header "Reconstruyendo todos los servicios"
        print_warning "Esto puede tomar varios minutos..."
        docker-compose build
        docker-compose up -d
    else
        print_header "Reconstruyendo servicio: $1"
        docker-compose build "$1"
        docker-compose up -d "$1"
    fi
    print_status "Reconstrucción completada."
}

# Función para reiniciar servicios
restart() {
    if [ -z "$1" ]; then
        print_header "Reiniciando todos los servicios"
        docker-compose restart
    else
        print_header "Reiniciando servicio: $1"
        docker-compose restart "$1"
    fi
    print_status "Reinicio completado."
}

# Función para limpiar completamente
clean() {
    print_warning "Esto eliminará todos los contenedores, imágenes y volúmenes."
    read -p "¿Estás seguro? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        print_header "Limpiando todo"
        docker-compose down -v --rmi all
        docker system prune -f
        print_status "Limpieza completada."
    else
        print_status "Operación cancelada."
    fi
}

# Función para mostrar ayuda
help() {
    echo "Into the Unknown - Script de Utilidades"
    echo ""
    echo "Uso: $0 [comando] [parámetros]"
    echo ""
    echo "Comandos disponibles:"
    echo "  start           Inicia todos los servicios"
    echo "  stop            Para todos los servicios"
    echo "  restart [svc]   Reinicia todos los servicios o uno específico"
    echo "  status          Muestra el estado de los servicios"
    echo "  logs [svc]      Muestra logs de todos los servicios o uno específico"
    echo "  rebuild [svc]   Reconstruye todos los servicios o uno específico"
    echo "  clean           Limpia completamente todo (¡CUIDADO!)"
    echo "  help            Muestra esta ayuda"
    echo ""
    echo "Servicios disponibles: discovery, pioneer, challenger, db"
    echo ""
    echo "Ejemplos:"
    echo "  $0 start"
    echo "  $0 logs discovery"
    echo "  $0 rebuild pioneer"
    echo "  $0 restart challenger"
}

# Procesar comandos
case "$1" in
    start)
        start
        ;;
    stop)
        stop
        ;;
    restart)
        restart "$2"
        ;;
    status)
        status
        ;;
    logs)
        logs "$2"
        ;;
    rebuild)
        rebuild "$2"
        ;;
    clean)
        clean
        ;;
    help|--help|-h)
        help
        ;;
    *)
        print_error "Comando desconocido: $1"
        echo ""
        help
        exit 1
        ;;
esac
