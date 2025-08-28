
# LCC-OT — Auditoría de Seguridad (agosto 2025)

Este informe resume hallazgos de seguridad y mejoras recomendadas tras revisar el repositorio **lcc-ot** tal como fue enviado (.zip).
Incluye referencias a archivos y números de línea.


## Resumen Ejecutivo

- **Gravedad Alta**:  
  1) **Controles de rol inconsistentes** entre grupos y campo `user_type` → posibles bypass de permisos para técnicos.  
  2) **Servidor de desarrollo (`runserver`) en compose** para servir producción.

- **Gravedad Media**:  
  4) **Subida de adjuntos sin validación** (extensiones/tamaño/AV).  
  5) **API DRF sin *throttling*/paginación explícita**.  
  6) **Cookies/headers de seguridad no definidos** en settings por defecto (recomendación para prod).  
  7) **Credenciales de superusuario dummy** en `docker-compose.yml` (si se usan para autoprovisión).

- **Gravedad Baja / Mejora**:  
  8) `serve_audio_file` fuerza `audio/ogg` en lugar de inferir el tipo.  
  9) Logging con paths/estado de archivos (útil para debug, pero mejor reducir en prod).

---

## Hallazgos Detallados

### 1) Controles de rol inconsistentes (ALTA)
- **Dónde**: `web/work_order/permissions.py` **L15** — `NotTecnicoRequiredMixin` valida **grupo** `"Técnico"`  
  ```py
  return not user.groups.filter(name__iregex="^t[eé]cnico$").exists()
  ```
- **Riesgo**: El proyecto usa **`accounts.CustomUser.user_type`** (`admin`, `tecnico`, etc.). En varias vistas/API se chequea `user_type`, pero este mixin usa **grupos**. Si un usuario con `user_type='tecnico'` no está en el grupo `"Técnico"`, **podría crear/editar** OTs (bypass).  
- **Recomendación**: Unificar criterio en **`user_type`** (o en grupos, pero uno solo). Ejemplo:
  ```py
  # web/work_order/permissions.py
  class NotTecnicoRequiredMixin(UserPassesTestMixin):
      def test_func(self):
          return getattr(self.request.user, "user_type", "") != "tecnico"
  ```
  Y en DRF ya usás:
  ```py
  class NotTecnicoWritePermission(permissions.BasePermission):
      def has_permission(self, request, view):
          if request.method in permissions.SAFE_METHODS:
              return request.user and request.user.is_authenticated
          return getattr(request.user, 'user_type', '') != 'tecnico'
  ```
  Además, agregá tests que validen que un `tecnico` **no puede** `POST/PUT/PATCH` ni en HTML ni en API.

---


### 2) Uso de `runserver` en compose (ALTA)
- **Dónde**: `docker-compose.yml` **L26**  
  ```yaml
  command: ["./wait-for-db.sh", "sh", "-c", "... & python bot.py & exec python manage.py runserver 0.0.0.0:8000"]
  ```
