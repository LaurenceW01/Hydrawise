# Hydrawise PostgreSQL Migration Runbook (Exact, End-to-End)

This guide gives exact, copy/paste instructions to:

1. Back up the Hydrawise PostgreSQL database on the **old PC**
2. Transfer it to the **new PC**
3. Restore it with the exact project naming expected by this codebase
4. Verify the app connects with project credentials

---

## 0) What this project expects (important)

From the project code (`database/db_config.py`), runtime DB config is:

- First priority: `DATABASE_URL`
- Fallback only if `DATABASE_URL` is missing: `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`

For this runbook, the project user/database names are:

- Database: `hydrawise`
- App DB user: `hydrawise`
- Port: `5432`

If your source DB has a different name, set the variables in the steps below accordingly.

---

## 1) Prerequisites on BOTH PCs

1. PostgreSQL is installed.
2. PostgreSQL command-line tools are available: `psql`, `pg_dump`, `pg_restore`, `createdb`.
3. You can authenticate as an admin user (commonly `postgres`).

### 1.1 Verify tools in PowerShell

```powershell
Get-Command psql, pg_dump, pg_restore, createdb
```

If not found, either:

- open the "SQL Shell (psql)" and use full paths, or
- add PostgreSQL bin folder to PATH (example):

```powershell
$env:Path += ";C:\Program Files\PostgreSQL\16\bin"
```

Replace `16` with your installed PostgreSQL version.

---

## 2) On OLD PC: create backup files

Use these values (edit if your source uses different host/port/user/db):

```powershell
$SRC_HOST = "localhost"
$SRC_PORT = "5432"
$SRC_ADMIN_USER = "postgres"
$SRC_DB = "hydrawise"
```

Set admin password for this shell session:

```powershell
$env:PGPASSWORD = "<SOURCE_ADMIN_PASSWORD>"
```

### 2.1 Confirm source DB exists

```powershell
psql -h $SRC_HOST -p $SRC_PORT -U $SRC_ADMIN_USER -d postgres -c "\l"
```

### 2.2 Create a custom-format backup (recommended)

```powershell
pg_dump -h $SRC_HOST -p $SRC_PORT -U $SRC_ADMIN_USER -d $SRC_DB -F c -b -v -f ".\hydrawise.backup"
```

Notes:

- `-F c` = custom format (best for controlled restore)
- `-b` = includes large objects

### 2.3 Optional: save globals (roles/cluster objects)

Only needed if you want to migrate cluster-wide roles exactly.

```powershell
pg_dumpall -h $SRC_HOST -p $SRC_PORT -U $SRC_ADMIN_USER --globals-only > ".\globals.sql"
```

### 2.4 Integrity checks before transfer

```powershell
Get-Item ".\hydrawise.backup" | Format-List Name,Length,LastWriteTime
pg_restore -l ".\hydrawise.backup" | Select-Object -First 20
```

If these commands work, the backup file is readable.

---

## 3) Transfer files to NEW PC

Copy at minimum:

- `hydrawise.backup`

Optional:

- `globals.sql`

After copy, place files in an easy folder, example:

- `C:\Temp\hydrawise-migration\`

---

## 4) On NEW PC: restore with project credentials

This section restores to local PostgreSQL with:

- DB = `hydrawise`
- user = `hydrawise`

### 4.1 Set variables

```powershell
$NEW_HOST = "localhost"
$NEW_PORT = "5432"
$NEW_ADMIN_USER = "postgres"
$APP_DB = "hydrawise"
$APP_USER = "hydrawise"
$APP_PASSWORD = "<SET_THIS_TO_YOUR_PROJECT_DB_PASSWORD>"
$BACKUP_FILE = "C:\Temp\hydrawise-migration\hydrawise.backup"
```

Set admin password:

```powershell
$env:PGPASSWORD = "<NEW_PC_ADMIN_PASSWORD>"
```

### 4.2 Create app user if needed

```powershell
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d postgres -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$APP_USER') THEN CREATE ROLE $APP_USER LOGIN PASSWORD '$APP_PASSWORD'; END IF; END \$\$;"
```

If user already exists and you need to update password:

```powershell
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d postgres -c "ALTER ROLE $APP_USER WITH LOGIN PASSWORD '$APP_PASSWORD';"
```

### 4.3 Create target DB if needed

```powershell
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d postgres -c "SELECT 1 FROM pg_database WHERE datname = '$APP_DB';"
createdb -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -O $APP_USER $APP_DB
```

If `createdb` says it already exists, continue.

### 4.4 Restore data/schema

Use this command to avoid source ownership/privilege conflicts while keeping content intact:

```powershell
pg_restore -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB --no-owner --no-privileges --exit-on-error -v "$BACKUP_FILE"
```

### 4.5 Ensure ownership and grants for app user

```powershell
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d postgres -c "ALTER DATABASE $APP_DB OWNER TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "ALTER SCHEMA public OWNER TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $APP_USER;"
psql -h $NEW_HOST -p $NEW_PORT -U $NEW_ADMIN_USER -d $APP_DB -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $APP_USER;"
```

---

## 5) Configure this project `.env` for local DB

Set these values in `.env`:

```env
DATABASE_TYPE=postgresql
DATABASE_URL=postgresql://hydrawise:<YOUR_PASSWORD>@localhost:5432/hydrawise

