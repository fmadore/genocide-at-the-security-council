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

const ROOT = new URL('../src/', import.meta.url).pathname;
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

/** The `question="…"` or `question={…}` prop of one Figure's opening tag. */
function question(openTag) {
	const quoted = openTag.match(/\bquestion="((?:[^"\\]|\\.)*)"/);
	if (quoted) return quoted[1];
	const braced = openTag.match(/\bquestion=\{((?:[^{}]|\{[^{}]*\})*)\}/);
	return braced ? `{${braced[1]}}` : '';
}

function snippet(block, name) {
	const open = block.indexOf(`{#snippet ${name}()}`);
	if (open < 0) return null;
	const close = block.indexOf('{/snippet}', open);
	return block.slice(open + `{#snippet ${name}()}`.length, close);
}

export function figures(source, file) {
	const out = [];
	const re = /<Figure\b/g;
	let match;
	while ((match = re.exec(source))) {
		const openEnd = source.indexOf('>', match.index);
		const closeAt = source.indexOf('</Figure>', openEnd);
		const openTag = source.slice(match.index, openEnd + 1);
		const block = source.slice(openEnd + 1, closeAt);
		const title = (openTag.match(/\btitle="([^"]*)"/) ?? [null, '(untitled)'])[1];
		const counts = { question: words(question(openTag)) };
		for (const name of ['reading', 'caveat', 'more']) {
			const body = snippet(block, name);
			if (body !== null) counts[name] = words(body);
		}
		out.push({ file, title, counts, line: source.slice(0, match.index).split('\n').length });
	}
	return out;
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
