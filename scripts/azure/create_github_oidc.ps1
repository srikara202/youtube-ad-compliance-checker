param(
    [Parameter(Mandatory = $true)]
    [string]$SubscriptionId,

    [Parameter(Mandatory = $true)]
    [string]$ResourceGroupName,

    [Parameter(Mandatory = $true)]
    [string]$RepoOwner,

    [Parameter(Mandatory = $true)]
    [string]$RepoName,

    [Parameter(Mandatory = $true)]
    [string]$WebAppName,

    [string]$Branch = "main",
    [string]$EntraAppName = "github-actions-youtube-ad-compliance-checker"
)

$ErrorActionPreference = "Stop"

function Assert-AzureCli {
    $pythonCli = "C:\Program Files\Microsoft SDKs\Azure\CLI2\python.exe"
    if (Test-Path $pythonCli) {
        $script:AzCliExecutable = $pythonCli
        $script:AzCliPrefixArgs = @("-m", "azure.cli")
        return
    }

    $azCommand = Get-Command az -ErrorAction SilentlyContinue
    if (-not $azCommand) {
        throw "Azure CLI is required. Install Azure CLI and run 'az login' before using this script."
    }

    $script:AzCliExecutable = $azCommand.Source
    $script:AzCliPrefixArgs = @()
}

function Invoke-Az {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)

    $result = & $script:AzCliExecutable @script:AzCliPrefixArgs @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Azure CLI command failed: az $($Arguments -join ' ')"
    }
    return $result
}

Assert-AzureCli

$tenantId = Invoke-Az account show --subscription $SubscriptionId --query tenantId --output tsv
$existingAppId = Invoke-Az ad app list --display-name $EntraAppName --query "[0].appId" --output tsv

if ($existingAppId) {
    $appId = $existingAppId
    Write-Host "Reusing existing Microsoft Entra app '$EntraAppName'."
}
else {
    Write-Host "Creating Microsoft Entra app '$EntraAppName'..."
    $appId = Invoke-Az ad app create --display-name $EntraAppName --query appId --output tsv
}

try {
    $spObjectId = Invoke-Az ad sp show --id $appId --query id --output tsv 2>$null
}
catch {
    $spObjectId = ""
}
if (-not $spObjectId) {
    Write-Host "Creating service principal..."
    Invoke-Az ad sp create --id $appId --output none
    $spObjectId = Invoke-Az ad sp show --id $appId --query id --output tsv
}

$scope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName"
$roleExists = Invoke-Az role assignment list `
    --assignee-object-id $spObjectId `
    --scope $scope `
    --query "[?roleDefinitionName=='Contributor'] | length(@)" `
    --output tsv

if ($roleExists -eq "0") {
    Write-Host "Assigning Contributor on resource group '$ResourceGroupName'..."
    Invoke-Az role assignment create `
        --assignee-object-id $spObjectId `
        --assignee-principal-type ServicePrincipal `
        --role Contributor `
        --scope $scope `
        --output none
}

$subject = "repo:$RepoOwner/$RepoName:ref:refs/heads/$Branch"
$existingCredential = Invoke-Az ad app federated-credential list --id $appId `
    --query "[?subject=='$subject'] | length(@)" `
    --output tsv

if ($existingCredential -eq "0") {
    $credentialPayload = @{
        name = "github-$Branch"
        issuer = "https://token.actions.githubusercontent.com"
        subject = $subject
        audiences = @("api://AzureADTokenExchange")
    } | ConvertTo-Json -Depth 4

    $credentialFile = Join-Path $env:TEMP "github-federated-credential.json"
    Set-Content -Path $credentialFile -Value $credentialPayload -Encoding UTF8

    Write-Host "Creating federated credential for branch '$Branch'..."
    Invoke-Az ad app federated-credential create `
        --id $appId `
        --parameters $credentialFile `
        --output none

    Remove-Item $credentialFile -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "Add these GitHub repository secrets:"
Write-Host "AZURE_CLIENT_ID=$appId"
Write-Host "AZURE_TENANT_ID=$tenantId"
Write-Host "AZURE_SUBSCRIPTION_ID=$SubscriptionId"
Write-Host "AZURE_WEBAPP_NAME=$WebAppName"
