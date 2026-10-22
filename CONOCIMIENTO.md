# Prueba de conocimiento

## 1. Linux: servicio systemd que no arranca tras reiniciar

Primero veo el estado del servicio y el error que muestra, y después reviso sus logs desde el último arranque. También verifico que esté habilitado para iniciar con el sistema, porque a veces funciona a mano pero nunca se habilitó.

```bash
systemctl status servicio
journalctl -u servicio -b
systemctl is-enabled servicio
```

## 2. Linux: contador en memoria con PM2 en modo cluster

Cada instancia es un proceso aparte con su propia memoria, así que cada una lleva su propio contador. Si el límite es 100 peticiones, en la práctica se pueden hacer hasta 200, porque las peticiones se reparten entre las dos. Además el contador se pierde si una instancia se reinicia. La solución es guardarlo en algo compartido, como Redis.

## 3. Redes: curl falla, ¿DNS, red/firewall o TLS?

Lo reviso paso a paso. Si `dig` no devuelve una IP, el problema es DNS. Si resuelve, pruebo si llego al puerto con `nc`; si se queda esperando, suele ser un firewall. Si conecta, uso `curl -v` para ver si el error es del certificado TLS.

```bash
dig api.ejemplo.com
nc -vz api.ejemplo.com 443
curl -v https://api.ejemplo.com/health
```

## 4. Contenedores: contenedor que se reinicia en bucle

Reviso los logs del contenedor para ver el error antes de que se cierre, y con `docker inspect` veo el código de salida y si se quedó sin memoria. Las causas más comunes son una variable de entorno faltante, una dependencia caída como la base de datos, o falta de memoria.

```bash
docker logs contenedor
docker inspect contenedor
```

## 5. Bases de datos: migración que elimina una columna en uso

El riesgo es que la versión actual sigue corriendo durante el despliegue y falla al buscar la columna. Además, si algo sale mal, no se puede volver atrás porque la columna ya no existe. Lo hago en dos pasos: primero despliego una versión que ya no usa la columna, y después, en otro despliegue, la elimino. Antes hago un backup.

## 6. Bases de datos: `sslmode=require` vs `verify-full`

Con `require` la conexión va cifrada, pero no se comprueba que el servidor sea realmente la base de datos. Con `verify-full` sí se verifica el certificado y que el nombre del servidor coincida. Desactivar la verificación en toda la aplicación permite que alguien se haga pasar por el servidor y robe credenciales o datos (ataque man-in-the-middle).

## 7. Nube: access keys de AWS en un `.env`

En lugar de guardar claves, le asigno a la EC2 un rol de IAM con solo los permisos que necesita. Así el script obtiene credenciales temporales automáticamente y no hay claves guardadas en el servidor. En GCP es lo mismo: le asigno una cuenta de servicio a la VM. Otros secretos, como contraseñas, irían en Secrets Manager (AWS) o Secret Manager (GCP).

## 8. Tus proyectos

**Matrix Crossing Benchmark:** Dejé el state de Terraform local y puse los `.tfstate` y `terraform.tfvars` en el `.gitignore`. Las credenciales eran temporales de AWS Academy: el script de inicio las pide y las guarda en `~/.aws/credentials`, así que no quedan en el código y expiran con el lab. Las EC2 no llevan claves, usan el `LabInstanceProfile`. Con más tiempo, movería el state a un bucket de S3 con bloqueo.

**CloudSense:** Hoy mide CPU, RAM y red con datos simulados. En una VM real agregaría el uso de disco, porque un disco lleno hace fallar los servicios. Pondría alertas cuando la CPU o la RAM pasen del 85% durante varios minutos, cuando el disco pase del 85% y cuando la VM deje de enviar métricas, porque puede estar caída.

## Uso de IA

- **Herramienta:** Claude (Claude Code).
- **Qué hice yo:** el razonamiento, los pasos y los comandos.
- **Qué hizo la IA:** darles formato (títulos, bloques de código) y dejar la redacción más clara.
