const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

function createWindow() {
  const win = new BrowserWindow({
    width: 800,
    height: 600,
    webPreferences: {
      preload: path.join(__dirname, 'frontend/preload.js'),
      contextIsolation: true
    }
  });

  win.loadFile('frontend/index.html');
}

ipcMain.handle('gerar-audios', async (event, pasta, quantidade) => {
  return new Promise((resolve, reject) => {
    const process = spawn('python', ['backend/app.py', pasta, quantidade]);

    let output = '';
    let error = '';

    process.stdout.on('data', data => {
      output += data.toString();
    });

    process.stderr.on('data', data => {
      error += data.toString();
    });

    process.on('close', code => {
      if (code === 0) {
        resolve(output);
      } else {
        reject(error || 'Erro ao executar script Python');
      }
    });
  });
});

app.whenReady().then(createWindow);
