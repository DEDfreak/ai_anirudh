const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const isDev = require('electron-is-dev');

let pythonProcess = null;

function createPythonProcess() {
  // Use process.resourcesPath in production
  let backendExe;
  // if (app.isPackaged) {
  //   backendExe = path.join(process.resourcesPath, 'python', 'app.exe');
  // } else {
  //   backendExe = path.join(__dirname, '..', 'python', 'dist', 'app.exe');
  // }

  console.log('Starting Python process...');
  backendExe = path.join(__dirname, '..', 'python', 'dist', 'app.exe');

  pythonProcess = spawn(backendExe, [], {
    cwd: path.dirname(backendExe),
    stdio: 'inherit'
  });

  pythonProcess.on('error', (err) => {
    console.error('Failed to start Python process.', err);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
  });
}

function createWindow() {
  const win = new BrowserWindow({
    width: 1400,
    height: 900,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
    }
  });

  let indexPath;
  if (app.isPackaged) {
    indexPath = path.join(process.resourcesPath, 'renderer', 'dist', 'index.html');
  } else {
    indexPath = path.join(__dirname, '..', 'renderer', 'dist', 'index.html');
  }
  win.loadFile(indexPath);

  if (isDev) {
    win.webContents.openDevTools();
  }
}

app.whenReady().then(() => {
  console.log('App is ready');
  console.log('Starting Python backend...');
  createPythonProcess();
  console.log('Creating browser window...');
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('quit', () => {
  console.log('Terminating Python process...');
  if (pythonProcess) {
    pythonProcess.kill('SIGTERM');
    pythonProcess = null;
  }
});