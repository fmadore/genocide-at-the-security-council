import { existsSync } from 'node:fs';
import { resolve } from 'node:path';

const expected = [
	'index.html',
	'chronology/index.html',
	'language/index.html',
	'concordance/index.html',
	'methods/index.html',
	'404.html'
];
const missing = expected.filter((path) => !existsSync(resolve('build', path)));
if (missing.length) {
	throw new Error(`Static build is missing public route(s): ${missing.join(', ')}`);
}
console.log(`Verified ${expected.length} static entry points.`);
