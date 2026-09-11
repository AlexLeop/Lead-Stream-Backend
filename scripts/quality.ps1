$ErrorActionPreference = "Stop"

$python = if (Test-Path ".venv\Scripts\python.exe") {
    ".venv\Scripts\python.exe"
} else {
    "python"
}

function Invoke-QualityStep {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Name,
        [Parameter(Mandatory = $true)]
        [scriptblock]$Action
    )

    Write-Host "`n==> $Name"
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "A etapa '$Name' falhou com o código $LASTEXITCODE."
    }
}

Invoke-QualityStep "Ruff" { & $python -m ruff check . }
Invoke-QualityStep "Mypy" { & $python -m mypy src }

$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
Invoke-QualityStep "Migrations pendentes" {
    & $python manage.py makemigrations --check --dry-run
}

$env:DJANGO_SETTINGS_MODULE = "config.settings.production"
$env:DJANGO_SECRET_KEY = "quality-check-only-this-is-not-a-production-secret-change-me"
$env:DJANGO_ALLOWED_HOSTS = "quality.invalid"
$env:DATABASE_URL = "postgresql://quality:quality@localhost:5432/quality"
$env:CELERY_BROKER_URL = "amqp://quality:quality@localhost:5672//"
$env:REDIS_URL = "redis://localhost:6379/15"
$env:DJANGO_SECURE_SSL_REDIRECT = "true"
$env:DATA_HASH_KEY = "quality-check-only-data-hash-key"
$env:DATA_HASH_KEY_VERSION = "v1"
Invoke-QualityStep "Configuração de produção" {
    & $python manage.py check --deploy --fail-level WARNING
}

$env:DJANGO_SETTINGS_MODULE = "config.settings.test"
Invoke-QualityStep "Testes" { & $python -m pytest -q }

Write-Host "`nTodos os gates de qualidade passaram."
