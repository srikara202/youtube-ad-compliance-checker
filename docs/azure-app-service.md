# Azure App Service Setup

This project is configured for a single-host deployment:

- FastAPI serves the API
- FastAPI also serves the built React app from `frontend/dist`
- GitHub Actions runs tests on pull requests and deploys `main` to Azure App Service

## Prerequisites

- Azure CLI installed and authenticated
- Permission to create App Service resources and Microsoft Entra applications
- Existing Azure OpenAI, Azure AI Search, Azure AI Video Indexer, and related runtime resources already configured in `.env`

## 1. Create the App Service resources

From the repo root, run:

```powershell
.\scripts\azure\bootstrap_app_service.ps1 `
  -SubscriptionId "<your-subscription-id>" `
  -WebAppName "<globally-unique-webapp-name>" `
  -ResourceGroupName "youtube-ad-compliance-rg" `
  -AppServicePlanName "youtube-ad-compliance-f1" `
  -Location "australiaeast"
```

What the script does:

- Creates the resource group if needed
- Creates a Linux App Service plan on `F1`
- Creates the Python 3.12 web app
- Enables system-assigned managed identity
- Sets the startup command to `bash startup.sh`
- Copies the current `.env` values into App Service application settings
- Adds App Service deployment build settings
- Assigns `Contributor` on the Azure Video Indexer account resource so the app can call `generateAccessToken`

## 2. Create GitHub OIDC deployment identity

Run:

```powershell
.\scripts\azure\create_github_oidc.ps1 `
  -SubscriptionId "<your-subscription-id>" `
  -ResourceGroupName "youtube-ad-compliance-rg" `
  -RepoOwner "srikara202" `
  -RepoName "youtube-ad-compliance-checker" `
  -WebAppName "<same-webapp-name>"
```

The script prints the GitHub secrets to add:

- `AZURE_CLIENT_ID`
- `AZURE_TENANT_ID`
- `AZURE_SUBSCRIPTION_ID`
- `AZURE_WEBAPP_NAME`

No runtime secrets from `.env` should be stored in GitHub.

## 3. Enable branch protection

Option A: run the helper script with a GitHub PAT that has repo admin access:

```powershell
.\scripts\github\set-main-branch-protection.ps1 `
  -RepoOwner "srikara202" `
  -RepoName "youtube-ad-compliance-checker" `
  -GitHubToken "<admin-token>"
```

Option B: configure it manually in GitHub:

- Protect `main`
- Require pull requests before merge
- Require status checks to pass before merge
- Require the `Test and Build` check

## 4. Deployment behavior

- Pull requests to `main` run backend tests, frontend tests, and frontend build
- Pushes to `main` rerun the same checks and deploy to Azure App Service

## 5. App Service expectations

- App Service uses `requirements.txt` during build automation
- `startup.sh` launches Gunicorn with the Uvicorn worker
- The React frontend must be built in CI so `frontend/dist` is included in the deployment package

## 6. Smoke test after deploy

Verify:

- `https://<webapp-name>.azurewebsites.net/health` returns 200
- `https://<webapp-name>.azurewebsites.net/` serves the React UI
- Creating an audit from the browser starts and completes or fails with a visible terminal state
