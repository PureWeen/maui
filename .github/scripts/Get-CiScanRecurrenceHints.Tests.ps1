#!/usr/bin/env pwsh
#Requires -Modules Pester

BeforeAll {
    $script:HintScript = Join-Path $PSScriptRoot 'Get-CiScanRecurrenceHints.ps1'
    . $script:HintScript
    $script:Glide = Get-Content (Join-Path $PSScriptRoot 'fixtures/ci-scan-recurrence-glide.json') -Raw |
        ConvertFrom-Json -AsHashtable
    $script:Issue33038 = Get-Content (Join-Path $PSScriptRoot 'fixtures/ci-scan-recurrence-issue33038.json') -Raw |
        ConvertFrom-Json -AsHashtable

    function New-Fixture {
        param($Data)
        return @{ key = $Data.request.key; builds = $Data.observations }
    }
    function Copy-TestValue {
        param($Value)
        return ($Value | ConvertTo-Json -Depth 20 | ConvertFrom-Json -AsHashtable)
    }
    function Merge-TestOriginals {
        param($Data, $Hints, [int[]]$Unavailable = @())
        $positive = [System.Collections.Generic.HashSet[long]]::new()
        [void]$positive.Add($Data.original.current_build_id)
        $fallback = @($Hints.hints | Where-Object state -EQ 'UNKNOWN' | ForEach-Object build_id)
        $unknown = @()
        foreach ($hint in $Hints.hints) {
            if ($hint.state -eq 'RECURRED') { [void]$positive.Add($hint.build_id) }
            elseif ($hint.build_id -in $Unavailable) { $unknown += $hint.build_id }
            elseif ($hint.build_id -in $Data.original.positive_build_ids) { [void]$positive.Add($hint.build_id) }
        }
        return @{
            positive = @($positive | Sort-Object)
            fallback = @($fallback | Sort-Object)
            unknown = $unknown
            complete = $unknown.Count -eq 0
        }
    }
}

Describe 'No-provider recurrence hook' {
    It 'defaults to UNKNOWN for every selected prior build' {
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request
        $hints.provider | Should -Be 'none'
        @($hints.hints).Count | Should -Be 2
        @($hints.hints | Where-Object state -NE 'UNKNOWN').Count | Should -Be 0
        ($hints.hints.build_id -join ',') | Should -Be '1605031,1605107'
    }

    It 'keeps the original-only decision identical with provider none' -ForEach @(
        @{ FixtureName = 'Glide' }, @{ FixtureName = 'Issue33038' }
    ) {
        $data = Get-Variable $FixtureName -ValueOnly
        $hints = Get-CiScanRecurrenceHints -Request $data.request -Provider none
        $merged = Merge-TestOriginals $data $hints
        $merged.complete | Should -BeTrue
        ($merged.positive -join ',') | Should -Be (($data.original.positive_build_ids | Sort-Object) -join ',')
        $merged.fallback.Count | Should -Be $data.request.prior_build_ids.Count
    }

    It 'supports the disabled pre-agent bootstrap and double-dash provider option' {
        $output = Join-Path $TestDrive 'bootstrap.json'
        & pwsh -NoProfile -File $HintScript --provider none --output $output
        $LASTEXITCODE | Should -Be 0
        $result = Get-Content $output -Raw | ConvertFrom-Json -AsHashtable
        $result.provider | Should -Be 'none'
        $result.key | Should -BeNullOrEmpty
        $result.hints.Count | Should -Be 0
    }

    It 'does not read a fixture in default mode' {
        Mock Get-Content { throw 'Unexpected fixture read' }
        Get-CiScanRecurrenceHints -Request $Glide.request | Out-Null
        Should -Invoke Get-Content -Times 0
    }
}

