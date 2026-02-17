param(
    [Parameter(Mandatory = $true)][string]$BackupFile,
    [string]$NewHost = "localhost",
    [string]$NewPort = "5432",
    [string]$NewAdminUser = "postgres",
    [string]$AppDb = "hydrawise",
    [string]$AppUser = "hydrawise",
    [Parameter(Mandatory = $true)][string]$AppPassword,
    [string]$NewAdminPassword,
    [switch]$RestoreGlobals,
    [string]$GlobalsFile
)

$ErrorActionPreference = "Stop"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Command,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $Command $($Arguments -join ' ')"
    }
}

function Assert-CommandExists {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command not found in PATH: $Name"
    }
}

function Run-Psql {
    param([Parameter(Mandatory = $true)][string]$Sql, [string]$Db = "postgres")
    Invoke-CheckedCommand -Command "psql" -Arguments @(
        "-h", $NewHost,
        "-p", $NewPort,
        "-U", $NewAdminUser,
        "-d", $Db,
        "-v", "ON_ERROR_STOP=1",
        "-c", $Sql
    )
}

Write-Host "=== Hydrawise NEW PC Restore Script ===" -ForegroundColor Cyan

Assert-CommandExists -Name "psql"
Assert-CommandExists -Name "createdb"
Assert-CommandExists -Name "pg_restore"

$resolvedBackup = Resolve-Path -Path $BackupFile -ErrorAction SilentlyContinue
if (-not $resolvedBackup) {
    throw "Backup file not found: $BackupFile"
}
$resolvedBackup = $resolvedBackup.Path

if ($RestoreGlobals) {
    if (-not $GlobalsFile) {
        throw "You set -RestoreGlobals but did not provide -GlobalsFile."
    }
    $resolvedGlobals = Resolve-Path -Path $GlobalsFile -ErrorAction SilentlyContinue
    if (-not $resolvedGlobals) {
        throw "Globals file not found: $GlobalsFile"
    }
    $resolvedGlobals = $resolvedGlobals.Path
}

if (-not $NewAdminPassword) {
    $secure = Read-Host "Enter NEW PC PostgreSQL admin password for user '$NewAdminUser'" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $NewAdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$previousPgPassword = $env:PGPASSWORD
$env:PGPASSWORD = $NewAdminPassword

try {
    Write-Host "`n1) Checking PostgreSQL access..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Command "psql" -Arguments @(
        "-h", $NewHost,
        "-p", $NewPort,
        "-U", $NewAdminUser,
        "-d", "postgres",
        "-c", "SELECT version();"
    )

    if ($RestoreGlobals) {
        Write-Host "`n2) Restoring globals (roles/cluster objects)..." -ForegroundColor Yellow
        Invoke-CheckedCommand -Command "psql" -Arguments @(
            "-h", $NewHost,
            "-p", $NewPort,
            "-U", $NewAdminUser,
            "-d", "postgres",
            "-f", $resolvedGlobals
        )
    }

    Write-Host "`n3) Ensuring app role exists and has expected password..." -ForegroundColor Yellow
    $createRoleSql = @"
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$AppUser') THEN
        CREATE ROLE $AppUser LOGIN PASSWORD '$AppPassword';
    ELSE
        ALTER ROLE $AppUser WITH LOGIN PASSWORD '$AppPassword';
    END IF;
END $$;
"@
    Run-Psql -Sql $createRoleSql -Db "postgres"

    Write-Host "`n4) Ensuring target database exists..." -ForegroundColor Yellow
    $dbExists = & psql -h $NewHost -p $NewPort -U $NewAdminUser -d postgres -t -A -c "SELECT 1 FROM pg_database WHERE datname = '$AppDb';"
    if ($LASTEXITCODE -ne 0) {
        throw "Failed checking if database exists."
    }
    if (-not ($dbExists -match "1")) {
        Invoke-CheckedCommand -Command "createdb" -Arguments @(
            "-h", $NewHost,
            "-p", $NewPort,
            "-U", $NewAdminUser,
            "-O", $AppUser,
            $AppDb
        )
        Write-Host "Created database '$AppDb'." -ForegroundColor Green
    }
    else {
        Write-Host "Database '$AppDb' already exists; continuing." -ForegroundColor DarkYellow
    }

    Write-Host "`n5) Restoring backup into target database..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Command "pg_restore" -Arguments @(
        "-h", $NewHost,
        "-p", $NewPort,
        "-U", $NewAdminUser,
        "-d", $AppDb,
        "--no-owner",
        "--no-privileges",
        "--exit-on-error",
        "-v",
        $resolvedBackup
    )

    Write-Host "`n6) Applying ownership and grants for app user..." -ForegroundColor Yellow
    Run-Psql -Sql "ALTER DATABASE $AppDb OWNER TO $AppUser;" -Db "postgres"
    Run-Psql -Sql "ALTER SCHEMA public OWNER TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "GRANT ALL PRIVILEGES ON ALL FUNCTIONS IN SCHEMA public TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO $AppUser;" -Db $AppDb
    Run-Psql -Sql "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON FUNCTIONS TO $AppUser;" -Db $AppDb

    Write-Host "`n7) Verifying login and table visibility as app user..." -ForegroundColor Yellow
    $env:PGPASSWORD = $AppPassword
    Invoke-CheckedCommand -Command "psql" -Arguments @(
        "-h", $NewHost,
        "-p", $NewPort,
        "-U", $AppUser,
        "-d", $AppDb,
        "-c", "\dt"
    )
    Invoke-CheckedCommand -Command "psql" -Arguments @(
        "-h", $NewHost,
        "-p", $NewPort,
        "-U", $AppUser,
        "-d", $AppDb,
        "-c", "SELECT NOW();"
    )

    Write-Host "`nRestore complete." -ForegroundColor Green
    Write-Host "Update your project .env to local DB:" -ForegroundColor Cyan
    Write-Host "  DATABASE_TYPE=postgresql" -ForegroundColor Cyan
    Write-Host "  DATABASE_URL=postgresql://$AppUser:<YOUR_PASSWORD>@localhost:$NewPort/$AppDb" -ForegroundColor Cyan
    Write-Host "  DB_HOST=localhost" -ForegroundColor Cyan
    Write-Host "  DB_PORT=$NewPort" -ForegroundColor Cyan
    Write-Host "  DB_NAME=$AppDb" -ForegroundColor Cyan
    Write-Host "  DB_USER=$AppUser" -ForegroundColor Cyan
    Write-Host "  DB_PASSWORD=<YOUR_PASSWORD>" -ForegroundColor Cyan
}
finally {
    if ($null -ne $previousPgPassword) {
        $env:PGPASSWORD = $previousPgPassword
    }
    else {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}
