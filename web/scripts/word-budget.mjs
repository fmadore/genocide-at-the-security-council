/**
 * The word budget every `Figure` is held to.
 *
 * The review of 1 September 2026 (§5.1) counted about 5,200 words of figure
 * apparatus over twenty figures and found four kinds of prose beside the
 * marks, of which only one — the caveat a reader needs before quoting a
 * number — earns its place there. The remedy it proposed is a budget, and a
 * budget nobody checks is a wish. This script reads every `<Figure>` in
 * `src/` and counts the words in its `question` prop and its `reading` and
 * `caveat` snippets, every conditional branch included, the way the review
 * counted. Anything past the limit fails `npm run lint`.
 *
 *   question  ≤ 20 words   what the figure is here to answer
 *   reading   ≤ 60 words   what the marks encode, what a click does
 *   caveat    ≤ 50 words   the one wrong reading this figure invites
 *
 * Overflow has a place to go: the `more` snippet, rendered as a disclosure in
 * the margin, is not budgeted here but is reported, so a figure cannot hide a
 * lecture behind a summary either — it is capped at 150. Method belongs on
 * Methods behind an anchor; engineering narration belongs nowhere.
 *
 * Counting rule: a `{expression}` is one word, markup is none, and the text of
 * every `{#if}` branch counts, because a reader can meet any of them.
 */
import { readFileSync, readdirSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parse } from 'svelte/compiler';

// Through `fileURLToPath`, not `URL.pathname`: on Windows the latter yields
// `/C:/…`, which `readdirSync` tolerates and `join` does not, so the walk
// found the first directory and then looked for `C:\C:\…` inside it. The
// budget had stopped running for anyone not on the deploy runner, silently,
// because the failure is an ENOENT on a path nobody reads twice.
const ROOT = fileURLToPath(new URL('../src/', import.meta.url));
const BUDGET = { question: 20, reading: 60, caveat: 50, more: 150 };

function* svelteFiles(dir) {
	for (const name of readdirSync(dir)) {
		const path = join(dir, name);
		if (statSync(path).isDirectory()) yield* svelteFiles(path);
		else if (name.endsWith('.svelte') && name !== 'Figure.svelte') yield path;
	}
}

/** Words in a fragment of Svelte markup, by the rule in the header. */
export function words(markup) {
	const text = markup
		.replace(/<!--[\s\S]*?-->/g, ' ')
		.replace(/\{#(if|each|key|await)[^}]*\}/g, ' ')
		.replace(/\{:(else|then|catch)[^}]*\}/g, ' ')
		.replace(/\{\/(if|each|key|await)\}/g, ' ')
		.replace(/\{@(const|render|html)[^}]*\}/g, ' ')
		// A `{expression}` may nest braces (`{count(x)}`, `{a ? { b } : c}`); one
		// level of nesting is enough for what the routes write.
		.replace(/\{(?:[^{}]|\{[^{}]*\})*\}/g, ' X ')
		.replace(/<[^>]+>/g, ' ')
		.replace(/&[a-z]+;|&#\d+;/g, ' ');
	return text.split(/\s+/).filter((w) => /[\p{L}\p{N}]/u.test(w)).length;
}

/** The source text of an attribute's value: quoted text as written, an expression in braces. */
function attributeText(source, attribute) {
	if (!attribute || attribute.value === true) return '';
	const parts = Array.isArray(attribute.value) ? attribute.value : [attribute.value];
	return parts
		.map((part) => (part.type === 'Text' ? part.data : source.slice(part.start, part.end)))
		.join('');
}

/** The markup inside one `{#snippet name()}` of a Figure, or null. */
function snippet(source, figure, name) {
	const block = figure.fragment.nodes.find(
		(node) => node.type === 'SnippetBlock' && node.expression?.name === name
	);
	if (!block) return null;
	const nodes = block.body.nodes;
	return nodes.length ? source.slice(nodes[0].start, nodes.at(-1).end) : '';
}

/**
 * Every `<Figure>` in one file, found by the Svelte parser rather than by
 * string search: `indexOf('>')` ended an opening tag at the first `=>` in a
 * prop such as `download={{ chart: () => … }}` (audit of 19 November 2026).
 */
export function figures(source, file) {
	const found = [];
	(function walk(node) {
		if (!node || typeof node !== 'object') return;
		if (node.type === 'Component' && node.name === 'Figure') found.push(node);
		for (const value of Object.values(node)) {
			if (Array.isArray(value)) value.forEach(walk);
			else if (value && typeof value === 'object') walk(value);
		}
	})(parse(source, { modern: true }));
	return found.map((figure) => {
		const attribute = (name) => figure.attributes.find((attr) => attr.name === name);
		const titled = attribute('title');
		const title =
			titled && Array.isArray(titled.value) && titled.value.every((part) => part.type === 'Text')
				? attributeText(source, titled)
				: '(untitled)';
		const counts = { question: words(attributeText(source, attribute('question'))) };
		for (const name of ['reading', 'caveat', 'more']) {
			const body = snippet(source, figure, name);
			if (body !== null) counts[name] = words(body);
		}
		return { file, title, counts, line: source.slice(0, figure.start).split('\n').length };
	});
}

const found = [];
for (const path of svelteFiles(ROOT)) {
	found.push(...figures(readFileSync(path, 'utf8'), relative(ROOT, path)));
}

let over = 0;
let total = 0;
const rows = [];
for (const figure of found) {
	const parts = [];
	for (const [slot, limit] of Object.entries(BUDGET)) {
		const n = figure.counts[slot];
		if (n === undefined) continue;
		if (slot !== 'more') total += n;
		const flag = n > limit ? ' !' : '';
		if (n > limit) over += 1;
		parts.push(`${slot} ${String(n).padStart(3)}/${limit}${flag}`);
	}
	rows.push(
		`${(figure.file + ':' + figure.line).padEnd(34)} ${figure.title.slice(0, 44).padEnd(44)} ${parts.join('  ')}`
	);
}
console.log(rows.join('\n'));
console.log(`\n${found.length} figures, ${total} words of question + reading + caveat`);
if (over) {
	console.error(
		`\n${over} slot(s) over budget — move overflow to \`more\`, method to Methods, narration nowhere.`
	);
	process.exit(1);
}
