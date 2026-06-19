@echo off
setlocal

set "PROJECT_DIR=D:\GradProject\IZEE"
set "PYTHON_EXE=C:\Users\Omar\AppData\Local\Programs\Python\Python312\python.exe"
set "PGPASSWORD=1234"
set "PYTHONPATH=%PROJECT_DIR%"
set "IZEE_CONVERTED_DIR=%PROJECT_DIR%\local_replay_data"
set "IZEE_REPLAY_FILES=day_1_monday_observations.jsonl"

cd /d "%PROJECT_DIR%"

echo ============================================================
echo IZEE GTFS-Based Full Pipeline Test
echo ============================================================
echo.

echo [1/6] Generate GTFS-based observations...
"%PYTHON_EXE%" scripts\generate_gtfs_pipeline_observations.py
if errorlevel 1 goto fail
echo.

echo [2/6] Initialize database schema...
"%PYTHON_EXE%" init_db.py
if errorlevel 1 goto fail
echo.

echo [3/7] Sync existing database schema...
"%PYTHON_EXE%" scripts\sync_db_schema.py
if errorlevel 1 goto fail
echo.

echo [4/8] Load GTFS reference tables if empty...
"%PYTHON_EXE%" scripts\load_gtfs_if_empty.py
if errorlevel 1 goto fail
echo.

echo [5/8] Clean previous GTFS pipeline test rows...
"%PYTHON_EXE%" scripts\cleanup_gtfs_pipeline_test.py
if errorlevel 1 goto fail
echo.

echo [6/8] Run bulk replay through Vehicle State Engine and Event Engine...
"%PYTHON_EXE%" scripts\bulk_replay.py
if errorlevel 1 goto fail
echo.

echo [7/8] Build segment statistics...
"%PYTHON_EXE%" scripts\segment_stats.py
if errorlevel 1 goto fail
echo.

echo [8/8] Run Alert Engine...
"%PYTHON_EXE%" scripts\alert_engine_run.py
if errorlevel 1 goto fail
echo.

echo ============================================================
echo Final verification counts
echo ============================================================
psql -h localhost -p 5433 -U postgres -d izee_db -c "select 'transit_events' as table_name, count(*) from transit_events union all select 'segment_statistics', count(*) from segment_statistics union all select 'alerts', count(*) from alerts;"
psql -h localhost -p 5433 -U postgres -d izee_db -c "select type, severity, count(*) from alerts group by type, severity order by type, severity;"

echo.
echo DONE. Review the output above.
goto end

:fail
echo.
echo FAILED. Review the error above.

:end
endlocal
