# EIR: PoC con Docker Compose

Demostración con datos sintéticos: React/Vite → Nginx → FastAPI → SQLite. Nginx sirve el frontend y hace proxy de `/api/` al backend en la red interna de Compose. Apollo es determinista: devuelve una respuesta fija y no utiliza un modelo ni realiza análisis clínico. SQLite se conserva en el volumen Docker `astra-data`. Solo Nginx publica un puerto; la base de datos y el backend no se publican.

## Ejecución local

Requisitos: Docker con Compose, acceso al daemon y acceso a registros de imágenes y paquetes durante la construcción. Desde este directorio:

```bash
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Abrir http://127.0.0.1:8080. La dirección y el puerto pueden modificarse en `.env`. Comprobar la API a través de Nginx:

```bash
curl -fsS http://127.0.0.1:8080/api/health
curl -fsS http://127.0.0.1:8080/api/astronauts/demo
curl -fsS -X POST http://127.0.0.1:8080/api/apollo/chat -H 'Content-Type: application/json' -d '{"message":"Hola"}'
```

`docker compose restart` reinicia los servicios sin eliminar los datos; `docker compose down` detiene y elimina los contenedores, pero conserva el volumen. No usar `down -v` si se quieren conservar los datos.

## EC2 existente

No se requieren servicios administrados adicionales. Antes de operar, verificar la cuenta y región autorizadas, el estado de la instancia, CPU, RAM, espacio en disco, arquitectura de CPU, acceso y costo de la instancia existente. Estas consultas son de solo lectura (requieren AWS CLI, credenciales y permisos adecuados):

```bash
aws sts get-caller-identity
aws ec2 describe-instances --query 'Reservations[].Instances[].[InstanceId,State.Name,InstanceType,PublicIpAddress,PrivateIpAddress,PlatformDetails]'
aws ssm describe-instance-information --query 'InstanceInformationList[].[InstanceId,PingStatus,PlatformName]'
```

Verificar el tipo de instancia en la documentación de AWS para conocer sus recursos; dentro de la instancia, usar `nproc`, `free -h`, `df -h` y, si corresponde, `nvidia-smi`. SSM necesita agente, rol y conectividad configurados; aparecer en el inventario no garantiza autorización para iniciar una sesión. Alternativamente, usar SSH con un usuario y clave autorizados. No instalar ni cambiar configuraciones de la instancia sin autorización.

Con acceso autorizado, Docker y Compose operativos, copiar este directorio a la instancia mediante el mecanismo permitido y ejecutar los comandos locales anteriores allí. La opción preferida conserva `ASTRA_BIND_ADDRESS=127.0.0.1` y utiliza un túnel SSH desde el equipo del usuario:

```bash
ssh -i /ruta/a/clave -L 8080:127.0.0.1:8080 usuario@host-ec2
```

Después abrir http://127.0.0.1:8080 en el equipo del usuario. El acceso SSH debe estar autorizado y restringido a la IP correspondiente. Como alternativa, se puede usar reenvío de puertos SSM si está habilitado y autorizado.

Si se requiere acceso directo público, definir `ASTRA_BIND_ADDRESS=0.0.0.0` y limitar el puerto elegido en el Security Group a la IP pública autorizada con CIDR `/32` antes de exponerlo. Cualquier cambio al Security Group existente requiere aprobación explícita. No abrir el daemon Docker ni SQLite. HTTP no cifra el tráfico: para cualquier despliegue más allá de esta prueba se necesita HTTPS y controles de acceso apropiados. No introducir datos reales ni secretos.

La ejecución de una EC2 existente puede generar cargos de cómputo, almacenamiento EBS, direcciones IPv4 públicas y transferencia de datos según su configuración; esta PoC no crea recursos AWS. Consultar precios y uso de la cuenta antes de operar.

## Traslado a una LAN sin Internet

Preparar previamente en una máquina conectada las imágenes ya construidas y transferirlas al servidor (`docker save` / `docker load`), junto con Compose, la configuración y cualquier actualización necesaria. Usar etiquetas de imágenes disponibles localmente en Compose y arrancar sin reconstruir ni descargar. Configurar una dirección LAN y puerto adecuados, acceso de red limitado y DNS o dirección IP interna. Preparar copias de seguridad del volumen SQLite y un mecanismo de actualización, además de HTTPS y controles de acceso según el uso. Comprobar la operación con Internet realmente desconectado: Docker por sí solo no demuestra funcionamiento offline. La construcción actual necesita descargar imágenes base y dependencias.

## Validación experimental de Ollama

La aplicación conserva `APOLLO_PROVIDER=deterministic` por defecto. Compose incluye Ollama sin publicar el puerto 11434, con un volumen persistente `ollama-models`, una inferencia concurrente y una comprobación de disponibilidad. No se habilita GPU. Ollama se ejecuta en la red interna de Compose; los otros contenedores de esa red pueden acceder a él. El frontend informa el proveedor configurado y el utilizado para cada respuesta. En caso de error de Ollama, la API responde 503 y la interfaz permite solicitar explícitamente una respuesta determinista.

Antes de descargar imágenes o modelos en EC2, verificar instancia, memoria disponible, espacio, arquitectura, carga actual, permisos y costo de almacenamiento. No hay garantía de que un modelo funcione en una instancia determinada. No continuar con modelos mayores si la máquina presenta presión de memoria, uso excesivo de swap o inestabilidad. Solo utilizar datos sintéticos. Para preparar la prueba:

```bash
docker compose config
docker compose up -d --build
docker compose ps
docker compose exec ollama ollama --version
docker image inspect ollama/ollama:latest --format '{{index .RepoDigests 0}}'
docker compose exec ollama ollama pull qwen3:0.6b
docker compose exec ollama ollama list
```

En `.env`, seleccionar `APOLLO_PROVIDER=ollama` y `OLLAMA_MODEL=qwen3:0.6b`; luego ejecutar `docker compose up -d backend`. Para regresar al modo anterior, configurar `APOLLO_PROVIDER=deterministic` y recrear el backend del mismo modo. El endpoint original también acepta opcionalmente `"provider":"deterministic"` para solicitar el modo predefinido sin cambiar el proveedor global. `GET /api/apollo/config` muestra la configuración. Las respuestas conservan los campos `assistant`, `mode` y `reply`. El endpoint procesa cada solicitud de manera independiente y no conserva historial conversacional.

Para cada modelo, registrar su versión/digest con `docker compose exec ollama ollama list` y `docker compose exec ollama ollama show qwen3:0.6b`. Ejecutar la evaluación reproducible desde la raíz:

```bash
python3 scripts/evaluate_ollama.py qwen3:0.6b --output /tmp/eir-qwen-06b.json
```

El archivo incluye las respuestas, tiempo total observado, tiempo de carga y generación reportados por Ollama, tokens por segundo cuando estén disponibles, muestras CPU/RAM de `docker stats` y errores. La primera solicitud puede incluir carga en frío; las siguientes son pruebas con el modelo ya cargado y los tiempos dependen de la configuración. La prueba multivuelta envía una conversación sintética completa directamente a Ollama; no demuestra que el endpoint de Apollo conserve historial. VRAM no se mide en el script: si hay GPU, observarla por separado con `nvidia-smi` y registrar límites y muestras. Revisar manualmente cada respuesta frente a las restricciones y anotar el resultado cualitativo por separado; estas pruebas no demuestran seguridad ni precisión clínica.

Solo tras revisar la estabilidad de `0.6b`, descargar y evaluar `qwen3:1.7b`; proceder a `qwen3:4b` únicamente si los recursos y la estabilidad lo permiten. Repetir los comandos sustituyendo el nombre del modelo y usando un archivo de salida diferente. La etiqueta `latest` de la imagen puede cambiar: registrar el digest y la versión realmente probados. Para una LAN sin Internet, además de los componentes ya descritos, transferir la imagen de Ollama y el volumen de modelos previamente descargados y comprobar su disponibilidad sin conexión. No se ha demostrado la viabilidad offline ni la calidad del modelo con esta configuración.
