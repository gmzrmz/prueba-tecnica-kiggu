# Notes API · Prueba técnica DevOps

API REST pequeña para gestionar notas, junto con el entorno para correrla en local, validarla en CI y desplegarla en una VM Linux con rollback automático. Guarda los datos en PostgreSQL y usa Redis para el rate limiting.

La parte 1 de la prueba está en [CONOCIMIENTO.md](CONOCIMIENTO.md).

## Cómo levantar y probar

Necesitas Docker con el comando `docker compose`. Para correr las pruebas, también Python 3.13.

```bash
# Levanta API, PostgreSQL y Redis. Devuelve el control cuando los tres están sanos.
docker compose up --build --wait
```

- API: http://127.0.0.1:8000/notes
- Swagger UI: http://127.0.0.1:8000/docs
- Estado de las dependencias: http://127.0.0.1:8000/health

| Método y ruta | Qué hace | Respuestas |
|---|---|---|
| `POST /notes` | Crea una nota | 201, 422, 429, 503 |
| `GET /notes?limit=&offset=` | Lista notas (máximo 100 por página) | 200, 422, 429, 503 |
| `GET /notes/{id}` | Lee una nota | 200, 404, 429, 503 |
| `PUT /notes/{id}` | Reemplaza una nota | 200, 404, 422, 429, 503 |
| `DELETE /notes/{id}` | Borra una nota | 204, 404, 429, 503 |
| `GET /health` | Estado de PostgreSQL y Redis | 200, 503 |

En las rutas de notas, 503 significa que PostgreSQL no responde.

```bash
# Pruebas, con el entorno levantado (en un entorno virtual de Python)
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-dev.txt
pytest

# Apagar y borrar los datos
docker compose down -v
```

No hay pasos manuales: la API crea el esquema de la base de datos al arrancar.

### Simular un despliegue con rollback, sin VM

`deploy.sh` usa el archivo de compose que indique `COMPOSE_FILE` (por defecto `compose.prod.yaml`). En local se apunta a `compose.yaml`:

```bash
export COMPOSE_FILE=compose.yaml
IMG=ghcr.io/gmzrmz/prueba-tecnica-kiggu

# 1. Una versión sana: se despliega y queda activa
TAG=v1 docker compose build api
./deploy.sh v1

# 2. Una versión rota a propósito: arranca, pero /health nunca responde
printf 'FROM %s:v1\nCMD ["sleep", "infinity"]\n' $IMG | docker build -t $IMG:roto -
./deploy.sh roto   # el healthcheck la marca unhealthy, vuelve a v1 y termina en error

# 3. Limpiar
docker compose down -v
unset COMPOSE_FILE
```

### Desplegar en una VM

Preparación, una sola vez:

1. En la VM: Docker instalado, una carpeta `~/notes` con el `.env` (a partir de `.env.example`, con permisos 600) y el certificado de la CA del PostgreSQL gestionado en `~/notes/certs/ca.pem`.
2. En GitHub, en los secretos del repositorio: `VM_HOST` (`usuario@ip`), `VM_SSH_KEY` (la llave privada) y `VM_KNOWN_HOSTS` (la salida de `ssh-keyscan <ip>`). En las variables: `DEPLOY_ENABLED=true`.

Desde ahí, cada merge a `main` que pase las pruebas se despliega solo. A mano: `./deploy.sh <SHA>` dentro de `~/notes`.

## Arquitectura

