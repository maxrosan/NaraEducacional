$urls = @(
    "http://76.13.234.11:3000/api/deploy/f0920b38ac1f2576290e771ed6f47ca1237bd287d6afacaf",
    "http://76.13.234.11:3000/api/deploy/b65e9a8716ac3b862d912ccd3b13cd9eac5ee408bfa841fa",
    "http://76.13.234.11:3000/api/deploy/2b6e9f329775671730838f000eeb9aa25e9f4463391b7745",
    "http://76.13.234.11:3000/api/deploy/ef089005d61fb72c872f217cf144eab599e2414a4dfc7f23",
    "http://76.13.234.11:3000/api/deploy/de4fe0f92673d78d058b14a179802e750e728b509acce0cb",
    "http://76.13.234.11:3000/api/deploy/8c12a9d7a7de889b0c4a01266ef959bd2dcc68e241d1461a",
    "http://76.13.234.11:3000/api/deploy/9f890c37cc68bbd5d7fe9b1ee6cfdedb88ed8ea4622801a7",
    "http://76.13.234.11:3000/api/deploy/1d27c5f618ec20d396c2a1696fcabb2429f3ecea5b734c84",
    "http://76.13.234.11:3000/api/deploy/c0bca0bf0c3b7a855dced26daaaa5f1ea0258a33d979dd58",
    "http://76.13.234.11:3000/api/deploy/abf9cf9a8570e97b05e205c61e9d14c534c9db32241a1917"
)

foreach ($url in $urls) {
    try {
        Write-Host "Chamando: $url"
        $response = Invoke-WebRequest -Uri $url -Method GET -TimeoutSec 30
        Write-Host "Status: $($response.StatusCode)"
    }
    catch {
        Write-Host "Erro ao chamar $url"
        Write-Host $_
    }
}