const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('backend', {
  gerarAudios: (pasta, quantidade) => ipcRenderer.invoke('gerar-audios', pasta, quantidade)
});
