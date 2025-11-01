-- Crear DB (si tu usuario tiene permisos); si ya existe, ignorar este bloque manualmente.
-- CREATE DATABASE platform_admin;

-- Conéctate a la DB platform_admin antes de ejecutar el resto.

-- Requisitos y esquema
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE SCHEMA IF NOT EXISTS control_plane;

-- Roles lógicos (sin login) para permisos mínimos
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ops_read') THEN
    CREATE ROLE ops_read NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='ops_admin') THEN
    CREATE ROLE ops_admin NOLOGIN;
  END IF;
END$$;

-- Quitar permisos a PUBLIC en el esquema
REVOKE ALL ON SCHEMA control_plane FROM PUBLIC;

-- Conceder uso del esquema
GRANT USAGE ON SCHEMA control_plane TO ops_read, ops_admin;

-- Permisos por defecto a futuro
ALTER DEFAULT PRIVILEGES IN SCHEMA control_plane GRANT SELECT ON TABLES TO ops_read;
ALTER DEFAULT PRIVILEGES IN SCHEMA control_plane GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO ops_admin;
