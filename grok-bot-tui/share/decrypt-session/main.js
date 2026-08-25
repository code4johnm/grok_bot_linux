"use strict";
const { app, safeStorage } = require("electron");
const fs = require("fs");
const os = require("os");
const path = require("path");

const logPath = process.env.GB_DECRYPT_LOG || "";
const tokenOut = process.env.GB_DECRYPT_TOKEN_OUT || "";
const secretsPath =
  process.env.GB_SECRETS_PATH ||
  path.join(os.homedir(), ".config", "Grok Bot", "sand-secrets.json");

function log(msg) {
  if (!logPath) return;
  try {
    fs.appendFileSync(logPath, String(msg) + "\n");
  } catch (_) {}
}

app.setName("Grok Bot");
const userData =
  process.env.GB_USER_DATA || path.join(os.homedir(), ".config", "Grok Bot");
app.setPath("userData", userData);
app.commandLine.appendSwitch("headless");
app.disableHardwareAcceleration();

app.whenReady().then(() => {
  try {
    if (!safeStorage.isEncryptionAvailable()) {
      log("unavailable");
      app.exit(2);
      return;
    }
    const raw = JSON.parse(fs.readFileSync(secretsPath, "utf8"));
    const acc = JSON.parse(raw["cursor-accounts"]);
    const active = acc.active;
    const slot = (acc.accounts && (acc.accounts[active] || Object.values(acc.accounts)[0])) || {};
    const blob = slot["cursor-access-token"];
    if (!blob) {
      log("no-blob");
      app.exit(3);
      return;
    }
    const token = safeStorage.decryptString(Buffer.from(blob, "base64"));
    if (!token || token.length < 16) {
      log("empty");
      app.exit(4);
      return;
    }
    if (!tokenOut) {
      log("no-out");
      app.exit(5);
      return;
    }
    fs.writeFileSync(tokenOut, token, { mode: 0o600 });
    log("ok");
    app.exit(0);
  } catch (err) {
    log("err=" + (err && err.message ? err.message : String(err)));
    app.exit(1);
  }
});

setTimeout(() => app.exit(1), 10000);
