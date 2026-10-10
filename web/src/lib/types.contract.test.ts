/**
 * The third writing of the artefact contract, held to the first.
 *
 * The shape of every artefact is written three times: by the Python that emits
 * it, by `types.ts`, which declares it, and by the validators in `data.ts` that
 * refuse it at the fetch. `scripts/lib/contract.py` reduces the first to a
 * skeleton, and `export_web.py` refuses a payload that has drifted from
 * `tests/contract/payload.json`; `contract.test.ts` holds what `data.ts`
 * requires to that skeleton. Nothing held `types.ts` to it, and `types.ts` is
 * what every figure is written against. A field could be declared there under a
 * name the pipeline never wrote, as present on every row when some rows omit
 * it, or as a number where the pipeline writes a null, and `svelte-check` would
 * pass all three, because the JSON is cast at the fetch rather than parsed. The
 * failure was the one the file's own header warned of: a blank chart.
 *
 * Generating `types.ts` from the skeleton would close that gap and throw away
 * the reason the file is worth reading. A skeleton knows that `speech_rate` is
 * `float|null`; it does not know why the null is there or what a figure owes a
 * reader when it meets one, and that is most of what the interfaces say. So
 * they stay written by hand, and the skeleton becomes their schema: this file
 * reads `types.ts` with the TypeScript compiler and walks each artefact's
 * declared type beside its committed shape.
 *
 *  - A declared field must be in the skeleton at that path. One that is not is a
 *    misspelling, or a field the pipeline stopped writing. An optional field may
 *    be absent where its interface is reused — `Word.log_dice` is written for
 *    collocates and not for keywords — but some artefact must write it, or it
 *    must carry an `@uncontracted` tag saying why the skeleton cannot show it.
 *  - A field the skeleton marks `key?` is absent from some members, and an
 *    interface that declares it always present will read those rows as
 *    `undefined`.
 *  - A leaf must accept every kind it is written as: `int` and `float` a number,
 *    `str` a string or a union of string literals, `bool` a boolean, and `null`
 *    a `| null`. An optional field is not a nullable one: JSON writes the null.
 *
 * The other direction is loose on purpose, as `contract.differences` is. A field
 * the pipeline writes and no interface declares is a field the dashboard does
 * not read yet, which is how every feature here started. A declaration wider
 * than this build — `number | null` over a column that happened to hold no
 * nulls, a field kept optional so an archived payload stays readable — has read
 * the producer rather than the sample, and is not drift.
 *
 * What a skeleton cannot show, this cannot check: the members of an array the
 * committed payload holds empty (the usage layer's comparison and gold tables,
 * until a second run and a coded sample exist), and the object half of a field
 * that was null throughout. Those interfaces are reached the day the contract is
 * regenerated over a payload that fills them.
 */

import ts from 'typescript';
import { describe, expect, it } from 'vitest';
import payload from '../../../tests/contract/payload.json';
/**
 * The two sources, imported as text.
 *
 * `contract.test.ts` imports its JSON rather than reading it off disk, because
 * `node:fs` would have `svelte-check`, which types this directory as browser
 * code, ask for Node's types. `?raw` is the same move for source: `vite/client`
 * declares it, SvelteKit's types already reference that, and Vite resolves it
 * under Vitest without the framework. The compiler still reads its own standard
 * library through `ts.sys`, but that is TypeScript's file rather than this
 * project's, and it is there wherever the devDependency is.
 */
import fetching from './data.ts?raw';
import declaring from './types.ts?raw';

/** A committed skeleton: a leaf such as `float|null`, an array of one merged element, or an object. */
type Shape = string | Shape[] | { [key: string]: Shape };

const contract: Record<string, Shape> = payload;

/** The suffix `contract.py` gives a field that some members of a collection omit. */
const OPTIONAL = '?';

/** The JSDoc tag that excuses a declared field from appearing in the skeleton. */
const UNCONTRACTED = 'uncontracted';

