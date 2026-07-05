// Minimal chromium-cli-style driver for this repo (chromium-cli itself isn't
// installed in this environment). Reads newline-separated commands from
// stdin and drives a headless Playwright Chromium page.
//
// Commands:
//   nav <url>                          goto (relative paths resolve against BASE_URL)
//   wait-for text=<substring>           wait until page contains text
//   wait-for <css selector>             wait until selector is visible
//   fill <css selector> <value...>      fill an input (React-safe, uses Playwright's pipeline)
//   set-files <css selector> <path>     set a file input's value
//   click <css selector or text=...>    click
//   press <key>                         press a key on the focused element
//   screenshot [name]                   full-page screenshot -> screenshots/<name|seq>.png
//   eval <js>                           page.evaluate(js) and print the result
//   console-errors                      print collected console/page errors so far
//   sleep <ms>                          last resort, avoid if wait-for works
//
// Usage:
//   node driver.mjs <<'EOF'
//   nav /login
//   fill input[name="email"] icaro@registro.local
//   fill input[name="password"] Registro@123
//   click button[type="submit"]
//   wait-for text=Dashboard
//   screenshot dashboard
//   EOF

import { chromium } from "playwright";
import fs from "node:fs";
import readline from "node:readline";

const BASE = process.env.BASE_URL ?? "http://localhost:3000";
const SHOT_DIR = process.env.SHOT_DIR ?? "./screenshots";
fs.mkdirSync(SHOT_DIR, { recursive: true });

const browser = await chromium.launch({ headless: true, args: ["--no-sandbox"] });
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (msg) => {
  if (msg.type() === "error") errors.push(msg.text());
});

let shotSeq = 0;

function resolveSelector(sel) {
  if (sel.startsWith("text=")) return `text=${sel.slice(5)}`;
  return sel;
}

async function runLine(line) {
  const trimmed = line.trim();
  if (!trimmed || trimmed.startsWith("#")) return;
  const [cmd, ...rest] = trimmed.split(" ");
  const arg = rest.join(" ");

  switch (cmd) {
    case "nav": {
      const url = arg.startsWith("http") ? arg : `${BASE}${arg}`;
      await page.goto(url);
      console.log("nav ->", page.url());
      break;
    }
    case "wait-for": {
      if (arg.startsWith("text=")) {
        await page.waitForSelector(`text=${arg.slice(5)}`, { timeout: 15000 });
      } else {
        await page.waitForSelector(arg, { state: "visible", timeout: 15000 });
      }
      console.log("wait-for ok:", arg);
      break;
    }
    case "fill": {
      const [sel, ...valueParts] = rest;
      await page.fill(resolveSelector(sel), valueParts.join(" "));
      console.log("fill ok:", sel);
      break;
    }
    case "set-files": {
      const [sel, filePath] = rest;
      await page.setInputFiles(resolveSelector(sel), filePath);
      console.log("set-files ok:", sel, filePath);
      break;
    }
    case "click": {
      await page.click(resolveSelector(arg));
      console.log("click ok:", arg);
      break;
    }
    case "press": {
      await page.keyboard.press(arg);
      console.log("press ok:", arg);
      break;
    }
    case "screenshot": {
      const name = arg || String(shotSeq++).padStart(2, "0");
      const path = `${SHOT_DIR}/${name}.png`;
      await page.screenshot({ path, fullPage: true });
      console.log("screenshot:", path);
      break;
    }
    case "eval": {
      const result = await page.evaluate(arg);
      console.log("eval ->", result);
      break;
    }
    case "console-errors": {
      console.log("console-errors:", errors.length ? errors : "(none)");
      break;
    }
    case "sleep": {
      await new Promise((r) => setTimeout(r, Number(arg)));
      break;
    }
    default:
      console.error("unknown command:", cmd);
  }
}

const rl = readline.createInterface({ input: process.stdin });
for await (const line of rl) {
  try {
    await runLine(line);
  } catch (err) {
    console.error("ERROR on line:", line, "->", err.message);
    console.log("console-errors so far:", errors);
    await browser.close();
    process.exit(1);
  }
}

await browser.close();