- **Riesgo**: `runserver` es **solo desarrollo**. No maneja concurrencia, ni timeouts, etc.  
- **Recomendación**: En producción usar **Gunicorn**/**Uvicorn** detrás de Nginx/Caddy/Traefik. Ejemplo:
  ```yaml
  command: ["./wait-for-db.sh", "sh", "-c", "python manage.py migrate && exec gunicorn web.wsgi:application -w 4 -b 0.0.0.0:8000"]
  ```
  Y mover **bot** a un **servicio separado** con permisos mínimos.

---

### 4) Adjuntos sin validación (MEDIA)
- **Dónde**: `web/work_order/models.py` **L72**  
  ```py
  archivo = models.FileField(upload_to="workorders/")
  ```
- **Riesgo**: Subida de archivos **sin limitar extensión/tamaño** → riesgo de **malware** o contenido activo si se abre en el browser.  
- **Recomendación**: Validar en **Form** y/o **clean()** del modelo:
  ```py
  # forms.py (ejemplo)
  ALLOWED_EXTS = {{".pdf", ".jpg", ".jpeg", ".png", ".docx", ".xlsx"}}
  MAX_MB = 10
  def clean_archivo(self):
      f = self.cleaned_data["archivo"]
      ext = Path(f.name).suffix.lower()
      if ext not in ALLOWED_EXTS:
          raise forms.ValidationError("Extensión no permitida.")
      if f.size > MAX_MB * 1024 * 1024:
          raise forms.ValidationError("Archivo demasiado grande.")
      return f
  ```
  Opcional: pasar por **antivirus (clamav-daemon)** y/o almacenar en **S3 con presigned URLs**.

---

### 5) API DRF sin throttling/paginación explícita (MEDIA)
- **Dónde**: `web/work_order/views.py` **L255-L260** (`WorkOrderViewSet`), `web/web/settings.py` (sin bloque DRF).  
- **Riesgo**: Scraping/DOS por llamadas masivas autenticadas.  
- **Recomendación** (en `settings.py` para **prod**):
  ```py
  REST_FRAMEWORK = {{  # añadir en prod
      "DEFAULT_AUTHENTICATION_CLASSES": [
          "rest_framework.authentication.SessionAuthentication",
      ],
      "DEFAULT_PERMISSION_CLASSES": [
          "rest_framework.permissions.IsAuthenticated",
      ],
      "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
      "PAGE_SIZE": 50,
      "DEFAULT_THROTTLE_CLASSES": [
          "rest_framework.throttling.UserRateThrottle",
          "rest_framework.throttling.AnonRateThrottle",
      ],
      "DEFAULT_THROTTLE_RATES": {{
          "user": "1000/day",
          "anon": "100/day",
      }},
  }}
  ```

---

### 6) Cookies/headers de seguridad (MEDIA)
- **Dónde**: `web/web/settings.py` — por defecto: **`DEBUG=True` (L24)**, **`ALLOWED_HOSTS=['*']` (L26)** y **sin** flags de seguridad (HSTS/SSL/cookies seguras).  
- **Recomendación** (para **prod**; sé que ya lo aplicás, dejo check-list):
  ```py
  SECURE_SSL_REDIRECT = True
  SESSION_COOKIE_SECURE = True
  CSRF_COOKIE_SECURE = True
  SESSION_COOKIE_HTTPONLY = True
  CSRF_COOKIE_HTTPONLY = True
  SECURE_HSTS_SECONDS = 31536000
  SECURE_HSTS_INCLUDE_SUBDOMAINS = True
  SECURE_HSTS_PRELOAD = True
  SECURE_REFERRER_POLICY = "same-origin"
  SECURE_CONTENT_TYPE_NOSNIFF = True
  X_FRAME_OPTIONS = "DENY"
  SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")  # si hay proxy
  ```
  Separar **settings_dev.py** y **settings_prod.py** usando `DJANGO_SETTINGS_MODULE`.

---

### 7) Credenciales de superusuario por defecto (MEDIA)
- **Dónde**: `docker-compose.yml` **L32-34**
  ```yaml
  DJANGO_SUPERUSER_USERNAME: admin
  DJANGO_SUPERUSER_PASSWORD: admin123
  ```
- **Riesgo**: Si algún script usa estas variables para **autocrear** el superusuario y el contenedor es accesible, queda una puerta obvia.  
- **Recomendación**: Usar **secrets/vars** reales en despliegue y **no** committear valores dummy. Si no se usan, eliminar.

---

### 8) Content-Type fijo en audio (BAJA)
- **Dónde**: `web/worklog/views.py` **L390**  
  ```py
  HttpResponse(f.read(), content_type='audio/ogg')
  ```
- **Mejora**: Usar `FileResponse` + `mimetypes.guess_type`:
  ```py
  from django.http import FileResponse
  import mimetypes
  ctype, _ = mimetypes.guess_type(file_path)
  return FileResponse(open(file_path, 'rb'), content_type=ctype or 'application/octet-stream')
  ```

---

### 9) Logging de paths/estado de archivos (BAJA)
- **Dónde**: `serve_audio_file` (múltiples `logger.info` con rutas).  
- **Mejora**: En **prod**, bajar a `DEBUG` o sanitizar rutas para evitar fuga innecesaria de estructura interna en logs.

---

## Otras Recomendaciones

- **Bot de Telegram**: ya mapeás usuarios por `telegram_chat_id` (bien). Recomendado:
  - Añadir *rate-limiting* por chat/acción.
  - Cifrar/hashear transcripciones sensibles en repositorios externos si se comparten.
  - Correr el bot en **contenedor aislado** (sección `bot` separada en compose) con **montajes mínimos**.

- **Límites de subida**: setear en settings:
  ```py
  DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10MB
  FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
  ```

- **CSP (Content Security Policy)**: si exponés vistas complejas, considerar `django-csp` para reducir XSS.

- **Backups & Rotación de logs**: verificar rotación y almacenamiento seguro de backups de DB/media.

---

## Checklist rápido (Prod)

- [ ] `DEBUG=False`, `ALLOWED_HOSTS` y `CSRF_TRUSTED_ORIGINS` correctos (✔️ ya lo tenés).  
- [ ] Gunicorn/Uvicorn + proxy; **no** `runserver`.   
- [ ] Permisos unificados por `user_type` (arreglar mixin).  
- [ ] Validación de archivos + límite de tamaño + (opcional AV).  
- [ ] DRF: paginación + throttling.  
- [ ] Cookies/headers de seguridad activados.  
- [ ] Usuario admin con password fuerte, creado de forma controlada.  


