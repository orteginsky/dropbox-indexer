import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AuthService:
    """Client for AccessTokenDropbox microservice on Cloud Run."""

    def __init__(self):
        self.token_service_url = settings.token_service_url.rstrip('/')
        self.api_secret_key = settings.api_secret_key
        
        # Variables para el manejo de caché
        self._cached_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None

    async def get_valid_token(self) -> str:
        """
        Obtiene un token de acceso de Dropbox vía POST.
        Utiliza caché local por 3.5 horas para evitar peticiones redundantes.
        """
        # 1. Verificar si tenemos un token en caché y si aún es válido
        if self._cached_token and self._token_expires_at and datetime.utcnow() < self._token_expires_at:
            logger.debug("Usando token de Dropbox desde el caché local")
            return self._cached_token

        # 2. Configuración de la petición
        headers = {
            "Content-Type": "application/json"
        }
        # Usamos la clave de las variables de entorno para mayor seguridad
        payload = {
            "signature": self.api_secret_key, 
            "service": "dropbox-index"
        }
        
        endpoint = f"{self.token_service_url}/api/v1/token"

        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Obteniendo nuevo token de: {endpoint}")
            
            token = None
            last_error = None

            # 3. Intentar hasta 3 veces (Reintentos asíncronos)
            for attempt in range(1, 4):
                try:
                    # ¡IMPORTANTE! El 'await' es necesario en FastAPI
                    response = await client.post(endpoint, json=payload, headers=headers)
                    response.raise_for_status()
                    
                    token = response.json().get("access_token")
                    if token:
                        break # ¡Éxito! Salimos del bucle de reintentos

                except httpx.HTTPError as e:
                    last_error = e
                    logger.warning(f"Intento {attempt}/3 falló: {e}")
                    if attempt < 3:
                        await asyncio.sleep(1) # Espera 1 seg sin bloquear el servidor

            if not token:
                logger.critical("No se pudo obtener el token después de 3 intentos.")
                raise ValueError(f"Falla al conectar con microservicio. Último error: {last_error}")

            # 4. Guardamos en caché
            self._cached_token = token
            self._token_expires_at = datetime.utcnow() + timedelta(hours=3, minutes=30)
            
            logger.info("✅ Token de Dropbox obtenido y guardado en caché exitosamente")
            return token


# Instancia única (Singleton) para que el caché funcione en toda la app
auth_service = AuthService()