/** What a declared type can carry, as far as JSON is concerned. */
type Kind = 'any' | 'null' | 'string' | 'number' | 'boolean' | 'array' | 'object' | 'other';

/** The declared kinds that can carry a value the skeleton names by each leaf. */
const CARRIED_BY: Record<string, Kind[]> = {
	int: ['number'],
	float: ['number'],
	str: ['string'],
	bool: ['boolean'],
	null: ['null'],
	// `merge` names a container `object` when it shares a path with a scalar,
	// which is how a centroid that is sometimes absent is written: `null|object`.
	object: ['array', 'object']
};

/**
 * One source compiled on its own.
 *
 * ES5's library is enough — it declares `Array`, `Record` and `Pick`, which is
 * all `types.ts` reaches for — and it parses in a fraction of the time the DOM's
 * would. The file is handed to the compiler from memory under a bare name, so
 * nothing but the library is read from disk.
 */
function compile(text: string) {
	const FILE = 'types.ts';
	const options: ts.CompilerOptions = {
		strict: true,
		noEmit: true,
		lib: ['lib.es5.d.ts'],
		types: []
	};
	const host = ts.createCompilerHost(options);
	const source = ts.createSourceFile(FILE, text, ts.ScriptTarget.ES2022, true);
	const read = host.getSourceFile.bind(host);
	host.getSourceFile = (name, ...rest) => (name === FILE ? source : read(name, ...rest));
	const program = ts.createProgram([FILE], options, host);
	const checker = program.getTypeChecker();
	const module = checker.getSymbolAtLocation(source);
	const exports = module ? checker.getExportsOfModule(module) : [];
	return {
		checker,
		exported: new Map(exports.map((symbol) => [symbol.name, symbol])),
		diagnostics: ts
			.getPreEmitDiagnostics(program)
			.map((diagnostic) => ts.flattenDiagnosticMessageText(diagnostic.messageText, '\n'))
	};
}

/**
 * Which interface types which artefact is not written down here a second time.
 *
 * `data.ts` already says it. `at<AnnualSeries>('series/annual.json')` is the
 * cast every figure built on that accessor inherits, and a table in this file
 * would be a copy that could disagree with it — checking a type the dashboard
 * had stopped using while the one it did use went unexamined. So the accessors
 * are read instead, by their calls to `at` and `json`: a literal path names one
 * artefact, and a template (`kwic/${term}.json`) matches the representative
 * file the contract samples. An artefact the contract tracks that no typed
 * accessor fetches fails below rather than going unchecked.
 */
const FETCHERS = new Set(['at', 'json']);

interface Accessor {
	/** The type argument, as written. */
	type: string;
	/** A literal path wins over a template that also matches it: `kwic/index.json`. */
	literal: boolean;
	path: RegExp;
}

const escape = (text: string) => text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

function pathOf(node: ts.Expression | undefined): Omit<Accessor, 'type'> | undefined {
	if (node && (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node))) {
		return { literal: true, path: new RegExp(`^${escape(node.text)}$`) };
	}
	if (node && ts.isTemplateExpression(node)) {
		const fixed = [node.head.text, ...node.templateSpans.map((span) => span.literal.text)];
		return { literal: false, path: new RegExp(`^${fixed.map(escape).join('[^/]+')}$`) };
	}
	// `at` hands its own parameter on to `json`: the generic plumbing, not an accessor.
	return undefined;
}

function accessors(text: string): Accessor[] {
	const found: Accessor[] = [];
	const visit = (node: ts.Node): void => {
		if (
			ts.isCallExpression(node) &&
			ts.isIdentifier(node.expression) &&
			FETCHERS.has(node.expression.text) &&
			node.typeArguments?.length === 1
		) {
			const [argument] = node.typeArguments;
			const path = pathOf(node.arguments[0]);
			if (path && ts.isTypeReferenceNode(argument!) && ts.isIdentifier(argument.typeName)) {
				found.push({ type: argument.typeName.text, ...path });
			}
		}
		ts.forEachChild(node, visit);
	};
	visit(ts.createSourceFile('data.ts', text, ts.ScriptTarget.ES2022, true));
	return found;
}

