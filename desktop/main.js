const { app, BrowserWindow, shell, dialog, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('child_process');
const http = require('http');
const https = require('https');
const net = require('net');
const path = require('path');
const fs = require('fs');

const GITHUB_REPO = 'g0dspeedbtw-crypto/TTRezka';
const RELEASES_URL = `https://github.com/${GITHUB_REPO}/releases/latest`;

let mainWindow = null;
let backendProc = null;
let latestFallbackUrl = RELEASES_URL;

function sendUpdateStatus(payload) {
  if (mainWindow && !mainWindow.isDestroyed()) {
    mainWindow.webContents.send('updater:status', payload);
  }
}

function compareSemver(a, b) {
  const pa = String(a || '0').replace(/^v/, '').split('.').map((n) => parseInt(n, 10) || 0);
  const pb = String(b || '0').replace(/^v/, '').split('.').map((n) => parseInt(n, 10) || 0);
  for (let i = 0; i < Math.max(pa.length, pb.length); i++) {
    const da = pa[i] || 0;
    const db = pb[i] || 0;
    if (da > db) return 1;
    if (da < db) return -1;
  }
  return 0;
}

function fetchLatestGithubRelease() {
  return new Promise((resolve, reject) => {
    const req = https.get(
      `https://api.github.com/repos/${GITHUB_REPO}/releases/latest`,
      { headers: { 'User-Agent': 'TikCut-Studio-Updater' } },
      (res) => {
        let body = '';
        res.on('data', (chunk) => { body += chunk; });
        res.on('end', () => {
          if (res.statusCode === 404) {
            return resolve(null);
          }
          if (res.statusCode !== 200) {
            return reject(new Error(`GitHub API HTTP ${res.statusCode}`));
          }
          try {
            resolve(JSON.parse(body));
          } catch (e) {
            reject(e);
          }
        });
      }
    );
    req.on('error', reject);
    req.setTimeout(10000, () => {
      req.destroy();
      reject(new Error('Таймаут подключения к GitHub'));
    });
  });
}

function setupAutoUpdater() {
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on('checking-for-update', () => {
    sendUpdateStatus({
      state: 'checking',
      currentVersion: app.getVersion(),
      message: 'Проверка обновлений на GitHub...',
    });
  });

  autoUpdater.on('update-available', async (info) => {
    let notes = '';
    if (typeof info.releaseNotes === 'string') {
      notes = info.releaseNotes;
    } else if (Array.isArray(info.releaseNotes)) {
      notes = info.releaseNotes.map((n) => n.note || '').join('\n');
    }
    if (!notes) {
      try {
        const rel = await fetchLatestGithubRelease();
        if (rel && rel.body) notes = rel.body;
      } catch (_) {}
    }
    sendUpdateStatus({
      state: 'available',
      currentVersion: app.getVersion(),
      version: info.version,
      releaseNotes: notes,
      message: `Доступна новая версия v${info.version} — начинаем загрузку...`,
    });
  });

  autoUpdater.on('update-not-available', (info) => {
    sendUpdateStatus({
      state: 'up-to-date',
      currentVersion: app.getVersion(),
      version: info?.version || app.getVersion(),
      message: `У вас установлена последняя версия v${app.getVersion()}`,
    });
  });

  autoUpdater.on('download-progress', (prog) => {
    const pct = Math.round(prog.percent || 0);
    const speedMb = ((prog.bytesPerSecond || 0) / (1024 * 1024)).toFixed(1);
    const doneMb = ((prog.transferred || 0) / (1024 * 1024)).toFixed(1);
    const totalMb = ((prog.total || 0) / (1024 * 1024)).toFixed(1);
    sendUpdateStatus({
      state: 'downloading',
      currentVersion: app.getVersion(),
      percent: pct,
      speedMb,
      doneMb,
      totalMb,
      message: `Загрузка обновления: ${pct}% (${doneMb} / ${totalMb} МБ • ${speedMb} МБ/с)`,
    });
  });

  autoUpdater.on('update-downloaded', (info) => {
    sendUpdateStatus({
      state: 'downloaded',
      currentVersion: app.getVersion(),
      version: info.version,
      message: `Обновление v${info.version} загружено и готово к установке!`,
    });
  });

  autoUpdater.on('error', async (err) => {
    console.warn('[updater] autoUpdater error, checking GitHub API fallback:', err?.message);
    try {
      const rel = await fetchLatestGithubRelease();
      if (rel && rel.tag_name && compareSemver(rel.tag_name, app.getVersion()) > 0) {
        const ver = rel.tag_name.replace(/^v/, '');
        latestFallbackUrl = rel.html_url || RELEASES_URL;
        // Try to pick direct .dmg (mac) or Setup.exe (win) download link
        const assets = rel.assets || [];
        const directAsset = assets.find((a) => {
          const n = (a.name || '').toLowerCase();
          if (process.platform === 'darwin') return n.endsWith('.dmg');
          if (process.platform === 'win32') return n.includes('setup') && n.endsWith('.exe');
          return false;
        });
        if (directAsset && directAsset.browser_download_url) {
          latestFallbackUrl = directAsset.browser_download_url;
        }
        sendUpdateStatus({
          state: 'manual-download',
          currentVersion: app.getVersion(),
          version: ver,
          releaseNotes: rel.body || '',
          releaseUrl: latestFallbackUrl,
          message: `Доступно обновление v${ver}`,
        });
        return;
      }
      sendUpdateStatus({
        state: 'up-to-date',
        currentVersion: app.getVersion(),
        version: app.getVersion(),
        message: `У вас установлена актуальная версия v${app.getVersion()}`,
      });
    } catch (_) {
      sendUpdateStatus({
        state: 'error',
        currentVersion: app.getVersion(),
        message: 'Не удалось проверить обновления (проверьте интернет)',
      });
    }
  });
}

async function triggerUpdateCheck(silent = false) {
  if (!silent) {
    sendUpdateStatus({ state: 'checking', message: 'Проверка обновлений...' });
  }
  if (!app.isPackaged) {
    // In dev mode, check GitHub Releases API directly
    try {
      const rel = await fetchLatestGithubRelease();
      if (rel && rel.tag_name && compareSemver(rel.tag_name, app.getVersion()) > 0) {
        const ver = rel.tag_name.replace(/^v/, '');
        latestFallbackUrl = rel.html_url || RELEASES_URL;
        sendUpdateStatus({
          state: 'manual-download',
          version: ver,
          releaseUrl: latestFallbackUrl,
          message: `Доступно обновление v${ver}`,
        });
      } else if (!silent) {
        sendUpdateStatus({
          state: 'up-to-date',
          version: app.getVersion(),
          message: `Установлена последняя версия (v${app.getVersion()})`,
        });
      }
    } catch (_) {
      if (!silent) {
        sendUpdateStatus({ state: 'error', message: 'Не удалось проверить обновления' });
      }
    }
    return;
  }

  try {
    await autoUpdater.checkForUpdates();
  } catch (err) {
    console.warn('[updater] checkForUpdates threw:', err?.message);
  }
}

function findFreePort() {
  return new Promise((resolve, reject) => {
    const srv = net.createServer();
    srv.unref();
    srv.on('error', reject);
    srv.listen(0, '127.0.0.1', () => {
      const { port } = srv.address();
      srv.close(() => resolve(port));
    });
  });
}

function waitForBackend(port, timeoutMs = 45000) {
  const started = Date.now();
  return new Promise((resolve, reject) => {
    const check = () => {
      const req = http.get(`http://127.0.0.1:${port}/api/health`, (res) => {
        if (res.statusCode === 200) {
          res.resume();
          return resolve();
        }
        res.resume();
        retry();
      });
      req.on('error', retry);
      req.setTimeout(1000, () => {
        req.destroy();
        retry();
      });
    };
    const retry = () => {
      if (Date.now() - started > timeoutMs) {
        return reject(new Error('Таймаут запуска локального сервера TikCut Studio'));
      }
      setTimeout(check, 300);
    };
    check();
  });
}

function resolveBackendCommand(port) {
  const isWin = process.platform === 'win32';
  const exeName = isWin ? 'tikcut-backend.exe' : 'tikcut-backend';

  const packagedBin = path.join(
    process.resourcesPath,
    'backend-dist',
    'tikcut-backend',
    exeName
  );
  if (fs.existsSync(packagedBin)) {
    return {
      cmd: packagedBin,
      args: ['--host', '127.0.0.1', '--port', String(port)],
      cwd: path.dirname(packagedBin),
    };
  }

  const localBin = path.join(__dirname, 'backend-dist', 'tikcut-backend', exeName);
  if (fs.existsSync(localBin)) {
    return {
      cmd: localBin,
      args: ['--host', '127.0.0.1', '--port', String(port)],
      cwd: path.dirname(localBin),
    };
  }

  const rootDir = path.resolve(__dirname, '..');
  const venvPy = isWin
    ? path.join(rootDir, '.venv', 'Scripts', 'python.exe')
    : path.join(rootDir, '.venv', 'bin', 'python');
  const pyCmd = fs.existsSync(venvPy) ? venvPy : isWin ? 'python' : 'python3';

  return {
    cmd: pyCmd,
    args: [path.join(rootDir, 'backend', 'server_entry.py'), '--host', '127.0.0.1', '--port', String(port)],
    cwd: rootDir,
  };
}

function startBackend(port) {
  const { cmd, args, cwd } = resolveBackendCommand(port);
  const dataDir = path.join(app.getPath('userData'), 'data');
  fs.mkdirSync(dataDir, { recursive: true });

  const env = { ...process.env, TIKCUT_DATA_DIR: dataDir };
  if (process.platform === 'darwin') {
    const extraPaths = ['/opt/homebrew/bin', '/usr/local/bin', '/usr/bin', '/bin'];
    env.PATH = [...extraPaths, env.PATH || ''].join(':');
  }

  backendProc = spawn(cmd, args, {
    cwd,
    env,
    stdio: ['ignore', 'pipe', 'pipe'],
  });

  backendProc.stdout.on('data', (d) => process.stdout.write(`[backend] ${d}`));
  backendProc.stderr.on('data', (d) => process.stderr.write(`[backend] ${d}`));

  backendProc.on('exit', (code) => {
    console.log(`[backend] exited with code ${code}`);
    backendProc = null;
  });
}

function stopBackend() {
  if (!backendProc) return;
  try {
    backendProc.kill('SIGTERM');
  } catch (_) {}
  backendProc = null;
}

ipcMain.handle('app:version', () => app.getVersion());
ipcMain.handle('app:open-external', (_e, url) => shell.openExternal(url || latestFallbackUrl));
ipcMain.handle('updater:check', () => triggerUpdateCheck(false));
ipcMain.handle('updater:download', () => autoUpdater.downloadUpdate());
ipcMain.handle('updater:install', () => {
  stopBackend();
  autoUpdater.quitAndInstall(false, true);
});

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1360,
    height: 880,
    minWidth: 960,
    minHeight: 680,
    backgroundColor: '#08090f',
    title: 'TikCut Studio',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    icon: path.join(__dirname, 'assets', process.platform === 'win32' ? 'icon.ico' : 'icon.png'),
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  await mainWindow.loadFile(path.join(__dirname, 'splash.html'));

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  try {
    const port = await findFreePort();
    startBackend(port);
    await waitForBackend(port);
    if (mainWindow) {
      await mainWindow.loadURL(`http://127.0.0.1:${port}`);
      // Auto-check for OTA updates 4 seconds after launch & every 30 minutes
      setTimeout(() => triggerUpdateCheck(true), 4000);
      setInterval(() => triggerUpdateCheck(true), 30 * 60 * 1000);
    }
  } catch (err) {
    console.error(err);
    dialog.showErrorBox(
      'Ошибка запуска TikCut Studio',
      `Не удалось запустить локальный сервер:\n${err.message}`
    );
  }
}

app.whenReady().then(() => {
  setupAutoUpdater();
  createWindow();
});

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', stopBackend);
