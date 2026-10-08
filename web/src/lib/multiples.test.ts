import { describe, expect, it } from 'vitest';
import { multiplesKey, multiplesPoints, multiplesSvg } from './multiples';

const colours = { ink: '#111111', faint: '#6b6b6b', rule: '#cfcfcf' };

const request = {
	rows: [
		{ name: 'genocide', values: [0, 0.02, 0.05], colour: '#111111', summary: '2.47%' },
		{ name: 'war crimes', values: [0.01, 0.03, 0.02], colour: '#2c7069', summary: '2.88%' }
	],
	periods: [1946, 1985, 2024],
	key: [
		{ label: 'core', colour: '#111111' },
		{ label: 'legal', colour: '#2c7069' }
	],
	ticks: [{ index: 1, title: '1985 — a date & a <label>' }],
	ticksLabel: '59 reference dates in 40 years',
	colours,
	fontFamily: 'Hanken Grotesk, sans-serif'
};

describe('the small multiples as a file', () => {
	it('scales a row to its own maximum and draws a flat-zero row on the floor', () => {
		expect(multiplesPoints([0, 5, 10], 600, 34)).toBe('0.0,32.0 300.0,17.0 600.0,2.0');
		expect(multiplesPoints([0, 0], 600, 34)).toBe('0.0,32.0 600.0,32.0');
	});

	it('names each register once, in the order the rows first wear it', () => {
		const key = multiplesKey([
			{ register: 'core', colour: 'a' },
			{ register: 'legal', colour: 'b' },
			{ register: 'legal', colour: 'b' },
			{ colour: 'c' }
		]);
		expect(key).toEqual([
			{ register: 'core', colour: 'a' },
			{ register: 'legal', colour: 'b' }
		]);
	});

	it('writes a standalone document with every colour a literal', () => {
		const svg = multiplesSvg(request);
		expect(svg.startsWith('<svg xmlns="http://www.w3.org/2000/svg"')).toBe(true);
		expect(svg).toMatch(/width="900" height="\d+"/);
		// A file read with none of the site's CSS: no custom property may survive.
		expect(svg).not.toContain('var(');
		expect(svg).toContain('stroke="#2c7069"');
	});

	it('carries the key, every row, and the reference dates with their label', () => {
		const svg = multiplesSvg(request);
		for (const text of ['core', 'legal', 'genocide', 'war crimes', '2.47%', '2.88%']) {
			expect(svg).toContain(`>${text}</text>`);
		}
		expect(svg).toContain('59 reference dates in 40 years');
		expect(svg.match(/<polyline/g)).toHaveLength(2);
		expect(svg).toContain('>1946</text>');
		expect(svg).toContain('>2024</text>');
	});

	it('escapes what it was handed rather than writing it as markup', () => {
		const svg = multiplesSvg(request);
		expect(svg).toContain('<title>1985 — a date &amp; a &lt;label&gt;</title>');
		expect(svg).not.toContain('<label>');
	});

	it('leaves the reference-date rail out when there are no dates', () => {
		const svg = multiplesSvg({ ...request, ticks: [] });
		expect(svg).not.toContain('59 reference dates');
		expect(svg).not.toContain('<title>');
	});
});
