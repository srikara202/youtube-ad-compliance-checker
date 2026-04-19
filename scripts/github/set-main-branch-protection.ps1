param(
    [Parameter(Mandatory = $true)]
    [string]$GitHubToken,

    [string]$RepoOwner = "srikara202",
    [string]$RepoName = "youtube-ad-compliance-checker",
    [string]$Branch = "main",
    [string]$RequiredCheck = "Test and Build"
)

$ErrorActionPreference = "Stop"

$headers = @{
    Authorization = "Bearer $GitHubToken"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$body = @{
    required_status_checks = @{
        strict = $true
        contexts = @($RequiredCheck)
    }
    enforce_admins = $false
    required_pull_request_reviews = @{
        dismiss_stale_reviews = $false
        require_code_owner_reviews = $false
        required_approving_review_count = 0
    }
    restrictions = $null
    allow_force_pushes = $false
    allow_deletions = $false
    block_creations = $false
    required_conversation_resolution = $false
    lock_branch = $false
    allow_fork_syncing = $true
    required_linear_history = $false
} | ConvertTo-Json -Depth 6

$uri = "https://api.github.com/repos/$RepoOwner/$RepoName/branches/$Branch/protection"

Invoke-RestMethod -Method Put -Uri $uri -Headers $headers -ContentType "application/json" -Body $body | Out-Null
Write-Host "Branch protection updated for $RepoOwner/$RepoName:$Branch"