Los diagramas C4 están en [docs/arquitectura/workspace.dsl](docs/arquitectura/workspace.dsl), escritos con Structurizr DSL. Para verlos, pega el archivo en [playground.structurizr.com](https://playground.structurizr.com) y navega entre niveles con doble clic. Son seis vistas: contexto, contenedores, componentes, despliegue local, despliegue en producción y una vista dinámica del despliegue con rollback.

```
 Local y CI (compose.yaml)                 Producción (compose.prod.yaml, VM en GCP)
 ─────────────────────────                 ─────────────────────────────────────────
 [api] 127.0.0.1:8000                      [api] :80
   ├──▶ [postgres]  sin puerto publicado     ├──▶ [redis]  sin puerto publicado
   └──▶ [redis]     sin puerto publicado     └──TLS verify-full──▶ PostgreSQL gestionado
```

## Decisiones

Diseñé con cinco criterios: que sea fácil de entender, fácil de explicar, escalable, seguro y rápido. Además, hacer lo que pide el enunciado, ni más ni menos. Lo que quedó fuera está en [Qué faltó y cómo seguiría](#qué-faltó-y-cómo-seguiría).

### Elecciones principales

| Decisión | Por qué | Lo que descarté |
|---|---|---|
| Python + FastAPI, síncrono | Valida la entrada con Pydantic y genera OpenAPI y Swagger UI sin trabajo extra. Ya lo usé en un proyecto anterior. El código síncrono es más fácil de leer y probar, y a esta escala rinde igual. | Express, que exige armar la validación y la documentación a mano. Async, más complejo sin ganancia aquí. |
| SQL directo con psycopg | Son cinco consultas, y se ve exactamente qué llega a la base. | Un ORM: otra capa para algo tan pequeño. |
| Redis para rate limiting | Un contador en memoria falla con varias instancias ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 2). En Redis, el contador es compartido. | Redis como caché de lecturas: obliga a invalidar datos en cada `PUT` y `DELETE`. |
| Ventana fija por IP | Se explica en una línea. En el borde entre dos ventanas pueden pasar hasta el doble de peticiones, y aquí es aceptable. | Ventana deslizante: más precisa, pero más compleja. |
| Si Redis falla, la API deja pasar las peticiones | Un problema en Redis no tumba la API, y `/health` lo reporta. Prefiero disponibilidad a bloquear a todos. | Rechazar todo cuando Redis no responde. |
| Migraciones con un script propio de unas 25 líneas | Aplica en orden los `.sql` pendientes y anota cuáles aplicó. Vive en la misma imagen que la API, así que la versión del código y la del esquema siempre coinciden. | dbmate, que necesita una segunda imagen o un binario extra. Alembic, que genera plantillas que aquí no hacen falta. |
| La API migra al arrancar, con un candado | `pg_advisory_lock` deja migrar a una sola instancia a la vez; las demás esperan y encuentran todo aplicado. Es un contenedor menos. | Un contenedor `migrate` aparte. |
| Dos archivos de compose independientes | `compose.yaml` (local y CI) y `compose.prod.yaml` (VM). Cada uno se lee de arriba abajo, sin fusiones implícitas. | Un archivo base con overrides. |
| Imágenes en GHCR, con el SHA del commit como tag | Se construye una vez y se despliega exactamente lo que probó CI. Siempre se sabe a qué versión volver. | Construir en la VM. Usar el tag `latest`. |

### Construir (Dockerfile)

| Decisión | Por qué |
|---|---|
| `python:3.13-slim`, una sola etapa | La misma versión que uso en local. No hay nada que compilar, así que no hacen falta más etapas. |
| `psycopg[binary]` | Trae incluida la librería cliente de PostgreSQL, así que no se instala nada del sistema. |
| Copiar `requirements.txt` antes que el código | Si solo cambió el código, Docker reutiliza la capa de dependencias y el build tarda segundos. |
| El Dockerfile copia solo `app/` y `migrations/` | Nada más del repositorio, como un `.env`, puede terminar dentro de la imagen. El `.dockerignore` además evita enviar `.git` y `.env` al build. |
| Versiones exactas de las dependencias directas en `requirements.txt` | Se sabe exactamente qué versión de cada paquete usa el código. Las dependencias de esas dependencias no están fijadas (ver [Qué faltó y cómo seguiría](#qué-faltó-y-cómo-seguiría)). |
| Usuario sin privilegios de root | Si alguien explota la API, no es root dentro del contenedor. |

### Configurar

| Decisión | Por qué |
|---|---|
| Tres variables: `DATABASE_URL`, `REDIS_URL` y `RATE_LIMIT_PER_MINUTE` | Es todo lo que cambia entre entornos. El código es el mismo en local y en producción. |
| En local, valores de desarrollo escritos en `compose.yaml` | Son contraseñas desechables de desarrollo, no secretos. Así el entorno se levanta con un comando, sin copiar ningún `.env`. |
| En producción, un `.env` en la VM con permisos 600; en el repo solo `.env.example` | Los secretos nunca tocan Git. En un GCP real los leería de Secret Manager con la cuenta de servicio de la VM ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 7). |
| `sslmode=verify-full` y el certificado de la CA montado de solo lectura | Valida el certificado y el nombre del servidor, no solo que la conexión vaya cifrada ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 6). |

### Arrancar

| Decisión | Por qué |
|---|---|
| Healthcheck de Docker en los tres servicios: `/health` en el `Dockerfile` de la API; `pg_isready` y `redis-cli ping` en `compose.yaml` | Una sola definición de "sano", que usan compose, CI y el despliegue. Al estar en el `Dockerfile`, el de la API viaja con la imagen y vale igual en local y en producción. |
| La API espera a que sus dependencias estén sanas (`depends_on`): PostgreSQL y Redis en local; solo Redis en producción | No intenta migrar antes de tiempo. En producción, PostgreSQL es externo: si no responde al arrancar, la migración falla, el contenedor termina y `restart: unless-stopped` lo vuelve a intentar hasta que responda. |
| Al arrancar, primero el script de migraciones y después `exec uvicorn` | Migra y después atiende. Con `exec`, uvicorn recibe la señal de apagado y se detiene limpio. |
| Volumen con nombre para PostgreSQL en local | Los datos sobreviven a los reinicios; `docker compose down -v` empieza de cero. |
| En producción, `restart: unless-stopped` | Si la VM se reinicia, los servicios vuelven solos. |
| En producción, rotación de logs (3 archivos de 10 MB) | Evita que los logs llenen el disco ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 8). |

