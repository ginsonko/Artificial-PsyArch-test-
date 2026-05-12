param(
  [Parameter(Mandatory=$true)]
  [string]$RepoUrl,

  [string]$Branch = "master",

  [switch]$SkipIntegrityCheck
)

$ErrorActionPreference = "Stop"

function Run-Git {
  param([Parameter(ValueFromRemainingArguments=$true)][string[]]$Args)
  git @Args
  if ($LASTEXITCODE -ne 0) {
    throw "git $($Args -join ' ') failed with exit code $LASTEXITCODE"
  }
}

if (-not $SkipIntegrityCheck) {
  python .\scripts\verify_release_integrity.py
  if ($LASTEXITCODE -ne 0) {
    throw "Integrity check failed. Use -SkipIntegrityCheck only if you intentionally publish after a manual review."
  }
}

$status = git status --short
if ($status) {
  Write-Host "Working tree is not clean:"
  Write-Host $status
  throw "Commit or discard local changes before publishing."
}

$existing = git remote get-url origin 2>$null
if ($LASTEXITCODE -ne 0) {
  Run-Git remote add origin $RepoUrl
} elseif ($existing -ne $RepoUrl) {
  Write-Host "Existing origin: $existing"
  Write-Host "Requested origin: $RepoUrl"
  throw "Origin already exists with a different URL. Update it manually if this is intended."
}

Run-Git push -u origin $Branch
Run-Git ls-remote --heads origin $Branch

Write-Host "Published $Branch to $RepoUrl"
