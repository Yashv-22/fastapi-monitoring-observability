$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
$secretDirectory = Join-Path $projectRoot '.secrets'
$secretPath = Join-Path $secretDirectory 'slack_webhook_url'
$webhook = $env:SLACK_WEBHOOK_URL

# PowerShell does not automatically import Compose's .env file. Read only this
# named key when it is not already present in the process environment.
if ([string]::IsNullOrWhiteSpace($webhook)) {
    $dotenvPath = Join-Path $projectRoot '.env'
    if (Test-Path -LiteralPath $dotenvPath) {
        foreach ($line in Get-Content -LiteralPath $dotenvPath) {
            if ($line -match '^\s*SLACK_WEBHOOK_URL\s*=\s*(.*)\s*$') {
                $webhook = $Matches[1].Trim().Trim('"').Trim("'")
                break
            }
        }
    }
}

if ([string]::IsNullOrWhiteSpace($webhook)) {
    throw 'Set SLACK_WEBHOOK_URL in the process environment or ignored .env file. The value was not displayed.'
}

$uri = $null
if (-not [System.Uri]::TryCreate($webhook, [System.UriKind]::Absolute, [ref]$uri) -or
    $uri.Scheme -ne 'https' -or
    $uri.Host -ne 'hooks.slack.com' -or
    -not $uri.AbsolutePath.StartsWith('/services/', [System.StringComparison]::Ordinal)) {
    throw 'SLACK_WEBHOOK_URL must be an HTTPS Slack incoming-webhook URL. The value was not displayed.'
}

New-Item -ItemType Directory -Path $secretDirectory -Force | Out-Null
[System.IO.File]::WriteAllText($secretPath, $webhook, [System.Text.UTF8Encoding]::new($false))
Write-Output 'Slack webhook secret prepared in the ignored local secret file; the value was not displayed.'
