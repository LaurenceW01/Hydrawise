param(
    [string]$SrcHost = "localhost",
    [string]$SrcPort = "5432",
    [string]$SrcAdminUser = "postgres",
    [string]$SrcDb = "hydrawise",
    [string]$OutputDir = ".",
    [string]$BackupFileName = "hydrawise.backup",
    [switch]$IncludeGlobals,
    [string]$SourceAdminPassword
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

Write-Host "=== Hydrawise OLD PC Backup Script ===" -ForegroundColor Cyan

Assert-CommandExists -Name "psql"
Assert-CommandExists -Name "pg_dump"
Assert-CommandExists -Name "pg_restore"
if ($IncludeGlobals) {
    Assert-CommandExists -Name "pg_dumpall"
}

if (-not $SourceAdminPassword) {
    $secure = Read-Host "Enter SOURCE PostgreSQL admin password for user '$SrcAdminUser'" -AsSecureString
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $SourceAdminPassword = [Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

$resolvedOutputDir = (Resolve-Path -Path $OutputDir -ErrorAction SilentlyContinue)
if (-not $resolvedOutputDir) {
    New-Item -ItemType Directory -Path $OutputDir | Out-Null
    $resolvedOutputDir = Resolve-Path -Path $OutputDir
}
$resolvedOutputDir = $resolvedOutputDir.Path

$backupPath = Join-Path $resolvedOutputDir $BackupFileName
$globalsPath = Join-Path $resolvedOutputDir "globals.sql"

$previousPgPassword = $env:PGPASSWORD
$env:PGPASSWORD = $SourceAdminPassword

try {
    Write-Host "`n1) Checking source databases..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Command "psql" -Arguments @(
        "-h", $SrcHost,
        "-p", $SrcPort,
        "-U", $SrcAdminUser,
        "-d", "postgres",
        "-c", "\l"
    )

    Write-Host "`n2) Creating custom-format backup..." -ForegroundColor Yellow
    Invoke-CheckedCommand -Command "pg_dump" -Arguments @(
        "-h", $SrcHost,
        "-p", $SrcPort,
        "-U", $SrcAdminUser,
        "-d", $SrcDb,
        "-F", "c",
        "-b",
        "-v",
        "-f", $backupPath
    )

    if ($IncludeGlobals) {
        Write-Host "`n3) Exporting globals (roles/cluster objects)..." -ForegroundColor Yellow
        Invoke-CheckedCommand -Command "pg_dumpall" -Arguments @(
            "-h", $SrcHost,
            "-p", $SrcPort,
            "-U", $SrcAdminUser,
            "--globals-only"
        ) | Out-File -FilePath $globalsPath -Encoding utf8
    }

    Write-Host "`n4) Backup integrity checks..." -ForegroundColor Yellow
    Get-Item $backupPath | Format-List Name, Length, LastWriteTime
    Invoke-CheckedCommand -Command "pg_restore" -Arguments @("-l", $backupPath)

    Write-Host "`nBackup complete." -ForegroundColor Green
    Write-Host "Backup file: $backupPath" -ForegroundColor Green
    if ($IncludeGlobals) {
        Write-Host "Globals file: $globalsPath" -ForegroundColor Green
    }
}
finally {
    if ($null -ne $previousPgPassword) {
        $env:PGPASSWORD = $previousPgPassword
    }
    else {
        Remove-Item Env:PGPASSWORD -ErrorAction SilentlyContinue
    }
}
