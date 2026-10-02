#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Produces optional test-recurrence hints without selecting builds or reading logs.
.DESCRIPTION
    The default provider is none: every requested prior build is UNKNOWN and requires
    the scanner's existing original-evidence lookback. Fixture is for offline tests only.
    No supported test-history service exists for public CI today.
.EXAMPLE
    ./Get-CiScanRecurrenceHints.ps1 -InputPath request.json -Provider none -OutputPath hints.json
#>
[CmdletBinding()]
param(
    [Alias('-input')]
    [string]$InputPath,
    [Alias('-provider')]
    [ValidateSet('none', 'fixture')]
    [string]$Provider = 'none',
    [Alias('-fixture')]
    [string]$FixturePath,
    [Alias('-output')]
    [string]$OutputPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Test-CiScanPositiveId {
    param($Value)
    return (($Value -is [int] -or $Value -is [long]) -and $Value -gt 0)
}

function Assert-CiScanRecurrenceRequest {
    param([System.Collections.IDictionary]$Request)
    if ($null -eq $Request -or -not (Test-CiScanPositiveId $Request['schema_version']) -or
        $Request['schema_version'] -ne 1 -or
        $Request['key'] -isnot [System.Collections.IDictionary]) {
        throw 'Expected schema_version 1 and an exact failure key.'
    }
    $key = $Request['key']
    if (-not (Test-CiScanPositiveId $key['definition_id'])) {
        throw 'key.definition_id must be a positive integer.'
    }
    foreach ($name in @('test_name', 'arguments', 'argument_hash', 'queue_name', 'test_run_name', 'signature')) {
        if ($key[$name] -isnot [string]) {
            throw "key.$name must be a string, including explicit empty arguments/configuration."
        }
    }
    if ([string]::IsNullOrWhiteSpace($key['test_name']) -or
        [string]::IsNullOrWhiteSpace($key['signature'])) {
        throw 'The test name and failure signature must not be empty.'
    }
    if ($Request['prior_build_ids'] -isnot [array] -or $Request['prior_build_ids'].Count -gt 100) {
        throw 'prior_build_ids must be an array of at most 100 selected build IDs.'
    }
    foreach ($id in $Request['prior_build_ids']) {
        if (-not (Test-CiScanPositiveId $id)) {
            throw 'Every prior_build_ids entry must be a positive integer.'
        }
    }
}

function Get-CiScanRecurrenceHints {
    param(
        [System.Collections.IDictionary]$Request,
        [ValidateSet('none', 'fixture')]
        [string]$Provider = 'none',
        $Fixture
    )
    Assert-CiScanRecurrenceRequest $Request
    $key = $Request['key']
    $providerError = $null
    if ($Provider -eq 'fixture') {
        if ($Fixture -isnot [System.Collections.IDictionary] -or
            $Fixture['key'] -isnot [System.Collections.IDictionary] -or
            $Fixture['builds'] -isnot [array] -or $Fixture['error']) {
            $providerError = 'fixture-unavailable-or-invalid'
        }
        else {
            if (-not (Test-CiScanPositiveId $Fixture['key']['definition_id'])) {
                $providerError = 'fixture-key-mismatch'
            }
            foreach ($name in @('definition_id', 'test_name', 'arguments', 'argument_hash',
                                'queue_name', 'test_run_name', 'signature')) {
                if (($name -ne 'definition_id' -and $Fixture['key'][$name] -isnot [string]) -or
                    $Fixture['key'][$name] -cne $key[$name]) {
                    $providerError = 'fixture-key-mismatch'
                }
            }
        }
    }
    $seen = [System.Collections.Generic.HashSet[long]]::new()
    $hints = @(
        foreach ($id in $Request['prior_build_ids']) {
            if (-not $seen.Add([long]$id)) { continue }
            $state = 'UNKNOWN'
            $reason = 'provider-disabled'
            if ($Provider -eq 'fixture') {
                $reason = if ($providerError) { $providerError } else { 'missing-or-ambiguous' }
                if (-not $providerError) {
                    $records = @($Fixture['builds'] | Where-Object {
                        $_ -is [System.Collections.IDictionary] -and
                        (Test-CiScanPositiveId $_['build_id']) -and $_['build_id'] -eq $id
                    })
                    if ($records.Count -eq 1 -and $records[0]['observations'] -is [array] -and
                        $records[0]['observations'].Count -gt 0) {
                        $other = @($records[0]['observations'] | Where-Object {
                            $_ -isnot [System.Collections.IDictionary] -or
                            $_['outcome'] -cne 'Failed' -or $_['signature'] -cne $key['signature']
                        })
                        if ($other.Count -eq 0) {
                            $state = 'RECURRED'
                            $reason = 'exact-failure-observed'
                        }
                        else {
                            $reason = 'mixed-or-nonmatching-observations'
                        }
                    }
                }
            }
            [ordered]@{ build_id = $id; state = $state; reason = $reason }
        }
    )
    return [ordered]@{
        schema_version = 1
        provider = $Provider
        key = $key
        hints = $hints
        diagnostics = @($(if ($providerError) { $providerError }))
    }
}

if ($MyInvocation.InvocationName -eq '.') { return }

if ($InputPath) {
    $request = Get-Content -LiteralPath $InputPath -Raw | ConvertFrom-Json -AsHashtable
    $fixture = $null
    if ($Provider -eq 'fixture') {
        if (-not $FixturePath) { throw 'The test-only fixture provider requires FixturePath.' }
        try {
            $fixture = Get-Content -LiteralPath $FixturePath -Raw | ConvertFrom-Json -AsHashtable
        }
        catch [System.Management.Automation.ItemNotFoundException] {
            Write-Warning 'Fixture unavailable; every requested build requires original fallback.'
        }
        catch [System.UnauthorizedAccessException] {
            Write-Warning 'Fixture unreadable; every requested build requires original fallback.'
        }
        catch [System.IO.IOException] {
            Write-Warning 'Fixture read failed; every requested build requires original fallback.'
        }
        catch [System.ArgumentException] {
            Write-Warning 'Fixture JSON invalid; every requested build requires original fallback.'
        }
    }
    $result = Get-CiScanRecurrenceHints -Request $request -Provider $Provider -Fixture $fixture
}
elseif ($Provider -eq 'none') {
    # Discovery and window selection still belong to the agent, after this bootstrap.
    $result = [ordered]@{
        schema_version = 1; provider = 'none'; key = $null; hints = @()
        diagnostics = @('provider-disabled; supply an exact key and selected IDs after discovery')
    }
}
else {
    throw 'The test-only fixture provider requires InputPath.'
}
foreach ($diagnostic in $result['diagnostics']) {
    if ($Provider -ne 'none') { Write-Warning "$diagnostic; original fallback required." }
}
$json = $result | ConvertTo-Json -Depth 20
if ($OutputPath) {
    $directory = Split-Path -Parent ([System.IO.Path]::GetFullPath($OutputPath))
    [System.IO.Directory]::CreateDirectory($directory) | Out-Null
    [System.IO.File]::WriteAllText($OutputPath, "$json`n", [System.Text.UTF8Encoding]::new($false))
}
else {
    $json
}
