workspace "Notes API" "Prueba técnica DevOps: API de notas y su entorno de ejecución, validación y despliegue." {

    model {
        # Cada nivel declara sus propias relaciones, sin deducirlas de los componentes.
        !impliedRelationships false

        # Personas
        cliente = person "Cliente de la API" "Persona o sistema que gestiona notas por HTTP, incluido Swagger UI."
        dev = person "Desarrollador" "Escribe el código y lo integra mediante pull requests."

        # Sistema
        notes = softwareSystem "Notes API" "Permite crear, listar, leer, actualizar y borrar notas." {
            api = container "API" "Expone el CRUD de notas, /health y /docs. Al arrancar aplica las migraciones pendientes. No guarda estado: la configuración llega por variables de entorno y los secretos de producción viven en la VM, nunca en Git." "Python, FastAPI, uvicorn" {
                notesRouter = component "Rutas de notas" "Endpoints del CRUD. Valida la entrada con Pydantic y traduce errores a códigos HTTP coherentes (201, 404, 422)." "FastAPI APIRouter"
                rateLimiter = component "Rate limiter" "Limita peticiones por IP con ventana fija y responde 429 al superar el límite. No se aplica a /health. Si Redis falla o tarda más de 1 s, deja pasar la petición." "Dependencia de FastAPI"
                repo = component "Repositorio de notas" "Consultas SQL con parámetros sobre un pool de conexiones, con timeout de 2 s." "psycopg"
                healthRouter = component "Ruta de salud" "Comprueba Postgres y Redis con timeouts cortos. Responde 200 si ambos están bien y 503 si alguno falla. Docker la usa como healthcheck." "FastAPI APIRouter"
                migraciones = component "Migraciones" "Script que corre antes de uvicorn: aplica en orden los .sql pendientes y anota cuáles aplicó. Un candado evita que dos instancias migren a la vez." "Python, psycopg"
            }
            db = container "Base de datos" "Guarda las notas y el registro de migraciones aplicadas." "PostgreSQL" "Database"
            cache = container "Redis" "Guarda los contadores del rate limiting. Si se pierden, solo se reinician los límites." "Redis" "Database"
        }

        # Sistemas externos
        github = softwareSystem "GitHub" "Repositorio, Actions (CI/CD) y Container Registry: imágenes versionadas por el SHA del commit." "External"
        awsService = softwareSystem "Servicio en EC2" "Servicio externo en AWS, puerto 8091 (objetivo 10, diseñado en el README)." "External"

        # Relaciones, nivel 1: contexto
        cliente -> notes "Gestiona notas" "HTTP/JSON"
        dev -> github "Sube código y abre pull requests" "git"
        github -> notes "En cada PR construye y prueba; en main publica la imagen y despliega" "GitHub Actions; SSH"
        notes -> awsService "Consume (no implementado)" "HTTPS :8091"

        # Relaciones, nivel 2: contenedores
        cliente -> api "Gestiona notas" "HTTP/JSON"
        github -> api "Despliega con deploy.sh, que espera a que la API quede sana" "SSH"
        api -> db "Aplica migraciones al arrancar, lee y escribe notas, comprueba salud" "SQL; TLS verify-full en producción"
        api -> cache "Cuenta peticiones por IP, comprueba salud" "Redis"
        api -> awsService "Consume (no implementado)" "HTTPS :8091"

        # Relaciones, nivel 3: componentes de la API
        cliente -> notesRouter "Envía peticiones" "HTTP/JSON"
        github -> healthRouter "deploy.sh espera a que /health quede sano (healthcheck de Docker)" "HTTP a localhost"
        notesRouter -> rateLimiter "Comprueba el límite de la IP" "Llamada en proceso"
        notesRouter -> repo "Lee y escribe notas" "Llamada en proceso"
        rateLimiter -> cache "INCR + EXPIRE en una transacción, con una clave por IP y ventana" "Redis"
        repo -> db "Consultas SQL con parámetros" "SQL; TLS verify-full en producción"
        healthRouter -> db "SELECT 1" "SQL; TLS verify-full en producción"
        healthRouter -> cache "PING" "Redis"
        migraciones -> db "Aplica los .sql pendientes, con pg_advisory_lock" "SQL; TLS verify-full en producción"

        # Entornos de despliegue
        local = deploymentEnvironment "Local" {
            deploymentNode "Máquina del desarrollador o runner de CI" "Cualquier equipo con Docker. Un comando levanta todo; en CI, las pruebas corren contra este mismo entorno." "Docker" {
                deploymentNode "Docker Compose" "Healthcheck en los tres servicios. Red interna: solo la API publica puerto, en 127.0.0.1:8000." "compose.yaml" {
                    containerInstance api
                    containerInstance db
                    containerInstance cache
                }
            }
        }

        produccion = deploymentEnvironment "Producción" {
            deploymentNode "Google Cloud" "Donde corre la API en producción." "GCP" {
                deploymentNode "VM Linux" "Firewall de GCP: puerto 80 abierto al público y 22 solo para el despliegue, con llave SSH. IP externa estática." "Compute Engine" {
                    deploymentNode "Docker Compose" "Misma imagen que probó CI; solo cambia la configuración. Healthchecks, reinicio automático y rotación de logs. Solo la API publica puerto, en el 80." "compose.prod.yaml" {
                        containerInstance api
                        containerInstance cache
                    }
                }
                deploymentNode "PostgreSQL gestionado" "Fuera de la VM. Solo acepta conexiones desde la IP de la VM y con TLS; los clientes validan el certificado y el nombre del servidor (verify-full)." "Servicio gestionado, p. ej. Cloud SQL" {
                    containerInstance db
                }
            }
            deploymentNode "Amazon Web Services" "Nube del servicio externo que consume la API." "AWS" {
                deploymentNode "EC2" "Security group: puerto 8091 abierto solo a la IP estática de la VM de GCP." "Amazon EC2" {
                    softwareSystemInstance awsService
                }
            }
        }
    }

    configuration {
        scope softwaresystem
    }

    views {
        # Muestra las vistas en el orden en que están definidas: de lo general a lo detallado.
        properties {
            "structurizr.sort" "created"
        }

        systemContext notes "Contexto" "Nivel 1: quién usa el sistema y con qué sistemas externos se relaciona." {
            include * dev
            autolayout lr
        }

        container notes "Contenedores" "Nivel 2: los procesos que forman el sistema y cómo se comunican." {
            include *
            autolayout lr
        }

        component api "Componentes" "Nivel 3: las piezas internas de la API." {
            include *
            autolayout lr
        }

        deployment * local "DespliegueLocal" "Dónde corre cada contenedor en local y en CI." {
            include *
            autolayout lr
        }

        deployment * produccion "DespliegueProduccion" "Dónde corre cada contenedor en producción." {
            include *
            autolayout lr
        }

        dynamic notes "DespliegueRollback" "Cómo se despliega una versión y cómo se vuelve atrás si no queda sana." {
            github -> api "Ejecuta deploy.sh por SSH: levanta la imagen nueva, identificada por el SHA del commit"
            api -> db "Al arrancar, aplica las migraciones pendientes (expand-contract, compatibles con la versión anterior)"
            github -> api "docker compose up --wait: espera hasta 60 s a que el healthcheck (/health) quede sano"
            github -> api "Si no quedó sana: levanta la imagen anterior, espera que quede sana y termina en error"
            autolayout lr
        }

        styles {
            element "Element" {
                color #ffffff
            }
            element "Person" {
                shape Person
                background #08427b
            }
            element "Software System" {
                background #1168bd
            }
            element "External" {
                background #8a8a8a
            }
            element "Container" {
                background #438dd5
            }
            element "Component" {
                background #85bbf0
                color #000000
            }
            element "Database" {
                shape Cylinder
            }
            element "Deployment Node" {
                background #ffffff
                color #000000
            }
        }
    }
}
