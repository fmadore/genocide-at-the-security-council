import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const expected = [
	'index.html',
	'chronology/index.html',
	'language/index.html',
	'actors/index.html',
	'concordance/index.html',
	'methods/index.html',
	'404.html',
	// Not a route: the polygons the actor view's filled map fetches. It is a
	// committed asset rather than a pipeline artefact, so nothing upstream would
	// notice its absence — the map would simply say the boundaries did not load,
	// in production, to a reader. Rebuild it with tools/build_boundaries.py.
	'geo/countries.json',
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
console.log(`Verified ${expected.length} static entry points and ${icons.length} manifest icons.`);
