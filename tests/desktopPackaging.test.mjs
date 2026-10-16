import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const root = process.cwd();
const read = (path) => readFileSync(join(root, path), "utf8");

const pkg = JSON.parse(read("package.json"));
const mainSource = read("electron/main.ts");
const specSource = read("backend.spec");
const backendMain = read("backend/app/main.py");

assert.ok(
  existsSync(join(root, "electron/assets/icon.ico")),
  "Electron packaging should have electron/assets/icon.ico",
);

assert.equal(
  pkg.scripts["electron:dev"],
  "npm run electron:tsc && electron .",
  "electron:dev should let Electron start its own backend instead of waiting for an external backend",
);

assert.match(
  mainSource,
  /const BACKEND_PORT = 18000;/,
  "Desktop backend should use a dedicated port so it does not collide with the web dev backend",
);
assert.match(
  mainSource,
  /A3_OFFLINE_DEMO:\s*"1"/,
  "Desktop backend should run in offline demo mode by default",
);
assert.match(
  mainSource,
  /fs\.mkdirSync\(userDataDir,\s*\{\s*recursive:\s*true\s*\}\)/,
  "Electron should create the desktop data directory before passing it to SQLite",
);
assert.match(
  mainSource,
  /backendProcess\.stdout\?\.on\("data"[\s\S]*logDesktop\("\[backend:stdout\]"/,
  "Electron should persist packaged backend stdout to the desktop log for blank-window diagnosis",
);
assert.match(
  mainSource,
  /backendProcess\.stderr\?\.on\("data"[\s\S]*logDesktop\("\[backend:stderr\]"/,
  "Electron should persist packaged backend stderr to the desktop log for blank-window diagnosis",
);
assert.match(
  mainSource,
  /backendProcess\.on\("exit"[\s\S]*logDesktop\(`\[backend\] process exit/,
  "Electron should persist packaged backend exit status to the desktop log",
);
assert.match(
  mainSource,
  /webContents\.session\.clearCache\(\)/,
  "Electron should clear the renderer cache before loading the local frontend to avoid stale asset MIME metadata",
);

assert.ok(
  existsSync(join(root, "backend/desktop_entry.py")),
  "PyInstaller should target a desktop entry module that actually starts uvicorn",
);
assert.match(
  read("backend/desktop_entry.py"),
  /uvicorn\.run\(/,
  "Desktop backend entry should call uvicorn.run",
);
assert.match(
  specSource,
  /\["backend\/desktop_entry\.py"\]/,
  "backend.spec should package the desktop backend entry, not backend/app/main.py directly",
);
assert.match(
  specSource,
  /\("frontend\/dist",\s*"frontend\/dist"\)/,
  "backend.spec should include the built Vue frontend in the backend onedir bundle",
);
assert.match(
  backendMain,
  /getattr\(sys,\s*"_MEIPASS"/,
  "FastAPI static frontend lookup should support PyInstaller runtime paths",
);