/** The names `data.ts` fetches one artefact as: exactly one, if all is well. */
function fetchedAs(artefact: string, from: Accessor[]): string[] {
	const matching = from.filter((accessor) => accessor.path.test(artefact));
	const literal = matching.filter((accessor) => accessor.literal);
	return [...new Set((literal.length ? literal : matching).map((accessor) => accessor.type))];
}

/** One declared field, followed across every path its interface is met at. */
interface Field {
	/** `Interface.field`, or for a field of an inline type the first path it was met at. */
	label: string;
	optional: boolean;
	/** The reason its `@uncontracted` tag gives: `''` for a bare tag, absent for none. */
	excuse?: string;
	written: boolean;
}

interface Root {
	artefact: string;
	type: ts.Type;
	shape: Shape;
}

/**
 * Every disagreement between declared types and the skeletons they stand for.
 *
 * Per-path findings are kept by artefact so a failure names the file a reader
 * would open. Whether an optional field is written *anywhere* can only be
 * decided once every artefact has been walked, so those are returned as the
 * fields themselves and judged by the caller.
 */
function audit(checker: ts.TypeChecker, roots: Root[]) {
	const problems = new Map<string, string[]>();
	const fields = new Map<ts.Node | ts.Symbol, Field>();
	let artefact = '';
	let found: string[] = [];

	const show = (type: ts.Type) => checker.typeToString(type);
	const parts = (type: ts.Type) =>
		(type.isUnion() ? type.types : [type]).filter(
			// `undefined` is how the checker spells `?:`, and optionality is judged
			// against the skeleton's marker, not against a leaf.
			(part) => !(part.flags & ts.TypeFlags.Undefined)
		);
	const kindOf = (type: ts.Type): Kind => {
		const flags = type.flags;
		if (flags & (ts.TypeFlags.Any | ts.TypeFlags.Unknown)) return 'any';
		if (flags & ts.TypeFlags.Null) return 'null';
		if (flags & ts.TypeFlags.StringLike) return 'string';
		if (flags & ts.TypeFlags.NumberLike) return 'number';
		if (flags & ts.TypeFlags.BooleanLike) return 'boolean';
		if (checker.isArrayType(type) || checker.isTupleType(type)) return 'array';
		if (flags & ts.TypeFlags.Object) return 'object';
		return 'other';
	};

	const field = (property: ts.Symbol, at: string, optional: boolean): Field => {
		const declaration = property.valueDeclaration ?? property.declarations?.[0];
		const key = declaration ?? property;
		const known = fields.get(key);
		if (known) return known;
		const owner =
			declaration && ts.isInterfaceDeclaration(declaration.parent)
				? declaration.parent.name.text
				: undefined;
		const tag = property.getJsDocTags(checker).find((one) => one.name === UNCONTRACTED);
		const created: Field = {
			label: owner ? `${owner}.${property.name}` : `${artefact} ${at}`,
			optional,
			excuse: tag ? ts.displayPartsToString(tag.text).trim() : undefined,
			written: false
		};
		fields.set(key, created);
		return created;
	};

	const walk = (type: ts.Type, shape: Shape, path: string): void => {
		const where = path || '(root)';
		const declared = parts(type);
		// Declared as anything at all: there is nothing to hold it to.
		if (declared.some((part) => kindOf(part) === 'any')) return;
		if (typeof shape === 'string') {
			const kinds = new Set(declared.map(kindOf));
			const uncarried = shape
				.split('|')
				.filter((leaf) => !(CARRIED_BY[leaf] ?? []).some((kind) => kinds.has(kind)));
			if (uncarried.length) found.push(`${where}: written as ${shape}, declared as ${show(type)}`);
			return;
		}
		const wanted: Kind = Array.isArray(shape) ? 'array' : 'object';
		const candidates = declared.filter((part) => kindOf(part) === wanted);
		if (candidates.length !== 1) {
			found.push(
				candidates.length
					? `${where}: declared as ${show(type)}, which offers more than one ${wanted} to compare`
					: `${where}: written as ${Array.isArray(shape) ? 'an array' : 'an object'}, declared as ${show(type)}`
			);
			return;
		}
		if (Array.isArray(shape)) elements(candidates[0]!, shape, path);
		else properties(candidates[0]!, shape, path);
	};

	const elements = (type: ts.Type, shape: Shape[], path: string) => {
		const [element] = shape;
		// Empty throughout the committed build: there is no element to compare.
		if (element === undefined) return;
		const members = checker.getTypeArguments(type as ts.TypeReference);
		if (checker.isTupleType(type)) {
			members.forEach((member, index) => walk(member, element, `${path}[${index}]`));
		} else {
			walk(members[0]!, element, `${path}[]`);
		}
	};

	const properties = (type: ts.Type, shape: { [key: string]: Shape }, path: string) => {
		const written = new Map(
			Object.entries(shape).map(([key, value]) =>
				key.endsWith(OPTIONAL)
					? [key.slice(0, -OPTIONAL.length), { always: false, value }]
					: [key, { always: true, value }]
			)
		);
		const declared = checker.getPropertiesOfType(type);
		for (const property of declared) {
			const at = `${path}.${property.name}`;
			const optional = (property.flags & ts.SymbolFlags.Optional) !== 0;
			const tracked = field(property, at, optional);
			const value = written.get(property.name);
			if (!value) {
				if (!optional && tracked.excuse === undefined) found.push(`${at}: declared, not written`);
				continue;
			}
			tracked.written = true;
			if (!value.always && !optional) {
				found.push(`${at}: absent from some members, declared as always present`);
			}
			walk(checker.getTypeOfSymbol(property), value.value, at);
		}
		// A `Record<string, …>`, or the rest of an interface with an index
		// signature. Without one, a field written and not declared is a field
		// the dashboard does not read yet.
		const index = checker.getIndexInfoOfType(type, ts.IndexKind.String)?.type;
		if (!index) return;
		const named = new Set(declared.map((property) => property.name));
		for (const [key, { value }] of written) {
			if (!named.has(key)) walk(index, value, `${path}.${key}`);
		}
	};

	for (const root of roots) {
		artefact = root.artefact;
		found = [];
		walk(root.type, root.shape, '');
		problems.set(artefact, found);
	}
	return { problems, fields: [...fields.values()] };
}

