/**
 * The small multiples, as geometry and as a file.
 *
 * `SmallMultiples.svelte` draws its rows as markup on the page, where colour
 * is a CSS custom property and the theme switch needs no redraw. That is
 * exactly what a downloaded file cannot have: an `.svg` opened anywhere else
 * has none of this site's CSS, so `var(--reg-legal)` in it is black, or
 * nothing. The figure therefore leaves as a second drawing, written here from
 * the same rows with every colour resolved to a literal — the move `export.ts`
 * makes for the caption it puts under every chart.
 *
 * The review of 19 September 2026 found this plate offering CSV and nothing
 * else, against the commitment that a figure leaves as CSV, SVG and PNG. It is
 * the one plate on the site drawn in markup rather than by ECharts, which is
 * why it was the one left out.
 */

import { escapeXml } from './export';

/** One row of the figure, with its colour already a literal. */
export interface MultiplesRow {
	name: string;
	values: number[];
	colour: string;
	summary: string;
}

/** A period carrying reference dates, by its position on the shared axis. */
export interface MultiplesTick {
	index: number;
	title: string;
}

/** A register and the colour its rows are drawn in. */
export interface MultiplesKey {
	label: string;
	colour: string;
}

/**
 * The points of one row's line, scaled to its own maximum.
 *
 * Shared by the page and the file so the two cannot draw the same row two
 * ways. A flat-zero row would divide by zero; it is drawn on the floor.
 */
export function multiplesPoints(values: number[], width: number, height: number): string {
	const top = Math.max(...values, 0);
	const scale = top > 0 ? top : 1;
	const x = (i: number) => (values.length < 2 ? 0 : (i / (values.length - 1)) * width);
	return values
		.map((v, i) => `${x(i).toFixed(1)},${(height - (v / scale) * (height - 4) - 2).toFixed(1)}`)
		.join(' ');
}

/**
 * The registers the rows are drawn in, once each, in the order the rows first
 * use them. The key names a colour only if a row on the plate wears it.
 */
export function multiplesKey<T extends { register?: string; colour: string }>(
	rows: T[]
): { register: string; colour: string }[] {
	const seen = new Map<string, string>();
	for (const row of rows) {
		if (row.register && !seen.has(row.register)) seen.set(row.register, row.colour);
	}
	return [...seen].map(([register, colour]) => ({ register, colour }));
}

export interface MultiplesSvgRequest {
	rows: MultiplesRow[];
	periods: (string | number)[];
	key: MultiplesKey[];
	ticks: MultiplesTick[];
	ticksLabel: string;
	colours: { ink: string; faint: string; rule: string };
	fontFamily: string;
}

/** The file's geometry, in px. Wider than a phone, narrower than a slide. */
const LAYOUT = {
	width: 900,
	name: 170,
	summary: 70,
	gap: 16,
	key: 28,
	row: 50,
	line: 34,
	rail: 14,
	scale: 18,
	swatch: 10,
	text: 13
};

/**
 * The figure as a standalone `<svg>` document.
 *
 * Laid out as the page lays it out — name, line, summary, then the reference
 * dates on the shared axis — with each row's name in ink behind a square of
 * its colour, and a key above the rows naming the registers the colours stand
 * for. `Download.svelte` puts the caption, the filters and the provenance
 * under it, as it does for every chart.
 */
export function multiplesSvg(request: MultiplesSvgRequest): string {
	const { rows, periods, key, ticks, ticksLabel, colours, fontFamily } = request;
	const L = LAYOUT;
	const plotX = L.name + L.gap;
	const plotWidth = L.width - plotX - L.gap - L.summary;
	const font = escapeXml(fontFamily);
	const text = (x: number, y: number, body: string, attrs = '') =>
		`<text x="${x}" y="${y}" font-family="${font}" font-size="${L.text}" ${attrs}>${escapeXml(body)}</text>`;
	const swatch = (x: number, y: number, colour: string) =>
		`<rect x="${x}" y="${y}" width="${L.swatch}" height="${L.swatch}" fill="${escapeXml(colour)}"/>`;

	const out: string[] = [];

	// The key: a square of each register's colour before its name.
	let cursor = 0;
	for (const entry of key) {
		out.push(swatch(cursor, 9, entry.colour));
		out.push(text(cursor + L.swatch + 6, 18, entry.label, `fill="${escapeXml(colours.faint)}"`));
		cursor += L.swatch + 6 + entry.label.length * 7.5 + 18;
	}

	let y = L.key;
	out.push(
		`<line x1="0" y1="${y}" x2="${L.width}" y2="${y}" stroke="${escapeXml(colours.ink)}" stroke-width="1"/>`
	);
	rows.forEach((row, index) => {
		const top = y + (L.row - L.line) / 2;
		const middle = y + L.row / 2 + 4;
		out.push(swatch(0, middle - 9, row.colour));
		out.push(
			text(L.swatch + 6, middle, row.name, `font-weight="600" fill="${escapeXml(colours.ink)}"`)
		);
		out.push(
			`<polyline transform="translate(${plotX} ${top})" points="${multiplesPoints(row.values, plotWidth, L.line)}" ` +
				`fill="none" stroke="${escapeXml(row.colour)}" stroke-width="1.6" stroke-linejoin="round"/>`
		);
		out.push(
			text(
				L.width,
				middle,
				row.summary,
				`text-anchor="end" fill="${escapeXml(colours.faint)}" font-variant-numeric="tabular-nums"`
			)
		);
		y += L.row;
		const last = index === rows.length - 1;
		out.push(
			`<line x1="0" y1="${y}" x2="${L.width}" y2="${y}" ` +
				`stroke="${escapeXml(last ? colours.ink : colours.rule)}" stroke-width="1"/>`
		);
	});

	if (ticks.length) {
		const x = (i: number) =>
			plotX + (periods.length < 2 ? 0 : (i / (periods.length - 1)) * plotWidth);
		y += 8;
		out.push(text(0, y + 11, ticksLabel, `font-weight="600" fill="${escapeXml(colours.faint)}"`));
		for (const tick of ticks) {
			out.push(
				`<line x1="${x(tick.index).toFixed(1)}" y1="${y}" x2="${x(tick.index).toFixed(1)}" ` +
					`y2="${y + L.rail}" stroke="${escapeXml(colours.faint)}" stroke-width="1">` +
					`<title>${escapeXml(tick.title)}</title></line>`
			);
		}
		const scaleY = y + L.rail + L.scale - 4;
		const mid = Math.floor(periods.length / 2);
		const label = `fill="${escapeXml(colours.faint)}"`;
		out.push(text(x(0), scaleY, String(periods[0] ?? ''), label));
		out.push(text(x(mid), scaleY, String(periods[mid] ?? ''), `text-anchor="middle" ${label}`));
		out.push(
			text(
				x(periods.length - 1),
				scaleY,
				String(periods[periods.length - 1] ?? ''),
				`text-anchor="end" ${label}`
			)
		);
		y += L.rail + L.scale;
	}

	const height = Math.ceil(y + 4);
	return [
		`<svg xmlns="http://www.w3.org/2000/svg" width="${L.width}" height="${height}" ` +
			`viewBox="0 0 ${L.width} ${height}">`,
		...out,
		'</svg>'
	].join('\n');
}
