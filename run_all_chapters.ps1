# run_all_chapters.ps1 - batch run chapters 3-10
# Usage: .\run_all_chapters.ps1

$env:MINIMAX_API_KEY = "sk-cp-tBm7dw8K4qRjykS3q7958_-6fnFu80r-hUu2J37kIJuimE8cj2aBKEB5aPXMXCHqmHwyJwY18oi7VseI2bi_8eWdEkowKX8wMvyydBcG_7uPeLvbjVsVTWU"

for ($i = 3; $i -le 10; $i++) {
    $chapter = "input/十日终焉_第${i}章.txt"
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Processing: $chapter" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    python run.py $chapter
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Chapter $i FAILED, exit code: $LASTEXITCODE" -ForegroundColor Red
    } else {
        Write-Host "Chapter $i done" -ForegroundColor Green
    }
    Write-Host ""
}

Write-Host "All chapters done!" -ForegroundColor Green