/** The verdicts that need every artefact walked first. */
function across(fields: Field[]) {
	return {
		unwritten: fields
			.filter((one) => one.optional && !one.written && one.excuse === undefined)
			.map((one) => `${one.label}: declared, and written by no artefact the contract tracks`),
		stale: fields
			.filter((one) => one.excuse !== undefined && one.written)
			.map((one) => `${one.label}: tagged @${UNCONTRACTED}, and the contract now carries it`),
		unexplained: fields
			.filter((one) => one.excuse === '')
			.map((one) => `${one.label}: tagged @${UNCONTRACTED} without a reason`)
	};
}

const compiled = compile(declaring);
const fetchers = accessors(fetching);
const roots = Object.entries(contract).flatMap(([artefact, shape]): Root[] => {
	const names = fetchedAs(artefact, fetchers);
	const symbol = names.length === 1 ? compiled.exported.get(names[0]!) : undefined;
	return symbol
		? [{ artefact, shape, type: compiled.checker.getDeclaredTypeOfSymbol(symbol) }]
		: [];
});
const { problems, fields } = audit(compiled.checker, roots);
const verdicts = across(fields);

describe('what types.ts declares against what the pipeline writes', () => {
	it('reads types.ts as the compiler does', () => {
		// The walk trusts the checker's reading of every alias, `extends` and
		// `Pick`. If the library failed to load, `Record` would resolve to an error
		// type, every map in the file would pass as unknowable, and the check below
		// could not fail.
		expect(compiled.diagnostics).toEqual([]);
	});

	it.each(Object.keys(contract))('%s is fetched as one declared type', (artefact) => {
		const names = fetchedAs(artefact, fetchers);
		expect(
			names,
			`data.ts fetches ${artefact} as ${names.join(' and ') || 'nothing typed'}`
		).toHaveLength(1);
		expect(compiled.exported.has(names[0]!), `types.ts exports no ${names[0]}`).toBe(true);
	});

	it('fetches nothing as a type the contract cannot check', () => {
		const untracked = fetchers
			.filter((accessor) => !Object.keys(contract).some((artefact) => accessor.path.test(artefact)))
			.map((accessor) => `${accessor.type} at ${accessor.path.source}`);
		expect(
			untracked,
			`fetched, and not in tests/contract/payload.json: ${untracked.join(', ')}`
		).toEqual([]);
	});

	it.each(Object.keys(contract))('%s is declared as it is written', (artefact) => {
		const found = problems.get(artefact) ?? [];
		expect(found, found.join('\n')).toEqual([]);
	});

	it('declares no field that nothing writes', () => {
		// The misspelt optional field: it passes every path one at a time, because
		// optional fields may be absent, and is absent from all of them.
		expect(verdicts.unwritten, verdicts.unwritten.join('\n')).toEqual([]);
	});

	it('excuses a field only with a reason, and only while the skeleton lacks it', () => {
		// A tag that outlives its reason is a comment that has started lying.
		const both = [...verdicts.unexplained, ...verdicts.stale];
		expect(both, both.join('\n')).toEqual([]);
	});
});

