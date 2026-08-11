import { existsSync } from 'node:fs';
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
	'geo/countries.json'
];
const missing = expected.filter((path) => !existsSync(resolve('build', path)));
if (missing.length) {
	throw new Error(`Static build is missing: ${missing.join(', ')}`);
}
console.log(`Verified ${expected.length} static entry points.`);