Describe 'Exact-key offline fixture provider' {
    It 'preserves three distinct builds, >=2 and window-bounded First seen' {
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider fixture -Fixture (New-Fixture $Glide)
        $merged = Merge-TestOriginals $Glide $hints
        $merged.positive.Count | Should -Be 3
        ($merged.positive.Count -ge 2) | Should -BeTrue
        $merged.fallback.Count | Should -Be 0
        ($merged.positive -join ',') | Should -Be '1605031,1605107,1605518'
        $first = @($merged.positive | ForEach-Object { $Glide.original.finish_times[[string]$_] } | Sort-Object)[0]
        if ($first -is [datetime]) { $first = $first.ToUniversalTime().ToString('o') }
        $first | Should -Be '2026-09-21T12:02:16.8695081Z'
        $first.Substring(0, 10) | Should -Be '2026-09-21'
    }

    It 'deduplicates selected IDs and multiple observations to one hint per build' {
        $request = Copy-TestValue $Glide.request
        $request.prior_build_ids += 1605107
        $hints = Get-CiScanRecurrenceHints -Request $request -Provider fixture -Fixture (New-Fixture $Glide)
        $hints.hints.Count | Should -Be 2
    }

    It 'routes the four OLD Issue33038 cases to originals and preserves 9/11' {
        $hints = Get-CiScanRecurrenceHints -Request $Issue33038.request -Provider fixture -Fixture (New-Fixture $Issue33038)
        $merged = Merge-TestOriginals $Issue33038 $hints
        ($merged.fallback -join ',') | Should -Be '1595567,1597560,1599656,1600800'
        $merged.positive.Count | Should -Be 9
        (1 + $hints.hints.Count) | Should -Be 11
    }

    It 'falls back if any component of the exact key differs' -ForEach @(
        @{ Field = 'definition_id'; Value = 313 }, @{ Field = 'test_name'; Value = 'AnotherTest' },
        @{ Field = 'arguments'; Value = 'argument' }, @{ Field = 'argument_hash'; Value = 'other' },
        @{ Field = 'queue_name'; Value = 'android.34' }, @{ Field = 'test_run_name'; Value = 'Debug' },
        @{ Field = 'signature'; Value = 'different exception' }
    ) {
        $fixture = Copy-TestValue (New-Fixture $Glide)
        $fixture.key[$Field] = $Value
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider fixture -Fixture $fixture
        @($hints.hints | Where-Object state -NE 'UNKNOWN').Count | Should -Be 0
        $hints.diagnostics | Should -Contain 'fixture-key-mismatch'
    }

    It 'does not match a signature found only in a different observation' {
        $fixture = Copy-TestValue (New-Fixture $Glide)
        $fixture.builds[0].observations = @(
            @{ outcome = 'Failed'; signature = 'other exception' },
            @{ outcome = 'Passed'; signature = $Glide.request.key.signature }
        )
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider fixture -Fixture $fixture
        $hints.hints[0].state | Should -Be 'UNKNOWN'
    }

    It 'falls back for passed, passed-on-rerun, not-executed and mixed outcomes' -ForEach @(
        @{ Outcome = 'Passed' }, @{ Outcome = 'PassedOnRerun' }, @{ Outcome = 'NotExecuted' }
    ) {
        $fixture = Copy-TestValue (New-Fixture $Glide)
        $fixture.builds[0].observations += @{ outcome = $Outcome; signature = '' }
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider fixture -Fixture $fixture
        $hints.hints[0].state | Should -Be 'UNKNOWN'
    }

    It 'falls back for missing, malformed, duplicate and errored provider data' {
        $fixtures = @(
            $null, @{}, 'invalid', @{ error = 'unavailable' },
            @{ key = $Glide.request.key; builds = @() },
            @{ key = $Glide.request.key; builds = @($Glide.observations[0], $Glide.observations[0]) },
            @{ key = $Glide.request.key; builds = @(@{ build_id = 1605031; observations = @('invalid') }) }
        )
        foreach ($fixture in $fixtures) {
            $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider fixture -Fixture $fixture
            @($hints.hints | Where-Object state -NE 'UNKNOWN').Count | Should -Be 0
        }
    }

    It 'keeps failed original fallback incomplete, never false or non-recurring' {
        $hints = Get-CiScanRecurrenceHints -Request $Glide.request -Provider none
        $merged = Merge-TestOriginals $Glide $hints -Unavailable @(1605031)
        $merged.complete | Should -BeFalse
        $merged.unknown | Should -Contain 1605031
    }

    It 'rejects an invalid request rather than inventing successful hints' {
        foreach ($request in @(@{}, @{ schema_version = 1 }, @{ schema_version = 1; key = @{} })) {
            { Get-CiScanRecurrenceHints -Request $request } | Should -Throw
        }
        $request = Copy-TestValue $Glide.request
        $request.prior_build_ids = @(-1)
        { Get-CiScanRecurrenceHints -Request $request } | Should -Throw '*positive integer*'
    }

    It 'materializes per-build UNKNOWN hints on the real none-provider CLI' {
        $inputFile = Join-Path $TestDrive 'request.json'
        $output = Join-Path $TestDrive 'hints.json'
        $Glide.request | ConvertTo-Json -Depth 20 | Set-Content $inputFile
        & pwsh -NoProfile -File $HintScript --provider none --input $inputFile --output $output
        $LASTEXITCODE | Should -Be 0
        $result = Get-Content $output -Raw | ConvertFrom-Json -AsHashtable
        $result.hints.Count | Should -Be 2
        @($result.hints | Where-Object state -NE 'UNKNOWN').Count | Should -Be 0
    }

    It 'warns and preserves UNKNOWN on unreadable or malformed fixture JSON' {
        $inputFile = Join-Path $TestDrive 'fixture-request.json'
        $badFixture = Join-Path $TestDrive 'invalid.json'
        $output = Join-Path $TestDrive 'error-hints.json'
        $Glide.request | ConvertTo-Json -Depth 20 | Set-Content $inputFile
        Set-Content $badFixture '{broken'
        $wrongShape = Join-Path $TestDrive 'wrong-shape.json'
        Set-Content $wrongShape '"invalid"'
        foreach ($fixture in @($badFixture, $wrongShape, (Join-Path $TestDrive 'missing.json'))) {
            & pwsh -NoProfile -File $HintScript --provider fixture --input $inputFile --fixture $fixture --output $output
            $LASTEXITCODE | Should -Be 0
            $result = Get-Content $output -Raw | ConvertFrom-Json -AsHashtable
            $result.diagnostics | Should -Contain 'fixture-unavailable-or-invalid'
            @($result.hints | Where-Object state -NE 'UNKNOWN').Count | Should -Be 0
        }
    }
}

Describe 'Workflow boundary' {
    It 'hard-codes only none in both scanner sources and compiler-generated locks' {
        foreach ($name in @('ci-status-main', 'ci-status-net11')) {
            foreach ($extension in @('md', 'lock.yml')) {
                $text = Get-Content (Join-Path $PSScriptRoot "../workflows/$name.$extension") -Raw
                $text | Should -Match 'Get-CiScanRecurrenceHints.ps1 --provider none'
                $text | Should -Not -Match '--provider fixture'
            }
        }
    }
}
