/**
 * How much of the data payload the service worker keeps for offline use.
 *
 * The worker caches every data file it fetches, so a reader who loses the
 * connection keeps what they have already read. Most of the payload is a
 * fixed set of artefacts, one file each, and caching all of them is bounded by
 * the release. Three families are not: one concordance per term, one file per
 * meeting and one shard of neighbours per slice of the semantic map. A reader
 * who works through a few hundred meetings would otherwise hold every one of
 * them on disk until the next deployment.
 *
 * Those families get a ceiling instead, in the spirit of `KEEP` in `data.ts`
 * and larger than it, because this cache is on disk rather than in a tab's
 * memory and exists to be read offline: enough for an afternoon's reading,
 * not the corpus.
 *
 * Pure, so that it can be tested here and imported by `service-worker.ts`.
 */

export interface Family {
	/** Whether a path under `data/` belongs to this family. */
	matches: (path: string) => boolean;
	/** How many of its files the offline cache keeps, most recently fetched first. */
	keep: number;
	/**
	 * What a reader calls these files, for the sentence that says what is kept
	 * offline (`unreachable` in `$lib/data`), so the ceiling and the copy that
	 * states it cannot drift apart.
	 */
	noun?: string;
}

export const OFFLINE_KEEP: readonly Family[] = [
	{ matches: (path) => path.startsWith('speeches/'), keep: 100, noun: 'meeting records' },
	{
		matches: (path) => path.startsWith('kwic/') && path !== 'kwic/index.json',
		keep: 6,
		noun: 'concordance terms'
	},
	{
		matches: (path) => path.startsWith('semantic/neighbours/'),
		keep: 32,
		noun: 'related-speech files'
	}
];

/** `100 meeting records, 6 concordance terms and 32 related-speech files`. */
export function offlineCeilings(families: readonly Family[] = OFFLINE_KEEP): string {
	const named = families.filter((family) => family.noun).map((f) => `${f.keep} ${f.noun}`);
	return named.length > 1 ? `${named.slice(0, -1).join(', ')} and ${named.at(-1)}` : named.join('');
}

/**
 * The cached paths to drop so that each bounded family keeps only its most
 * recent files.
 *
 * `cached` is in the order the cache holds its entries. The Cache API keeps
 * insertion order and a `put` over an existing entry moves it to the end, and
 * the worker puts every data file again each time the network serves it, so
 * the order is oldest fetch first. Paths outside `root` are never dropped.
 */
export function overflow(
	cached: readonly string[],
	root: string,
	families: readonly Family[] = OFFLINE_KEEP
): string[] {
	const stale: string[] = [];
	for (const family of families) {
		const held = cached.filter(
			(path) => path.startsWith(root) && family.matches(path.slice(root.length))
		);
		stale.push(...held.slice(0, Math.max(0, held.length - family.keep)));
	}
	return stale;
}
