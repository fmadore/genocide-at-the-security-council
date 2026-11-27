import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const publicPages = [
	'index.html',
	'chronology/index.html',
	'language/index.html',
	'actors/index.html',
	'concordance/index.html',
	'usage/index.html',
	'semantic/index.html',
	'methods/index.html'
];

const expected = [
	...publicPages,
	'sitemap.xml',
	'robots.txt',
	'llms.txt',
	'data-catalog.json',
	'404.html',
	// The PWA layer, and the same argument. Both fail silently: a missing worker
	// means the site simply stops working offline, and a missing manifest means
	// the install entry quietly disappears from the browser's menu. Neither shows
	// up in a page that renders perfectly well in front of you.
	'manifest.webmanifest',
	'service-worker.js'
];

const absent = (path) => !existsSync(resolve('build', path));

// Checked before the manifest is opened, so that a build without one fails with
// the sentence below rather than with a stack trace from readFileSync.
let missing = expected.filter(absent);

// The manifest's own icon list rather than a second copy of it here. A copy
// would be right on the day it was written and would then sit there agreeing
// with itself while the manifest moved on; this way, adding an icon to the
// manifest without running tools/build_icons.py is the thing that fails.
let icons = [];
if (!missing.length) {
	const manifest = JSON.parse(readFileSync(resolve('build', 'manifest.webmanifest'), 'utf8'));
	icons = manifest.icons.map((icon) => icon.src.replace(/^\.\//, ''));
	missing = icons.filter(absent);
}

if (missing.length) {
	throw new Error(`Static build is missing: ${missing.join(', ')}`);
}

const origin = 'https://fmadore.github.io/genocide-at-the-security-council';
const canonicalFor = (path) =>
	path === 'index.html' ? `${origin}/` : `${origin}/${path.replace(/index\.html$/, '')}`;
const sitemap = readFileSync(resolve('build', 'sitemap.xml'), 'utf8');
const metadataProblems = [];
for (const path of publicPages) {
	const html = readFileSync(resolve('build', path), 'utf8');
	const canonical = canonicalFor(path);
	if (!html.includes(`<link rel="canonical" href="${canonical}"`)) {
		metadataProblems.push(`${path}: canonical`);
	}
	if (!html.includes('<meta name="description" content="')) {
		metadataProblems.push(`${path}: description`);
	}
	if (!html.includes(`<meta property="og:url" content="${canonical}"`)) {
		metadataProblems.push(`${path}: Open Graph URL`);
	}
	if (!sitemap.includes(`<loc>${canonical}</loc>`)) {
		metadataProblems.push(`sitemap.xml: ${canonical}`);
	}
}

const home = readFileSync(resolve('build', 'index.html'), 'utf8');
for (const marker of ['"@type":"SoftwareApplication"', '"@type":"Dataset"', '10.7910/DVN/CKPTRB']) {
	if (!home.includes(marker)) metadataProblems.push(`index.html JSON-LD: ${marker}`);
}
const catalog = JSON.parse(readFileSync(resolve('build', 'data-catalog.json'), 'utf8'));
if (catalog.corpus?.doi !== '10.7910/DVN/CKPTRB' || !Array.isArray(catalog.endpoints)) {
	metadataProblems.push('data-catalog.json: corpus DOI or endpoints');
}
const llms = readFileSync(resolve('build', 'llms.txt'), 'utf8');
if (!llms.includes(`${origin}/data-catalog.json`)) {
	metadataProblems.push('llms.txt: data-catalog.json link');
}
if (metadataProblems.length) {
	throw new Error(`Static discovery metadata is missing: ${metadataProblems.join(', ')}`);
}
console.log(`Verified ${expected.length} static entry points and ${icons.length} manifest icons.`);
