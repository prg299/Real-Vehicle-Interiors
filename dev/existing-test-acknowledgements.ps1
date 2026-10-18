# Copy only acknowledgement values already present in the established isolated
# test profile. Never invent a new terms version or perform an agreement action.
function Add-ExistingTestAcknowledgements([string]$OptionsText, [string]$SourcePath) {
    if (-not (Test-Path -LiteralPath $SourcePath -PathType Leaf)) { return $OptionsText }
    $sourceText = [IO.File]::ReadAllText($SourcePath)
    foreach ($key in @('termsOfServiceVersion', 'showWelcomeMessage2', 'tutorialDone')) {
        $match = [regex]::Match($sourceText, ('(?m)^' + [regex]::Escape($key) + '=([^\r\n]*)'))
        if (-not $match.Success) { continue }
        $value = $match.Groups[1].Value
        $pattern = '(?m)^' + [regex]::Escape($key) + '=.*$'
        if ([regex]::IsMatch($OptionsText, $pattern)) {
            $OptionsText = [regex]::Replace($OptionsText, $pattern, ($key + '=' + $value))
        } else { $OptionsText = $OptionsText.TrimEnd() + "`n$key=$value`n" }
    }
    return $OptionsText
}
