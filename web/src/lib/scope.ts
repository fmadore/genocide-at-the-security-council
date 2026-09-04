/** R9's URL contract. An absent scope must keep every old link meaning "the word". */

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
