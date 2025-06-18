const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const isDev = process.argv.includes('--dev');

let mainWindow;
let pythonProcess;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 800,
    webPreferences: {
      nodeIntegration: false, // Disable Node.js integration in the renderer process
      contextIsolation: true, // Enable context isolation
      preload: path.join(__dirname, 'preload.js'), // Use a preload script
      webSecurity: false, // Only for development
      allowRunningInsecureContent: true // Only for development
    },
    show: false // Don't show until ready-to-show
  });

  // Load the app
  const startUrl = isDev 
    ? 'http://localhost:5173' // Vite dev server
    : `file://${path.join(__dirname, '../dist/index.html')}`; // Production build

  mainWindow.loadURL(startUrl);

  // Open DevTools in development mode
  if (isDev) {
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  }

  // Show window when page is ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    // Check if the dev server is running
    if (isDev) {
      const { exec } = require('child_process');
      exec('netstat -ano | findstr :5173', (error) => {
        if (error) {
          console.warn('Vite dev server not detected. Please run `npm run dev` in the renderer directory.');
        }
      });
    }
  });

  // Start Python backend
  startPythonBackend();

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
    if (pythonProcess) {
      pythonProcess.kill();
      pythonProcess = null;
    }
  });
}

function startPythonBackend() {
  // Kill any existing Python processes
  if (pythonProcess) {
    pythonProcess.kill();
  }

  // Start the Python backend using the virtual environment
  const pythonPath = path.join(__dirname, '..', 'python', 'app.py');
  const pythonExecutable = process.platform === 'win32' 
    ? path.join(__dirname, '..', 'python', 'venv', 'Scripts', 'python.exe')
    : path.join(__dirname, '..', 'python', 'venv', 'bin', 'python');
  
  pythonProcess = spawn(pythonExecutable, [pythonPath], {
    cwd: path.join(__dirname, '..')
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python: ${data}`);
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python Error: ${data}`);
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python process exited with code ${code}`);
    if (code !== 0 && mainWindow) {
      mainWindow.webContents.send('python-error', 'Python backend stopped unexpectedly');
    }
  });
}

// Create window when Electron has finished initialization
app.whenReady().then(createWindow);

// Quit when all windows are closed
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

// Cleanup on quit
app.on('will-quit', () => {
  if (pythonProcess) {
    pythonProcess.kill();
    pythonProcess = null;
  }
});
