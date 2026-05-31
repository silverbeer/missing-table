// Copy the repo-root CHANGELOG.md into the frontend's static assets so the
// "What's New" page can fetch it at runtime (/changelog.md).
//
// Runs as a pre{dev,serve,build} hook. The repo-root file is outside the
// frontend Docker build context, so CI also copies it explicitly before the
// frontend image build (see .github/workflows/ci.yml). If the source is
// missing (e.g. CHANGELOG.md not on this branch yet), write a placeholder so
// the fetch returns 200 with an empty-state body instead of 404.

import { existsSync, copyFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const source = resolve(here, '../../CHANGELOG.md');
const destDir = resolve(here, '../public');
const dest = resolve(destDir, 'changelog.md');

mkdirSync(destDir, { recursive: true });

if (existsSync(source)) {
  copyFileSync(source, dest);
  console.log(`[copy-changelog] ${source} → ${dest}`);
} else if (existsSync(dest)) {
  // Source not in context (e.g. inside the frontend Docker build, where the
  // repo-root file isn't visible). CI copies CHANGELOG.md into public/ before
  // the build, so keep that copy rather than clobbering it with a placeholder.
  console.log(`[copy-changelog] source missing; keeping existing ${dest}`);
} else {
  writeFileSync(dest, '# Changelog\n\nNo entries yet.\n');
  console.warn(`[copy-changelog] ${source} not found — wrote placeholder.`);
}
