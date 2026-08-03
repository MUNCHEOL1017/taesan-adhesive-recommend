$listener = New-Object System.Net.HttpListener
$listener.Prefixes.Add('http://localhost:3458/')
$listener.Start()
Write-Host 'Server running at http://localhost:3458/'

$mimeTypes = @{
    '.html' = 'text/html; charset=utf-8'
    '.htm'  = 'text/html; charset=utf-8'
    '.js'   = 'application/javascript; charset=utf-8'
    '.mjs'  = 'application/javascript; charset=utf-8'
    '.json' = 'application/json; charset=utf-8'
    '.css'  = 'text/css; charset=utf-8'
    '.svg'  = 'image/svg+xml'
    '.png'  = 'image/png'
    '.jpg'  = 'image/jpeg'
    '.jpeg' = 'image/jpeg'
    '.ico'  = 'image/x-icon'
}

while ($listener.IsListening) {
    $ctx = $listener.GetContext()
    try {
        $urlPath = $ctx.Request.Url.AbsolutePath
        if ($urlPath -eq '/') { $urlPath = '/index.html' }
        $relPath = $urlPath.TrimStart('/') -replace '/', [System.IO.Path]::DirectorySeparatorChar
        $filePath = Join-Path $PSScriptRoot $relPath

        if (-not (Test-Path $filePath -PathType Leaf)) {
            $ctx.Response.StatusCode = 404
            $ctx.Response.ContentType = 'text/plain; charset=utf-8'
            $notFoundBytes = [System.Text.Encoding]::UTF8.GetBytes('404 Not Found')
            $ctx.Response.ContentLength64 = $notFoundBytes.Length
            if ($ctx.Request.HttpMethod -ne 'HEAD') {
                $ctx.Response.OutputStream.Write($notFoundBytes, 0, $notFoundBytes.Length)
            }
        } else {
            $ext = [System.IO.Path]::GetExtension($filePath).ToLower()
            $contentType = if ($mimeTypes.ContainsKey($ext)) { $mimeTypes[$ext] } else { 'application/octet-stream' }
            $bytes = [System.IO.File]::ReadAllBytes($filePath)
            $ctx.Response.KeepAlive = $false
            $ctx.Response.SendChunked = $false
            $ctx.Response.ContentType = $contentType
            $ctx.Response.ContentLength64 = $bytes.Length
            if ($ctx.Request.HttpMethod -ne 'HEAD') {
                $ctx.Response.OutputStream.Write($bytes, 0, $bytes.Length)
            }
        }
    } catch {
        Write-Host "Request error: $_"
    } finally {
        $ctx.Response.OutputStream.Close()
    }
}
