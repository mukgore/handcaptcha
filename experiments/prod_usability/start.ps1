$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
node ./build.cjs
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
node ./server.cjs 8770
