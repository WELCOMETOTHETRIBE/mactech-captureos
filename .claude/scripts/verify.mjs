#!/usr/bin/env node
/**
 * UX verification script. Run by the ux-verifier agent.
 *
 * Usage:
 *   node .claude/scripts/verify.mjs \
 *     --base-url http://localhost:3000 \
 *     --pages /,/dashboard,/settings \
 *     --iteration 1 \
 *     --out .claude/screenshots
 *
 * Outputs:
 *   .claude/screenshots/<iteration>/<page>-<viewport>.png
 *   .claude/screenshots/<iteration>/results.json   (axe + contrast + meta)
 */

import { chromium } from 'playwright';
import AxeBuilder from '@axe-core/playwright';
import { mkdir, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { parseArgs } from 'node:util';

const { values } = parseArgs({
  options: {
    'base-url': { type: 'string', default: 'http://localhost:3000' },
    pages: { type: 'string', default: '/' },
    iteration: { type: 'string', default: '1' },
    out: { type: 'string', default: '.claude/screenshots' },
    'auth-cookie': { type: 'string' }, // e.g. "session=abc123"
  },
});

const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'mobile', width: 375, height: 812 },
];

const baseUrl = values['base-url'].replace(/\/$/, '');
const pages = values.pages.split(',').map((p) => p.trim());
const outDir = join(values.out, values.iteration);
await mkdir(outDir, { recursive: true });

const browser = await chromium.launch();
const results = {
  baseUrl,
  iteration: values.iteration,
  generatedAt: new Date().toISOString(),
  pages: [],
};

