# Lance la chaine sous Windows, en deux fenetres.
#
#   .\lancer.ps1                  le mode collaboratif
#   .\lancer.ps1 --simulation     le client dit ce qu'il enverrait, sans envoyer
#   .\lancer.ps1 -ServeurSeul     seulement le serveur d'entree
#
# Pourquoi ce script
# ------------------
# STK_input_server_v2.py cree sa manette virtuelle avec /dev/uinput : il ne
# peut tourner que sous Linux. Sous Windows, l'erreur obtenue est
# "No module named 'evdev'", et le conseil qui suit ("sudo chmod 666
# /dev/uinput") n'a pas de sens ici -- d'ou ce lanceur, qui prend d'office le
# bon des deux serveurs.
#
# $Reste est declare EN PREMIER, en Position 0 : sans ca un argument comme
# "--simulation" serait pris pour la valeur du premier parametre positionnel.

param(
    [Parameter(Position = 0, ValueFromRemainingArguments = $true)] $Reste,
    [switch]$ServeurSeul,
    [ValidateSet('', 'serveur', 'client')] [string]$Role = '',
    [string]$Arguments = ''
)

$DEPOT = Split-Path -Parent $MyInvocation.MyCommand.Path

# Le venv du projet s'il existe a cote, sinon le python du PATH.
$PY = Join-Path (Split-Path -Parent $DEPOT) ".venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { $PY = "python" }

if ($Role -eq 'serveur') {
    $host.UI.RawUI.WindowTitle = 'SERVEUR (manette virtuelle)'
    & $PY (Join-Path $DEPOT 'STK_input_server_win.py') -d
    return
}

if ($Role -eq 'client') {
    $host.UI.RawUI.WindowTitle = 'COLLABORATIF'
    $liste = @()
    if ($Arguments) {
        $liste = $Arguments.Split(' ', [StringSplitOptions]::RemoveEmptyEntries)
    }
    & $PY (Join-Path $DEPOT 'collaboratif\collaboratif.py') @liste
    return
}

$moi = $MyInvocation.MyCommand.Path

Write-Host ""
Write-Host "=== SERVEUR (manette virtuelle Windows) ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList @('-NoExit', '-File', $moi, '-Role', 'serveur')

if ($ServeurSeul) {
    Write-Host ""
    Write-Host "Serveur seul. Lance le client quand tu veux." -ForegroundColor Yellow
    Write-Host ""
    return
}

Start-Sleep -Seconds 2

$argsClient = @('-NoExit', '-File', $moi, '-Role', 'client')
if ($Reste) { $argsClient += @('-Arguments', ($Reste -join ' ')) }

Write-Host "=== COLLABORATIF ===" -ForegroundColor Cyan
Start-Process powershell -ArgumentList $argsClient

Write-Host ""
Write-Host "Deux fenetres ouvertes. Il reste a :" -ForegroundColor Yellow
Write-Host "  1. lancer SuperTuxKart en FENETRE (pas en plein ecran)"
Write-Host "  2. Options > Controles : la direction sur l'axe du Xbox 360"
Write-Host "     Controller, tout le reste au clavier"
Write-Host "  3. demarrer une course, puis cliquer dans la fenetre du jeu"
Write-Host "  4. Q dans la fenetre video, ou Ctrl+C, pour tout relacher"
Write-Host ""
