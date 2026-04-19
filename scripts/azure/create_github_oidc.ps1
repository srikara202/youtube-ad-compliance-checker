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
    if (-not (Get-Command az -ErrorAction SilentlyContinue)) {
        throw "Azure CLI is required. Install Azure CLI and run 'az login' before using this script."
    }
}

Assert-AzureCli

$tenantId = az account show --subscription $SubscriptionId --query tenantId --output tsv
$existingAppId = az ad app list --display-name $EntraAppName --query "[0].appId" --output tsv

if ($existingAppId) {
    $appId = $existingAppId
    Write-Host "Reusing existing Microsoft Entra app '$EntraAppName'."
}
else {
    Write-Host "Creating Microsoft Entra app '$EntraAppName'..."
    $appId = az ad app create --display-name $EntraAppName --query appId --output tsv
}

$spObjectId = az ad sp show --id $appId --query id --output tsv 2>$null
if (-not $spObjectId) {
    Write-Host "Creating service principal..."
    az ad sp create --id $appId --output none
    $spObjectId = az ad sp show --id $appId --query id --output tsv
}

$scope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroupName"
$roleExists = az role assignment list `
    --assignee-object-id $spObjectId `
    --scope $scope `
    --query "[?roleDefinitionName=='Contributor'] | length(@)" `
    --output tsv

if ($roleExists -eq "0") {
    Write-Host "Assigning Contributor on resource group '$ResourceGroupName'..."
    az role assignment create `
        --assignee-object-id $spObjectId `
        --assignee-principal-type ServicePrincipal `
        --role Contributor `
        --scope $scope `
        --output none
}

$subject = "repo:$RepoOwner/$RepoName:ref:refs/heads/$Branch"
$existingCredential = az ad app federated-credential list --id $appId `
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
    az ad app federated-credential create `
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
