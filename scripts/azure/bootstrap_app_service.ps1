param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$WebAppName,

    [string]$ResourceGroupName = "youtube-ad-compliance-rg",
    [string]$AppServicePlanName = "youtube-ad-compliance-f1",
    [string]$Location = "australiaeast",
    [string]$Runtime = "PYTHON|3.12",
    [string]$EnvFilePath = ".env",
    [string]$VideoIndexerResourceGroup = "",
    [string]$VideoIndexerAccountName = ""
)

$ErrorActionPreference = "Stop"

function Assert-AzureCli {
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI is required. Install Azure CLI and run 'az login' before using this script."
    }
}

function Parse-DotEnv {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        throw "Could not find env file at '$Path'."
    }

    $settings = [System.Collections.Generic.List[string]]::new()
    foreach ($line in Get-Content $Path) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $parts = $trimmed.Split("=", 2)
        if ($parts.Count -ne 2) {
            continue
        }

        $name = $parts[0].Trim()
        $rawValue = $parts[1].Trim()
        if ($rawValue.StartsWith('"')) {
            $endQuote = $rawValue.IndexOf('"', 1)
            if ($endQuote -gt 0) {
                $value = $rawValue.Substring(1, $endQuote - 1)
            }
            else {
                $value = $rawValue.Trim('"')
            }
        }
        elseif ($rawValue.StartsWith("'")) {
            $endQuote = $rawValue.IndexOf("'", 1)
            if ($endQuote -gt 0) {
                $value = $rawValue.Substring(1, $endQuote - 1)
            }
            else {
                $value = $rawValue.Trim("'")
            }
        }
        else {
            $value = ($rawValue -split '\s+#', 2)[0].Trim()
        }

        if ($name) {
            $settings.Add("$name=$value")
        }
    }

    return $settings
}

Assert-AzureCli

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$resolvedEnvPath = Join-Path $repoRoot $EnvFilePath
$appSettings = Parse-DotEnv -Path $resolvedEnvPath

$envMap = @{}
foreach ($setting in $appSettings) {
    $name, $value = $setting.Split("=", 2)
    $envMap[$name] = $value
}

if (-not $VideoIndexerResourceGroup -and $envMap.ContainsKey("AZURE_RESOURCE_GROUP")) {
    $VideoIndexerResourceGroup = $envMap["AZURE_RESOURCE_GROUP"]
}

if (-not $VideoIndexerAccountName -and $envMap.ContainsKey("AZURE_VI_NAME")) {
    $VideoIndexerAccountName = $envMap["AZURE_VI_NAME"]
}

$appSettings.Add("SCM_DO_BUILD_DURING_DEPLOYMENT=true")
$appSettings.Add("ENABLE_ORYX_BUILD=true")
if ($envMap.ContainsKey("FRONTEND_ORIGINS")) {
    $filteredSettings = [System.Collections.Generic.List[string]]::new()
    foreach ($setting in $appSettings) {
        if ($setting -notlike "FRONTEND_ORIGINS=*") {
            $filteredSettings.Add($setting)
        }
    }
    $appSettings = $filteredSettings
}
$appSettings.Add("FRONTEND_ORIGINS=https://$WebAppName.azurewebsites.net")

Write-Host "Creating or updating resource group '$ResourceGroupName'..."
az group create `
    --name $ResourceGroupName `
    --location $Location `
    --output none

Write-Host "Creating or updating App Service plan '$AppServicePlanName'..."
az appservice plan create `
    --name $AppServicePlanName `
    --resource-group $ResourceGroupName `
    --location $Location `
    --sku F1 `
    --is-linux `
    --output none

Write-Host "Creating or updating web app '$WebAppName'..."
az webapp create `
    --resource-group $ResourceGroupName `
    --plan $AppServicePlanName `
    --name $WebAppName `
    --runtime $Runtime `
    --output none

Write-Host "Enabling managed identity..."
az webapp identity assign `
    --resource-group $ResourceGroupName `
    --name $WebAppName `
    --output none

Write-Host "Configuring startup command..."
az webapp config set `
    --resource-group $ResourceGroupName `
    --name $WebAppName `
    --startup-file "bash startup.sh" `
    --output none

Write-Host "Applying app settings from .env..."
az webapp config appsettings set `
    --resource-group $ResourceGroupName `
    --name $WebAppName `
    --settings $appSettings `
    --output none

if ($VideoIndexerResourceGroup -and $VideoIndexerAccountName) {
    $principalId = az webapp identity show `
        --resource-group $ResourceGroupName `
        --name $WebAppName `
        --query principalId `
        --output tsv

    $videoIndexerScope = "/subscriptions/$SubscriptionId/resourceGroups/$VideoIndexerResourceGroup/providers/Microsoft.VideoIndexer/accounts/$VideoIndexerAccountName"

    Write-Host "Assigning Contributor on Azure Video Indexer account '$VideoIndexerAccountName'..."
    az role assignment create `
        --assignee-object-id $principalId `
        --assignee-principal-type ServicePrincipal `
        --role Contributor `
        --scope $videoIndexerScope `
        --output none
}
else {
    Write-Warning "Skipped Azure Video Indexer role assignment because AZURE_RESOURCE_GROUP or AZURE_VI_NAME was not available."
}

Write-Host ""
Write-Host "App Service bootstrap complete."
Write-Host "Web app URL: https://$WebAppName.azurewebsites.net"
