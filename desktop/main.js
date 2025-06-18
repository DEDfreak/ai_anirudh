const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const dotenv = require('dotenv');

const isPackaged = app.isPackaged;
let pythonProcess = null;

function createPythonProcess() {
  const pythonExePath = isPackaged
    ? path.join(process.resourcesPath, 'app', 'backend_dist', 'app.exe')
    : path.join(__dirname, '..', 'backend_dist', 'app.exe');

  const envPath = isPackaged
    ? path.join(process.resourcesPath, 'app', 'backend_dist', '.env')
    : path.join(__dirname, '..', 'python', '.env');

  console.log(`[Electron] Development mode: ${!isPackaged}`);
  console.log(`[Electron] Python executable path: ${pythonExePath}`);
  console.log(`[Electron] .env path: ${envPath}`);

  const envVars = dotenv.config({ path: envPath }).parsed || {};

  console.log('[Electron] Starting Python backend...');

  pythonProcess = spawn(pythonExePath, [], {
    env: { ...process.env, ...envVars }
  });

  pythonProcess.stdout.on('data', (data) => console.log(`[Python Backend]: ${data.toString()}`));
  pythonProcess.stderr.on('data', (data) => console.error(`[Python Backend ERR]: ${data.toString()}`));
  pythonProcess.on('close', (code) => {
    console.log(`[Electron] Python backend process exited with code ${code}`);
    pythonProcess = null;
  });
}

function createWindow() {
  const mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    },
  });

  if (isPackaged) {
    // This is the corrected path for the packaged application.
    mainWindow.loadFile(path.join(__dirname, 'renderer', 'dist', 'index.html'));
  } else {
    // This loads from the Vite dev server for `npm start`.
    // You must run the Vite dev server from the `desktop/renderer` directory.
    mainWindow.loadURL('http://localhost:5173'); 
    mainWindow.webContents.openDevTools();
  }
}

app.on('ready', () => {
  createPythonProcess();
  createWindow();
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});