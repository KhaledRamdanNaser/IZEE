@echo off
set "PATH=%PATH%;C:\Program Files\PostgreSQL\18\bin"
set "PGPASSWORD=1234"

echo Checking PostgreSQL tools from PATH...
where pg_isready
where psql
echo.

echo Checking PostgreSQL server on localhost:5433...
pg_isready -h localhost -p 5433
echo.

echo Checking database login...
psql -h localhost -p 5433 -U postgres -d izee_db -c "select current_database(), current_user;"
echo.

echo Done. This window can stay open so you can see the result.