describe('the walk, on declarations written to fail', () => {
	const probe = (source: string, shape: Shape) => {
		const { checker, exported, diagnostics } = compile(source);
		expect(diagnostics).toEqual([]);
		const symbol = exported.get('Probe');
		if (!symbol) throw new Error('the probe exports no Probe');
		const type = checker.getDeclaredTypeOfSymbol(symbol);
		const { problems, fields } = audit(checker, [{ artefact: 'probe.json', type, shape }]);
		const { unwritten, stale, unexplained } = across(fields);
		return [...(problems.get('probe.json') ?? []), ...unwritten, ...stale, ...unexplained];
	};

	it('finds each kind of drift it exists for', () => {
		const source = `
			export interface Probe {
				renamed: number;
				rate: number;
				sometimes: string;
				kind: number;
				misspelt?: string;
				/** @${UNCONTRACTED} Once, but no longer. */
				excused?: string;
				/** @${UNCONTRACTED} */
				bare?: string;
			}`;
		const shape = {
			rate: 'float|null',
			'sometimes?': 'str',
			kind: 'str',
			excused: 'str'
		};
		expect(probe(source, shape)).toEqual([
			'.renamed: declared, not written',
			'.rate: written as float|null, declared as number',
			'.sometimes: absent from some members, declared as always present',
			'.kind: written as str, declared as number',
			'Probe.misspelt: declared, and written by no artefact the contract tracks',
			'Probe.excused: tagged @uncontracted, and the contract now carries it',
			'Probe.bare: tagged @uncontracted without a reason'
		]);
	});

	it('accepts what TypeScript legitimately says about the same shapes', () => {
		const source = `
			interface Base { script: string; [key: string]: unknown }
			interface Picked { scopes: Record<'word' | 'debate', number>; dropped: string }
			export interface Probe extends Base, Pick<Picked, 'scopes'> {
				freq: 'year' | 'quarter';
				rate: number | null;
				centroid: [number, number] | null;
				terms: Record<string, { speeches: number[] }>;
				kept?: boolean;
				/** @${UNCONTRACTED} Written only on a derived measure. */
				derived?: string;
			}`;
		const shape = {
			script: 'str',
			lexicon_version: 'int',
			scopes: { debate: 'int', word: 'int' },
			freq: 'str',
			rate: 'float',
			centroid: 'null|object',
			terms: { '*': { speeches: ['int'] } },
			kept: 'bool',
			later: 'str'
		};
		expect(probe(source, shape)).toEqual([]);
	});
});
