# TikCut Studio — Десктопное приложение (macOS & Windows) для TikTok нарезок 9:16

Полноценное десктопное приложение для **macOS** и **Windows**, которое позволяет:
1. **Вставить ссылку на YouTube видео или запись прошлого стрима (YouTube Live / Twitch VOD / VK)** — ИИ проанализирует транскрипт и карту пересмотров YouTube **без скачивания всего видео**, найдёт лучшие моменты и вырежет **только выбранные 20–55 сек фрагменты**.
2. **Или загрузить локальное видео** (MP4, MOV, MKV, WEBM) с компьютера.
3. Автоматически перевести клипы в формат **9:16 (1080×1920)** (Crop или размытый фон) и наложить **русские авто-субтитры с пословной караоке-подсветкой** красивым шрифтом.

---

## Готовое приложение для macOS
После сборки готовые файлы лежат в папке `desktop/dist/`:
- `desktop/dist/mac-arm64/TikCut Studio.app` — можно сразу запускать двойным кликом или перенести в «Программы» (`/Applications`);
- `desktop/dist/TikCut Studio-1.0.0-arm64.dmg` — установщик `.dmg` для macOS.

## Сборка для Windows (`.exe` установщик и Portable)
У вас есть 2 варианта:
1. **На компьютере с Windows** (нужны Python 3.9–3.12, Node.js 20+ и `ffmpeg` в PATH):
   Запустите двойным кликом `scripts\build_windows.bat` — скрипт автоматически соберёт `desktop\dist\TikCut Studio Setup 1.0.0.exe` и портативную версию `.exe`.
2. **Автоматически через GitHub Actions** (даже без Windows-ПК):
   В проекте уже готов workflow `.github/workflows/build-desktop.yml`, который автоматически собирает сразу **macOS `.dmg`** и **Windows `.exe`**.

## Обновления по воздуху (OTA)
Приложение автоматически проверяет новые релизы на GitHub (`g0dspeedbtw-crypto/TTRezka`) при запуске и по кнопке **«🔄 Обновления»** в верхней панели, скачивает обновление в фоне с индикатором прогресса и предлагает перезапустить приложение для установки.

Чтобы выпустить новую версию для всех пользователей:
1. Поднимите `"version"` в `desktop/package.json` (например, с `"1.0.0"` до `"1.0.1"`).
2. Создайте тег и отправьте на GitHub:
   ```bash
   git add desktop/package.json && git commit -m "Release v1.0.1"
   git tag v1.0.1 && git push origin main --tags
   ```
GitHub Actions сам соберёт macOS + Windows и опубликует GitHub Release — все установленные приложения получат обновление автоматически!

## Режим разработки
- Веб-версия: `./start.sh`
- Десктоп в dev-режиме: `npm --prefix desktop start`
- Пересборка macOS-приложения:
  ```bash
  .venv/bin/python scripts/build_backend.py
  npm --prefix desktop run build:mac
  ```