### Atender peticiones

| Decisión | Por qué |
|---|---|
| Pool de conexiones a PostgreSQL (máximo 5 por proceso) | Reutiliza conexiones abiertas en vez de abrir una por petición. |
| Timeouts cortos: 2 s para PostgreSQL y 1 s para Redis | Si una dependencia se cuelga, la API responde con un error rápido en vez de quedarse esperando. Sin esto, `/health` y el fail-open no servirían. |
| Rate limit con la clave `rl:<ip>:<minuto>`, `INCR` y `EXPIRE` en una transacción, y 429 al superar el límite | Cada minuto usa una clave nueva, así que el contador se reinicia solo. Aunque una expiración fallara, la IP no queda bloqueada. |
| `/health` sin rate limit | El despliegue lo consulta varias veces seguidas, y un 429 provocaría un rollback por error. |
| `/health` hace `SELECT 1` y `PING`, y responde 200 o 503 | Refleja el estado real de las dependencias. |
| Si PostgreSQL no responde, las rutas de notas devuelven 503 "Base de datos no disponible" | Un error claro en vez de un 500 genérico. |
| SQL con parámetros, longitudes máximas y un máximo de 100 notas por listado | Sin inyección SQL ni respuestas gigantes. |

### Exponer

| Decisión | Por qué |
|---|---|
| En local, solo la API publica puerto, en `127.0.0.1:8000` | PostgreSQL y Redis solo se ven dentro de la red de Docker, y la API no queda visible para la red local. |
| En producción, el firewall abre el 80 al público y el 22 solo para desplegar, con llave SSH y sin contraseña | Es lo mínimo para servir y desplegar. Es un riesgo aceptado: no se puede restringir el 22 a las IPs de GitHub Actions, porque son miles y cambian. La solución es IAP (ver [Qué faltó y cómo seguiría](#qué-faltó-y-cómo-seguiría)). |
| El firewall es el de GCP, no `ufw` | Docker se salta las reglas de `ufw`: un puerto publicado por error quedaría abierto igual. |
| El PostgreSQL gestionado solo acepta la IP de la VM, y con TLS | La exposición mínima también aplica a la base de datos. |
| Redis sin puerto publicado | No se puede alcanzar desde fuera de la VM. |

### Probar

| Decisión | Por qué |
|---|---|
| pytest y httpx contra la API levantada | Las pruebas hacen peticiones HTTP reales, como un cliente, contra PostgreSQL y Redis reales. |
| Las pruebas que alteran el entorno lo restauran con fixtures | Las pruebas que apagan Redis o PostgreSQL (con `docker compose stop`) los vuelven a levantar al terminar, aunque fallen. Antes de cada prueba se vacían los contadores del rate limit. Así cada prueba funciona en cualquier orden. |
| La prueba del 429 hace peticiones hasta recibir un 429 | Tolera que el minuto cambie en medio de la prueba, así que no falla al azar. |

### Integración continua

| Decisión | Por qué |
|---|---|
| Un solo workflow con un solo job | En un PR construye la imagen, levanta el entorno y corre las pruebas. En `main`, además publica la imagen y despliega. Se lee de arriba abajo. |
| Si algo falla, el job muestra los logs de los contenedores | Se ve por qué falló sin tener que reproducirlo en local ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 4). |
| `compose.yaml` nombra la imagen `ghcr.io/gmzrmz/prueba-tecnica-kiggu:${TAG}` | CI construye, prueba y publica la misma imagen con `docker compose push`. |
| Protección de la rama `main`: el job tiene que pasar antes de integrar un PR | Sin esto, CI avisa pero no impide el merge. Es una configuración del repositorio, no código. |
| Permisos del workflow: `contents: read` y `packages: write` | Tiene solo los permisos que necesita. |
| Paquete de GHCR público | La VM descarga la imagen sin necesitar otra credencial. |

### Desplegar y volver atrás

| Decisión | Por qué |
|---|---|
| El job copia `compose.prod.yaml` y `deploy.sh` por `scp` y ejecuta `deploy.sh <SHA>` por `ssh` | La VM no necesita git ni el repositorio. |
| La host key de la VM está fijada en un secreto (`VM_KNOWN_HOSTS`) | Evita un ataque man-in-the-middle; es la misma idea que `verify-full`. |
| Las ejecuciones de CI en `main` van de una en una (`concurrency`) | Si se integran dos PRs seguidos, sus despliegues no se pisan en la VM. |
| El despliegue solo corre si `vars.DEPLOY_ENABLED` es `true` | Sin una VM configurada, el paso se salta. |
| `deploy.sh` usa el compose de `COMPOSE_FILE`, por defecto `compose.prod.yaml` | El mismo script se puede probar en local, sin VM. |
| `deploy.sh` usa `docker compose up --wait` | Levanta la versión nueva y espera hasta 60 s a que el healthcheck diga que está sana. Si no lo está, vuelve a levantar la versión anterior, que anota en el archivo `.deployed-tag`. Son unas 15 líneas. |
| Si hubo rollback, el job termina en error | El rollback protege el servicio, pero CI queda en rojo para que el fallo no pase inadvertido. |
| Migraciones expand-contract | El rollback devuelve la imagen anterior, pero no deshace el esquema. Por eso cada migración tiene que ser compatible con la versión anterior ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 5). |
| Corte de unos segundos al reemplazar el contenedor | Evitarlo requiere un balanceador (ver [Qué faltó y cómo seguiría](#qué-faltó-y-cómo-seguiría)). |

### Escalar

| Decisión | Por qué |
|---|---|
| La API no guarda estado | Los datos están en PostgreSQL y los contadores en Redis, así que se pueden correr varias instancias sin cambiar código. |
| `WEB_CONCURRENCY` en el `.env` de la VM | uvicorn lo lee solo: más procesos por VM cambiando solo la configuración. |
| Más VMs detrás de un balanceador | Las conexiones a PostgreSQL son instancias × procesos × 5, y deben quedar por debajo del límite del servicio gestionado. |
| Con varias VMs, Redis tiene que ser compartido | Si cada VM tuviera su propio Redis, cada una contaría por separado ([CONOCIMIENTO.md](CONOCIMIENTO.md), pregunta 2). |

## Objetivo 10 · Entre nubes

- **Que solo mi VM llegue:** la VM de GCP tiene una IP externa estática, que también es su IP de salida. El security group de la EC2 abre el 8091 solo a esa IP (`/32`).
- **Proteger la comunicación:** HTTPS en el 8091. La API valida el certificado y el nombre del servidor, como `verify-full` en PostgreSQL. Si el servicio lo permite, mTLS.
- **Proteger la credencial:** el token vive en GCP Secret Manager. La VM lo lee con su cuenta de servicio, que solo puede leer ese secreto, y lo recibe como variable de entorno. Nunca está en Git ni en la imagen.
- **Verificar:** desde la VM, `nc -vz <ec2> 8091` conecta, y `curl -v https://<ec2>:8091/<ruta>` con el token responde 200 con el certificado validado. Desde otra IP, `nc` se queda esperando; sin token, el servicio responde 401.

## Qué faltó y cómo seguiría

- **HTTPS público:** Caddy delante de la API, con certificados automáticos. El rate limit tendría que tomar la IP del cliente de la cabecera que agrega el proxy, y confiar en ella solo si viene del proxy.
- **SSH sin el puerto 22 abierto:** desplegar a través de IAP de GCP.
- **Secretos en Secret Manager**, en vez de un `.env` en la VM.
- **Despliegue sin cortes:** dos instancias detrás de un balanceador, pasando el tráfico a la nueva solo cuando esté sana (blue-green).
- **Lock file completo** de dependencias (por ejemplo con `pip-tools`), para que también las indirectas tengan versión fija y el build sea idéntico hoy y en un mes.
- **Escaneo de vulnerabilidades** de la imagen en CI, por ejemplo con Trivy.
- **Limpieza de imágenes viejas** en la VM, conservando la anterior para el rollback.
- **Métricas y alertas** de CPU, RAM, disco y `/health`.
- **Redis gestionado**, cuando haya más de una VM.
- **Infraestructura como código:** Terraform para la VM, el firewall y el PostgreSQL gestionado, para que la infraestructura también sea repetible.
- **VPN entre GCP y AWS** (objetivo 10): el tráfico iría por IPs privadas, sin exponer el 8091 a internet.

## Herramientas

- Python 3.13, FastAPI, uvicorn, psycopg 3, redis-py, pytest y httpx.
- Docker y Docker Compose, con las imágenes oficiales de PostgreSQL 17 y Redis 8.
- GitHub Actions y GitHub Container Registry (GHCR).
- Structurizr DSL para los diagramas C4.
- Claude (Claude Code), DeepSeek y Grok como asistentes; ver [Uso de IA](#uso-de-ia).

## Uso de IA

Para la parte 1, ver la sección "Uso de IA" de [CONOCIMIENTO.md](CONOCIMIENTO.md).

- **Herramientas:** Claude (Claude Code), DeepSeek y Grok.
- **Cómo las usé:** el diseño salió de una discusión constante. Con Claude iteré la arquitectura, y el diseño de cada ronda lo llevé a DeepSeek y Grok para recibir retroalimentación. Después decidí qué críticas aplicar y cuáles descartar.
- **Qué generó la IA:**
  - Los diagramas C4 en Structurizr DSL (Claude).
  - El registro de decisiones de este README: Claude propuso alternativas y redactó las justificaciones a lo largo de varias iteraciones.
  - Revisiones críticas del diseño (DeepSeek y Grok).
- **Qué hice yo:**
  - Definí el enfoque (C4, de lo general a lo detallado) y los criterios del diseño: fácil de entender y de explicar, escalable, seguro, rápido, y cumplir lo pedido sin agregar más.
  - Dirigí las iteraciones, contrasté el diseño entre los tres asistentes y aprobé las decisiones finales.
- **Un error que introdujo la IA:** el primer diseño del rate limiter usaba `INCR` y `EXPIRE` sin garantizar que se ejecutaran juntos. Si la API se caía entre los dos comandos, el contador quedaba sin expiración y esa IP quedaba bloqueada para siempre. Lo detectó una de las revisiones externas, y se corrigió con una clave por IP y por minuto y enviando los dos comandos en una transacción.