for (const path of pages) {
  const pageSlug = path === '/' ? 'root' : path.replace(/^\//, '').replace(/\//g, '_');
  const url = baseUrl + path;
  const pageResult = { path, url, viewports: {}, axe: null, contrast: null };

  for (const vp of VIEWPORTS) {
    const ctx = await browser.newContext({
      viewport: { width: vp.width, height: vp.height },
      deviceScaleFactor: 2,
    });
    if (values['auth-cookie']) {
      const [name, value] = values['auth-cookie'].split('=');
      await ctx.addCookies([
        { name, value, url: baseUrl },
      ]);
    }
    const page = await ctx.newPage();

    try {
      await page.goto(url, { waitUntil: 'networkidle', timeout: 20000 });
      // Settle any post-hydration animation
      await page.waitForTimeout(800);

      const screenshotPath = join(outDir, `${pageSlug}-${vp.name}.png`);
      await page.screenshot({ path: screenshotPath, fullPage: true });
      pageResult.viewports[vp.name] = {
        screenshot: screenshotPath,
        scrollWidth: await page.evaluate(() => document.documentElement.scrollWidth),
        viewportWidth: vp.width,
        horizontalScroll: false, // set below
      };
      pageResult.viewports[vp.name].horizontalScroll =
        pageResult.viewports[vp.name].scrollWidth > vp.width + 1;

      // Run axe + contrast on desktop viewport only (heaviest pass)
      if (vp.name === 'desktop') {
        const axeResults = await new AxeBuilder({ page })
          .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'best-practice'])
          .analyze();

        pageResult.axe = {
          violations: axeResults.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            help: v.help,
            helpUrl: v.helpUrl,
            nodes: v.nodes.slice(0, 5).map((n) => ({
              target: n.target,
              html: n.html.slice(0, 200),
              failureSummary: n.failureSummary,
            })),
            nodeCount: v.nodes.length,
          })),
          counts: {
            critical: axeResults.violations.filter((v) => v.impact === 'critical').length,
            serious: axeResults.violations.filter((v) => v.impact === 'serious').length,
            moderate: axeResults.violations.filter((v) => v.impact === 'moderate').length,
            minor: axeResults.violations.filter((v) => v.impact === 'minor').length,
          },
        };

        // Independent contrast scan — axe catches most but not all (esp. translucent)
        pageResult.contrast = await page.evaluate(() => {
          const parseRgb = (str) => {
            const m = str.match(/rgba?\(([^)]+)\)/);
            if (!m) return null;
            const parts = m[1].split(',').map((s) => parseFloat(s.trim()));
            return { r: parts[0], g: parts[1], b: parts[2], a: parts[3] ?? 1 };
          };
          const lum = ({ r, g, b }) => {
            const f = (c) => {
              c /= 255;
              return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
            };
            return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
          };
          const ratio = (a, b) => {
            const L1 = lum(a), L2 = lum(b);
            return (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
          };
          // Walk through a body-bg composite — naive but catches bad text-on-glass cases
          const findBgChain = (el) => {
            let node = el;
            const stack = [];
            while (node && node !== document.documentElement) {
              const cs = getComputedStyle(node);
              const bg = parseRgb(cs.backgroundColor);
              if (bg && bg.a > 0) stack.push(bg);
              node = node.parentElement;
            }
            stack.push({ r: 255, g: 255, b: 255, a: 1 }); // assume white page bg fallback
            // Composite top-down
            return stack.reverse().reduce((acc, layer) => {
              const a = layer.a;
              return {
                r: acc.r * (1 - a) + layer.r * a,
                g: acc.g * (1 - a) + layer.g * a,
                b: acc.b * (1 - a) + layer.b * a,
              };
            }, { r: 255, g: 255, b: 255 });
          };

          const failures = [];
          const nodes = document.querySelectorAll('p, span, a, button, h1, h2, h3, h4, h5, h6, label, li, td, th');
          let checked = 0;
          for (const el of nodes) {
            if (checked > 300) break; // cap perf
            const text = (el.innerText || '').trim();
            if (!text || text.length < 2) continue;
            const cs = getComputedStyle(el);
            const fg = parseRgb(cs.color);
            if (!fg) continue;
            const bg = findBgChain(el);
            const r = ratio(fg, bg);
            const sizePx = parseFloat(cs.fontSize);
            const bold = parseInt(cs.fontWeight) >= 700;
            const isLarge = sizePx >= 24 || (sizePx >= 18.66 && bold);
            const threshold = isLarge ? 3 : 4.5;
            if (r < threshold) {
              failures.push({
                tag: el.tagName.toLowerCase(),
                text: text.slice(0, 60),
                ratio: Math.round(r * 100) / 100,
                threshold,
                fontSize: sizePx,
                bold,
                selector: el.id ? `#${el.id}` : `${el.tagName.toLowerCase()}.${(el.className || '').toString().split(' ').filter(Boolean).slice(0, 2).join('.')}`,
              });
            }
            checked++;
          }
          return { checked, failures: failures.slice(0, 50), failureCount: failures.length };
        });

        // Focus indicator probe — tab through first 10 focusables
        pageResult.focusIndicators = await page.evaluate(() => {
          const focusables = document.querySelectorAll('a, button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
          const sample = Array.from(focusables).slice(0, 10);
          const results = [];
          for (const el of sample) {
            el.focus();
            const cs = getComputedStyle(el);
            const hasOutline = cs.outlineStyle !== 'none' && cs.outlineWidth !== '0px';
            const hasBoxShadow = cs.boxShadow !== 'none';
            results.push({
              tag: el.tagName.toLowerCase(),
              hasFocusIndicator: hasOutline || hasBoxShadow,
            });
          }
          return {
            sampled: results.length,
            withIndicator: results.filter((r) => r.hasFocusIndicator).length,
            without: results.filter((r) => !r.hasFocusIndicator).length,
          };
        });
      }
    } catch (err) {
      pageResult.viewports[vp.name] = { error: err.message };
    } finally {
      await ctx.close();
    }
  }

  results.pages.push(pageResult);
}

await browser.close();
await writeFile(join(outDir, 'results.json'), JSON.stringify(results, null, 2));
console.log(`Verification complete. Results: ${join(outDir, 'results.json')}`);
console.log(`Pages tested: ${results.pages.length}`);
const totalCritical = results.pages.reduce((s, p) => s + (p.axe?.counts.critical ?? 0), 0);
const totalSerious = results.pages.reduce((s, p) => s + (p.axe?.counts.serious ?? 0), 0);
const totalContrast = results.pages.reduce((s, p) => s + (p.contrast?.failureCount ?? 0), 0);
console.log(`Critical a11y: ${totalCritical} | Serious: ${totalSerious} | Contrast failures: ${totalContrast}`);
