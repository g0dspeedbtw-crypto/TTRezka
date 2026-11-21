const { contextBridge } = require('electron');

contextBridge.exposeInMainWorld('tikcutDesktop', {
  isDesktop: true,
  platform: process.platform,
});
