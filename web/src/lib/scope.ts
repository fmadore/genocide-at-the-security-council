/**
 * R9's URL contract, and the reading a view draws once it has one.
 *
 * An absent scope must keep every old link meaning "the word". Past that, the
 * one rule this module exists to hold is that a scope selects a reading set and
 * never a denominator: every share below divides by the population the cut came
 * out of — a year's speeches, a delegation's speeches — and never by another
 * reading set. A control that moved the base of a published rate would make the
 * rate mean something new every time it was touched.
 */

import type { CorpusScope, ScopeCut, ScopeDelegation, ScopeIndex } from './types';

export const SCOPE_PARAM = 'scope';
export const SCOPE_IDS = ['word', 'vocabulary', 'debate'] as const;
export type ScopeId = (typeof SCOPE_IDS)[number];
export const DEFAULT_SCOPE: ScopeId = 'word';

export function readScope(params: URLSearchParams): ScopeId {
	const value = params.get(SCOPE_PARAM);
	return SCOPE_IDS.includes(value as ScopeId) ? (value as ScopeId) : DEFAULT_SCOPE;
}

/**
 * Change only scope state. The default is omitted so a default selection
 * serialises to the same URL the site published before R9.
 */
export function withScope(params: URLSearchParams, scope: ScopeId): URLSearchParams {
	const next = new URLSearchParams(params);
	if (scope === DEFAULT_SCOPE) next.delete(SCOPE_PARAM);
	else next.set(SCOPE_PARAM, scope);
	return next;
}

/** The selected reading set's own row, by id rather than by position. */
export function scopeOf(index: ScopeIndex, id: ScopeId): CorpusScope {
	const found = index.scopes.find((scope) => scope.id === id);
	if (!found) throw new Error(`The scope artefact declares no reading set called ${id}.`);
	return found;
}

export interface ScopeReading {
	speeches: number;
	/** The population the reading set was selected out of, never a reading set. */
	held: number;
	/** Withheld below the minimum: a share of a handful outranks every real one. */
	share: number | null;
}

export function reading(cut: ScopeCut, scope: ScopeId, minimum = 0): ScopeReading {
	const speeches = cut.scopes[scope];
	return {
		speeches,
		held: cut.held,
		share: cut.held >= minimum && cut.held > 0 ? speeches / cut.held : null
	};
}

export interface RankedDelegation extends ScopeReading {
	country_org: string;
}

/**
 * Delegations by their share of their own record, under one reading set.
 *
 * Speakers under the actor view's declared minimum are dropped rather than
 * ranked without a rate: this is a ranking, and the actor table already carries
 * the full list with its withheld rows named.
 */
export function rankedDelegations(
	index: ScopeIndex,
	scope: ScopeId,
	minimum: number,
	limit: number
): RankedDelegation[] {
	return index.delegations
		.filter((cut: ScopeDelegation) => cut.held >= minimum && cut.scopes[scope] > 0)
		.map((cut) => ({ country_org: cut.country_org, ...reading(cut, scope, minimum) }))
		.sort((a, b) => (b.share ?? 0) - (a.share ?? 0) || b.speeches - a.speeches)
		.slice(0, limit);
}

/**
 * The terms *the vocabulary* is built from, mirroring `scripts/lib/scopes.py`.
 *
 * The reader decides membership speech by speech, from the offsets the meeting
 * export already carries, rather than fetching a second artefact to be told
 * what the record in front of it already says.
 */
export const VOCABULARY_TERMS = [
	'genocide',
	'ethnic_cleansing',
	'crimes_against_humanity',
	'war_crimes'
] as const;

/**
 * Whether one speech belongs to a reading set.
 *
 * `saysTheWord` is the meeting's own answer, not the speech's: the debate set
 * is all-or-nothing inside a record, which is exactly what makes it able to
 * hold a delegation that said nothing.
 */
export function speechInScope(
	hits: Record<string, unknown>,
	scope: ScopeId,
	saysTheWord: boolean
): boolean {
	if (scope === 'debate') return saysTheWord;
	if (scope === 'word') return 'genocide' in hits;
	return VOCABULARY_TERMS.some((term) => term in hits);
}
