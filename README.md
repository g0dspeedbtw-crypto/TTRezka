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

## Режим разработки
- Веб-версия: `./start.sh`
- Десктоп в dev-режиме: `npm --prefix desktop start`
- Пересборка macOS-приложения:
  ```bash
  .venv/bin/python scripts/build_backend.py
  npm --prefix desktop run build:mac
  ```
