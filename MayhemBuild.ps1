# MayhemBuild.ps1
# Fica observando o cliente do League of Legends. Quando voce pega/troca de
# campeao na selecao, abre a build dele no METAsrc (ARAM Mayhem).
#
# Uso:  powershell -ExecutionPolicy Bypass -File MayhemBuild.ps1
# Parar: Ctrl+C (ou fechar a janela)

param(
    # Segundos que o campeao precisa ficar igual antes de abrir a pagina
    # (evita abrir varias abas quando voce troca rapido no banco do ARAM).
    [double]$Espera = 1.5,
    # Base da URL; troque por https://www.metasrc.com/lol/aram para ARAM normal.
    [string]$BaseUrl = "https://www.metasrc.com/lol/mayhem/champions"
)

$ErrorActionPreference = 'Stop'

# --- O cliente do LoL usa certificado auto-assinado em 127.0.0.1 ---------------
if (-not ([System.Management.Automation.PSTypeName]'TrustAllCerts').Type) {
    Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
public class TrustAllCerts : ICertificatePolicy {
    public bool CheckValidationResult(ServicePoint sp, X509Certificate cert, WebRequest req, int problem) { return true; }
}
"@
}
[System.Net.ServicePointManager]::CertificatePolicy = New-Object TrustAllCerts
[System.Net.ServicePointManager]::SecurityProtocol = [System.Net.SecurityProtocolType]::Tls12

# --- Nomes que o METAsrc escreve diferente -------------------------------------
$Excecoes = @{
    'Jarvan IV'      = 'jarvan'
    'Nunu & Willump' = 'nunu'
    'MonkeyKing'     = 'wukong'
}

function Get-Slug([string]$nome) {
    if ($Excecoes.ContainsKey($nome)) { return $Excecoes[$nome] }
    $s = $nome.ToLower() -replace "['.]", '' -replace '[^a-z0-9]+', '-'
    return $s.Trim('-')
}

# --- Descobre porta e senha da API local do cliente ----------------------------
function Get-LcuAuth {
    $proc = Get-CimInstance Win32_Process -Filter "Name='LeagueClientUx.exe'" -ErrorAction SilentlyContinue |
            Select-Object -First 1
    if ($proc -and $proc.CommandLine -match '--app-port=(\d+)' ) {
        $port = $Matches[1]
        if ($proc.CommandLine -match '--remoting-auth-token=([\w-]+)') {
            return @{ Port = $port; Token = $Matches[1] }
        }
    }
    # Plano B: arquivo lockfile na pasta de instalacao
    $client = Get-Process LeagueClient -ErrorAction SilentlyContinue | Select-Object -First 1
    $dirs = @()
    if ($client -and $client.Path) { $dirs += Split-Path $client.Path }
    $dirs += 'C:\Riot Games\League of Legends', 'D:\Riot Games\League of Legends'
    foreach ($d in $dirs) {
        $lf = Join-Path $d 'lockfile'
        if (Test-Path $lf) {
            try {
                $parts = (Get-Content $lf -Raw -ErrorAction Stop).Split(':')
                return @{ Port = $parts[2]; Token = $parts[3] }
            } catch {}
        }
    }
    return $null
}

function Invoke-Lcu($auth, [string]$path) {
    $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("riot:$($auth.Token)"))
    Invoke-RestMethod -Uri "https://127.0.0.1:$($auth.Port)$path" -UseBasicParsing `
        -Headers @{ Authorization = "Basic $b64" } -TimeoutSec 3
}

# --- Loop principal -------------------------------------------------------------
Write-Host "MayhemBuild rodando. Abra o LoL e entre numa partida. (Ctrl+C para sair)" -ForegroundColor Cyan

$auth       = $null
$campeoes   = $null   # id -> nome
$aberto     = 0       # ultimo campeao cuja pagina ja foi aberta
$candidato  = 0
$desde      = [datetime]::MinValue
$avisouSemCliente = $false

while ($true) {
    try {
        if (-not $auth) {
            $auth = Get-LcuAuth
            if (-not $auth) {
                if (-not $avisouSemCliente) { Write-Host "Esperando o cliente do LoL abrir..." -ForegroundColor DarkGray; $avisouSemCliente = $true }
                Start-Sleep -Seconds 3; continue
            }
            Write-Host "Conectado ao cliente (porta $($auth.Port))." -ForegroundColor Green
            $avisouSemCliente = $false
            $campeoes = $null
        }

        if (-not $campeoes) {
            $campeoes = @{}
            # Nomes em ingles (o METAsrc usa eles; o cliente em PT-BR traduz alguns, ex. "Bardo")
            try {
                $v = (Invoke-RestMethod 'https://ddragon.leagueoflegends.com/api/versions.json' -UseBasicParsing -TimeoutSec 5)[0]
                $dd = Invoke-RestMethod "https://ddragon.leagueoflegends.com/cdn/$v/data/en_US/champion.json" -UseBasicParsing -TimeoutSec 10
                foreach ($p in $dd.data.PSObject.Properties) { $campeoes[[int]$p.Value.key] = $p.Value.name }
            } catch { Write-Host "Nao consegui baixar os nomes em ingles, usando os do cliente." -ForegroundColor DarkGray }
            # Completa com os nomes do cliente (campeoes muito novos)
            foreach ($c in (Invoke-Lcu $auth '/lol-game-data/assets/v1/champion-summary.json')) {
                if ($c.id -gt 0 -and -not $campeoes.ContainsKey([int]$c.id)) { $campeoes[[int]$c.id] = $c.name }
            }
        }

        $sessao = $null
        try { $sessao = Invoke-Lcu $auth '/lol-champ-select/v1/session' } catch {
            $code = $null
            if ($_.Exception.Response) { $code = [int]$_.Exception.Response.StatusCode }
            if ($code -ne 404) { throw }   # 404 = nao esta na selecao de campeoes
        }

        if (-not $sessao) {
            $aberto = 0; $candidato = 0
            Start-Sleep -Seconds 1; continue
        }

        $eu = $sessao.myTeam | Where-Object { $_.cellId -eq $sessao.localPlayerCellId } | Select-Object -First 1
        $champId = 0
        if ($eu) {
            $champId = [int]$eu.championId
            if ($champId -eq 0) { $champId = [int]$eu.championPickIntent }
        }

        if ($champId -ne $candidato) { $candidato = $champId; $desde = Get-Date }

        if ($candidato -gt 0 -and $candidato -ne $aberto -and ((Get-Date) - $desde).TotalSeconds -ge $Espera) {
            $nome = $campeoes[$candidato]
            if ($nome) {
                $url = "$BaseUrl/$(Get-Slug $nome)/build"
                Write-Host "$(Get-Date -Format HH:mm:ss)  $nome -> $url" -ForegroundColor Yellow
                Start-Process $url
            }
            $aberto = $candidato
        }
    } catch {
        # Cliente fechou/reiniciou: descarta a conexao e tenta de novo
        if ($auth) { Write-Host "Conexao com o cliente perdida, tentando de novo..." -ForegroundColor DarkGray }
        $auth = $null
        Start-Sleep -Seconds 3; continue
    }
    Start-Sleep -Milliseconds 700
}
