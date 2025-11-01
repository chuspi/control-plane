import os
from typing import Optional

class SecretManager:
    """
    Adapter de secretos con backends conmutables por env:
      - dev:    env | mock
      - stage/prod: vault | aws | gcp | azure  (requiere endpoint)
    """

    def __init__(self, backend: Optional[str] = None, endpoint: Optional[str] = None):
        self.env = (os.getenv("ENVIRONMENT", "dev") or "dev").lower()
        self.backend = (backend or os.getenv("SECRET_MANAGER_BACKEND") or "env").lower()
        self.endpoint = endpoint or os.getenv("SECRET_MANAGER_ENDPOINT") or ""

        # Guardrail: en staging/prod no se permiten env/mock
        if self.env in {"staging", "prod"} and self.backend in {"env", "mock"}:
            raise RuntimeError(
                f"SECRET_MANAGER_BACKEND={self.backend} no permitido en {self.env}; "
                f"use uno de: vault|aws|gcp|azure"
            )

        # Guardrail: en staging/prod, si backend es real, endpoint es obligatorio
        if self.env in {"staging", "prod"} and self.backend in {"vault", "aws", "gcp", "azure"}:
            if not self.endpoint.strip():
                raise RuntimeError(
                    f"Falta SECRET_MANAGER_ENDPOINT para backend={self.backend} en {self.env}"
                )

    async def get_password(self, secret_ref: str) -> str:
        # Backends de desarrollo
        if self.backend == "env":
            pwd = os.getenv("CONTROL_PLANE_TENANT_DB_PASSWORD")
            if not pwd:
                raise RuntimeError("CONTROL_PLANE_TENANT_DB_PASSWORD no definida (backend=env, solo dev).")
            return pwd

        if self.backend == "mock":
            return "<REPLACE_ME_DB_PASSWORD>"

        # Placeholders para backends reales
        if self.backend == "vault":
            # TODO: implementar con hvac (u otro), usando self.endpoint + secret_ref
            raise NotImplementedError("Vault backend aún no implementado.")
        if self.backend == "aws":
            # TODO: implementar con boto3/SecretsManager
            raise NotImplementedError("AWS Secrets Manager backend aún no implementado.")
        if self.backend == "gcp":
            # TODO: implementar con google-cloud-secret-manager
            raise NotImplementedError("GCP Secret Manager backend aún no implementado.")
        if self.backend == "azure":
            # TODO: implementar con azure-keyvault-secrets
            raise NotImplementedError("Azure Key Vault backend aún no implementado.")

        raise ValueError(f"SECRET_MANAGER_BACKEND desconocido: {self.backend}")
