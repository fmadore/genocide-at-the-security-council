/** Build the navigation inventory from figure source declarations, including components. */
import { existsSync, readFileSync, readdirSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { provenance } from '../src/lib/figures.ts';
import { parse } from 'svelte/compiler';

const root = fileURLToPath(new URL('../src/', import.meta.url));
function sources(path, seen = new Set()) {
	if (seen.has(path)) return [];
	seen.add(path);
	const source = readFileSync(path, 'utf8');
	const steps = [];
	const figures = [];
	function walk(node) {
		if (!node || typeof node !== 'object') return;
		if (node.type === 'Component' && node.name === 'Figure') figures.push(node);
		for (const value of Object.values(node)) {
			if (Array.isArray(value)) value.forEach(walk);
			else if (value && typeof value === 'object') walk(value);
		}
	}
	walk(parse(source, { modern: true }));
	for (const figure of figures) {
		const declaration = figure.attributes.find((attr) => attr.name === 'source');
		if (!declaration) throw new Error(`Figure has no source: ${path}`);
		let expression = source.slice(declaration.start, declaration.end).replace(/^source=/, '');
		// `source={name}`: read the `$derived` that defines `name` in the same file,
		// whatever it is called (it used to be `profileSource` by name only).
		const named = expression.match(/^\{(\w+)\}$/)?.[1];
		if (named) {
			const definition = new RegExp(String.raw`const ${named} = \$derived\(([\s\S]*?)\);`);
			expression = source.match(definition)?.[1] ?? '';
		}
		provenance(expression); // refuse an unclassifiable source
		steps.push(expression);
	}
	for (const match of source.matchAll(/import\s+\w+\s+from\s+['"]([^'"]+\.svelte)['"]/g)) {
		// `#lib/` is the subpath import package.json declares for src/lib (SvelteKit 3).
		const child = match[1].startsWith('#lib/')
			? join(root, 'lib', match[1].slice(5))
			: join(dirname(path), match[1]);
		if (child.endsWith('Figure.svelte')) continue;
		steps.push(...sources(child, seen));
	}
	return steps;
}
/** Every route directory, nested ones such as `reader/[meeting]` included. */
function routes(directory = join(root, 'routes'), prefix = '') {
	const out = [prefix];
	for (const entry of readdirSync(directory, { withFileTypes: true })) {
		if (entry.isDirectory())
			out.push(
				...routes(join(directory, entry.name), `${prefix}${prefix ? '/' : ''}${entry.name}`)
			);
	}
	return out;
}
const inventory = {};
for (const name of routes()) {
	const path = join(root, 'routes', name, '+page.svelte');
	if (!existsSync(path)) continue;
	const found = sources(path);
	if (found.length) inventory[`/${name}`] = provenance(found.join('; '));
}
const output = join(root, 'lib', 'page-provenance.json');
const content = JSON.stringify(inventory, null, '\t') + '\n';
if (process.argv.includes('--write')) writeFileSync(output, content);
else if (readFileSync(output, 'utf8') !== content) {
	throw new Error(
		'Figure provenance inventory changed; run node scripts/figure-provenance.mjs --write and review the diff'
	);
}
