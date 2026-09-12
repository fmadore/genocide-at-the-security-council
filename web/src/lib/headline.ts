/** All headline views use the full word-family count. */
export const HEADLINE: readonly string[] = ['genocide'];

/** The first headline measure among `available`, or undefined if neither is. */
export function headlineMeasure(available: Iterable<string>): string | undefined {
	const names = new Set(available);
	return HEADLINE.find((name) => names.has(name));
}
