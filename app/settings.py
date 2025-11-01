import os

ENVIRONMENT = os.getenv("ENVIRONMENT", "dev").lower()
SECRET_MANAGER_BACKEND = os.getenv("SECRET_MANAGER_BACKEND", "env").lower()
SECRET_MANAGER_ENDPOINT = os.getenv("SECRET_MANAGER_ENDPOINT", "")

# Guardrail: en staging/prod NO se permite env/mock
if ENVIRONMENT in {"staging", "prod"} and SECRET_MANAGER_BACKEND in {"env", "mock"}:
    raise RuntimeError(
        f"SECRET_MANAGER_BACKEND={SECRET_MANAGER_BACKEND} no permitido en {ENVIRONMENT}; "
        f"use uno de: vault|aws|gcp|azure"
    )
