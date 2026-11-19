#!/bin/sh
set -eu
# The application owns its schema and can run Flyway migrations inside this DB.
psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" --set=ON_ERROR_STOP=1 \
    --set=app_password="$FINSIGHT_BUSINESS_DB_PASSWORD" <<'SQL'
CREATE ROLE finsight LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD :'app_password';
ALTER DATABASE finsight OWNER TO finsight;
SQL
