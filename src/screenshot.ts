import puppeteer from "puppeteer";
import { resolve } from "path";

const HTML_FILE = resolve(import.meta.dir, "../index.html");
const OUTPUT_FILE = resolve(import.meta.dir, "../screenshot.png");

async function takeScreenshot() {
  const browser = await puppeteer.launch({ headless: true });
  const page = await browser.newPage();

  // Log console messages for debugging
  page.on("console", (msg) => console.log("PAGE LOG:", msg.text()));
  page.on("pageerror", (err) => console.log("PAGE ERROR:", err.message));

  await page.setViewport({ width: 1200, height: 1000 });
  await page.goto(`file://${HTML_FILE}`, { waitUntil: "networkidle0", timeout: 30000 });

  // Wait for Plotly chart to be fully rendered
  await page.waitForFunction(() => {
    const chart = document.querySelector("#chart .plot-container");
    return chart !== null;
  }, { timeout: 10000 });

  await new Promise((r) => setTimeout(r, 2000));

  await page.screenshot({ path: OUTPUT_FILE, fullPage: true });

  await browser.close();
  console.log(`Screenshot saved to ${OUTPUT_FILE}`);
}

takeScreenshot();
