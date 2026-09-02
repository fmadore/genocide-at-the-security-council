/**
 * Which measure a view opens on when nobody has chosen yet.
 *
 * Since lexicon v4 the published headline is `genocide_qualification` — the
 * `genocide` term minus its `genocidaires` actor label, 31 of the raw term's
 * 6,092 occurrences. The raw term stays in every artefact and is what the
 * concordance enumerates, so a reader can always select it; this only decides
 * what is drawn before anyone does.
 *
 * The fallback is not decoration. An artefact cut before v4 carries the raw
 * term and nothing derived, and the e2e fixtures are exactly such an artefact;
 * a page that reads the derived key directly crashes on them before its chart
 * exists. Three views open on the headline (the home page, the chronology, the
 * actor table), and one rule here is what keeps them from disagreeing about
 * what the site's first number is.
 */
export const HEADLINE: readonly string[] = ['genocide_qualification', 'genocide'];

/** The first headline measure among `available`, or undefined if neither is. */
export function headlineMeasure(available: Iterable<string>): string | undefined {
	const names = new Set(available);
	return HEADLINE.find((name) => names.has(name));
}