DB_HOST=localhost
DB_PORT=5432
DB_NAME=hydrawise
DB_USER=hydrawise
DB_PASSWORD=<YOUR_PASSWORD>
```

Important:

- Keep `DATABASE_URL` accurate, because it takes priority.
- Ensure `DB_NAME` and `DB_USER` are present (runtime fallback uses these names).
- `DB_DATABASE` / `DB_USERNAME` are not the primary names used by `database/db_config.py`.

---

## 6) Verify restore and app connectivity

### 6.1 Verify PostgreSQL objects/data

```powershell
$env:PGPASSWORD = "<YOUR_PASSWORD>"
psql -h localhost -p 5432 -U hydrawise -d hydrawise -c "\dt"
psql -h localhost -p 5432 -U hydrawise -d hydrawise -c "SELECT NOW();"
```

### 6.2 Verify through project scripts

From project root:

```powershell
python test_db_connection.py
python initialize_database.py
```

If both succeed, the app is correctly pointed at the restored local DB.

---

## 7) Optional exact ACL/owner clone mode (advanced)

If you require exact source ownership/ACL metadata (not just data/schema):

1. restore `globals.sql` first:

```powershell
$env:PGPASSWORD = "<NEW_PC_ADMIN_PASSWORD>"
psql -h localhost -p 5432 -U postgres -d postgres -f "C:\Temp\hydrawise-migration\globals.sql"
```

2. restore backup **without** `--no-owner --no-privileges`.

This can affect cluster roles globally. Use only if you explicitly need exact role/ACL parity.

---

## 8) Troubleshooting

### Error: `role "hydrawise" does not exist`

Create role first (Section 4.2), then rerun restore.

### Error: `permission denied for relation ...`

Re-run grants in Section 4.5.

### Error: cannot connect / SSL issues

For local connections, use `localhost` and standard local auth; avoid remote `DATABASE_URL`.

### Error: `pg_restore: [archiver] unsupported version`

Use a newer PostgreSQL client tools version on the new PC (same or newer than source).

---

## 9) Minimal command checklist (quick copy/paste)

```powershell
# OLD PC
$env:PGPASSWORD="<SOURCE_ADMIN_PASSWORD>"
pg_dump -h localhost -p 5432 -U postgres -d hydrawise -F c -b -v -f ".\hydrawise.backup"

# NEW PC
$env:PGPASSWORD="<NEW_PC_ADMIN_PASSWORD>"
psql -h localhost -p 5432 -U postgres -d postgres -c "CREATE ROLE hydrawise LOGIN PASSWORD '<APP_PASSWORD>';"
createdb -h localhost -p 5432 -U postgres -O hydrawise hydrawise
pg_restore -h localhost -p 5432 -U postgres -d hydrawise --no-owner --no-privileges --exit-on-error -v "C:\Temp\hydrawise-migration\hydrawise.backup"
psql -h localhost -p 5432 -U postgres -d postgres -c "ALTER DATABASE hydrawise OWNER TO hydrawise;"
psql -h localhost -p 5432 -U postgres -d hydrawise -c "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO hydrawise;"
psql -h localhost -p 5432 -U postgres -d hydrawise -c "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO hydrawise;"
```

---

## 10) Completion criteria

Migration is complete when all are true:

1. `psql -U hydrawise -d hydrawise -c "\dt"` returns expected tables
2. `python test_db_connection.py` passes
3. `.env` `DATABASE_URL` points to local `localhost:5432/hydrawise`
4. App runs and can read/write records

