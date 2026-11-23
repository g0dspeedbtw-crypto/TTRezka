const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('tikcutDesktop', {
  isDesktop: true,
  platform: process.platform,
  getVersion: () => ipcRenderer.invoke('app:version'),
  checkForUpdates: () => ipcRenderer.invoke('updater:check'),
  downloadUpdate: () => ipcRenderer.invoke('updater:download'),
  installUpdate: () => ipcRenderer.invoke('updater:install'),
  openExternal: (url) => ipcRenderer.invoke('app:open-external', url),
  openFolder: (folderPath) => ipcRenderer.invoke('app:open-folder', folderPath),
  onUpdateStatus: (callback) => {
    const handler = (_event, payload) => callback(payload);
    ipcRenderer.on('updater:status', handler);
    return () => ipcRenderer.removeListener('updater:status', handler);
  },
  // Multi-Account Social Studio Bridge (TikTok, YouTube Shorts, Instagram Reels)
  tiktokCheckSession: (accountId) => ipcRenderer.invoke('tiktok:check-session', accountId),
  tiktokOpenLogin: (accountId, accountName) => ipcRenderer.invoke('tiktok:open-login', { accountId, accountName }),
  tiktokUploadClip: (payload) => ipcRenderer.invoke('tiktok:upload-clip', payload),
  socialUploadClip: (payload) => ipcRenderer.invoke('social:upload-clip', payload),
  tiktokLogout: (accountId) => ipcRenderer.invoke('tiktok:logout', accountId),
  onTiktokSessionChanged: (callback) => {
    const handler = (_event, accountId) => callback(accountId);
    ipcRenderer.on('tiktok:session-changed', handler);
    return () => ipcRenderer.removeListener('tiktok:session-changed', handler);
  },
});
