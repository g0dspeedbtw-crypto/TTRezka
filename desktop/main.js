const { app, BrowserWindow, shell, dialog } = require('electron');
const { spawn } = require('child_process');
const http = require('http');
const net = require('net');
const path = require('path');
const fs = require('fs');

let mainWindow = null;
let backendProc = null;

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

  // 1. Packaged PyInstaller binary inside Electron resources
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

  // 2. Local PyInstaller build next to desktop/
  const localBin = path.join(__dirname, 'backend-dist', 'tikcut-backend', exeName);
  if (fs.existsSync(localBin)) {
    return {
      cmd: localBin,
      args: ['--host', '127.0.0.1', '--port', String(port)],
      cwd: path.dirname(localBin),
    };
  }

  // 3. Development fallback: workspace .venv Python
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
    }
  } catch (err) {
    console.error(err);
    dialog.showErrorBox(
      'Ошибка запуска TikCut Studio',
      `Не удалось запустить локальный сервер:\n${err.message}`
    );
  }
}

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', stopBackend);
