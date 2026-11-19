/** Number and label formatting, in one place so a table and a tooltip agree. */

const counts = new Intl.NumberFormat('en-GB');
const percents = new Intl.NumberFormat('en-GB', {
	style: 'percent',
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});
const decimals = new Intl.NumberFormat('en-GB', {
	minimumFractionDigits: 2,
	maximumFractionDigits: 2
});

export const count = (n: number) => counts.format(n);
export const percent = (n: number) => percents.format(n);
/**
 * A share that may be withheld. `Intl` formats `null` as 0, so a rate the
 * retention rule withheld would print as `0.00%`: a measured zero it is not.
 */
export const rateCell = (n: number | null | undefined) => (n == null ? 'withheld' : percent(n));
export const decimal = (n: number) => decimals.format(n);
export const signed = (n: number) => (n >= 0 ? `+${decimals.format(n)}` : decimals.format(n));

/** A change in a share, in signed percentage points: 0.0153 → `+1.53 pts`. */
export const points = (n: number) => `${n >= 0 ? '+' : '−'}${Math.abs(n * 100).toFixed(2)} pts`;

/**
 * Escape corpus-derived labels before interpolating them into ECharts HTML tooltips.
 *
 * `export.ts` has a near-twin, `escapeXml`, and the two are not a duplication
 * to be merged: an apostrophe becomes `&#39;` here and `&apos;` there, because
 * `&apos;` is XML and not one of HTML 4's named entities. This one writes into
 * a tooltip the browser parses as HTML; that one writes into a file that leaves
 * the browser as XML. Deleting either in favour of the other breaks one of the
 * two consumers in a way no test on this side would show.
 */
export const escapeHtml = (value: unknown): string =>
	String(value).replace(
		/[&<>'"]/g,
		(character) =>
			({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' })[character]!
	);

export function bytes(n: number): string {
	if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
	if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
	if (n >= 1e3) return `${(n / 1e3).toFixed(0)} kB`;
	return `${n} B`;
}

/** `crimes_against_humanity` → `crimes against humanity`. */
export const termLabel = (name: string) => name.replace(/_/g, ' ');

/** Display measure identifiers as readable words. */
export const measureLabel = termLabel;

/**
 * The columns the pairing holds constant, named the way a reader would name them.
 *
 * The artefacts carry the corpus's own column names in `matched_on`, and printing
 * them raw put "the same year, agenda_item_manual, speaker_group" into a sentence
 * on two separate pages. Anything unrecognised falls back to `termLabel`, so a new
 * matching column degrades to readable words rather than to an underscore.
 */
const MATCHED_ON: Record<string, string> = {
	year: 'year',
	agenda_item_manual: 'agenda item',
	agenda_item1: 'region of the agenda item',
	speaker_group: 'speaker group',
	entity_type: 'kind of speaker'
};

/**
 * What kind of speaker this is, for the delegations that sit in no UN regional
 * group and fall back to `entity_type`.
 *
 * The corpus stores those as identifiers, and the table printed `civil_society`
 * beside "Eastern European Group" in the same column. Anything unrecognised falls
 * back to the underscores stripped out, so a new type reads as words.
 */
const ENTITY_TYPE: Record<string, string> = {
	academia: 'Academia',
	civil_society: 'Civil society',
	company: 'Company',
	igo: 'Intergovernmental organisation',
	ngo: 'Non-governmental organisation',
	other: 'Other',
	state: 'State',
	un: 'United Nations'
};

export const entityType = (name: string) => ENTITY_TYPE[name] ?? termLabel(name);

export function matchedOn(fields: string[]): string {
	const names = fields.map((field) => MATCHED_ON[field] ?? termLabel(field));
	if (names.length < 2) return names.join('');
	// A list inside a sentence, so the last item takes "and" rather than a third
	// comma: "year, agenda item, speaker group" reads as a truncated list.
	return `${names.slice(0, -1).join(', ')} and ${names[names.length - 1]}`;
}

/**
 * The twelve months, here rather than in the figure that first needed them.
 *
 * `#lib/heatmap` owned these while the grid was the only thing that counted in
 * months. The concordance now filters by month too, and a second copy of the
 * list in the module that reads the filter is how a figure and the evidence
 * behind it start disagreeing about what June is called.
 */
export const MONTH_NAMES = [
	'January',
	'February',
	'March',
	'April',
	'May',
	'June',
	'July',
	'August',
	'September',
	'October',
	'November',
	'December'
];

/** `2014-06` → `June 2014`. */
export const monthLabel = (period: string): string => {
	const [year, month] = period.split('-');
	return `${MONTH_NAMES[Number(month) - 1] ?? month} ${year}`;
};

/**
 * Long official names are unreadable in a table cell or on an axis.
 *
 * Keyed by the corpus's own spelling, which is matched exactly. Dataset v6.0
 * already gives most states their short name (Russia, Syria, South Korea,
 * United Kingdom); these are the long forms it still writes.
 */
const SHORT: Record<string, string> = {
	'United States of America': 'United States',
	'Democratic Republic of the Congo': 'DR Congo',
	'Federated States of Micronesia': 'Micronesia'
};

export const shortCountry = (name: string) => SHORT[name] ?? name;

/**
 * Whether a speech's language field names a language at all.
 *
 * The corpus writes `Unknown` where the source recorded none, and that is every
 * speech in it: the field is present on all 182,684 and names a language on
 * none. Read as "some language, and not English", `Unknown` made the reader's
 * apparatus publish "179 speeches carry a non-English language label" on a
 * meeting held in English, and printed "spoke in Unknown" under every speaker.
 * A sentinel is an absent value wearing a name; it is treated as absent.
 *
 * Here rather than in the reader because two places read the same field for two
 * different sentences, and a second copy of this test is how they would come to
 * disagree about what the record says.
 */
export const namedLanguage = (language: string | null | undefined): boolean =>
	!!language && language.toLowerCase() !== 'unknown';

/** A language the record names, and which is not the language the record is in. */
export const interpretedFrom = (language: string | null | undefined): boolean =>
	namedLanguage(language) && language!.toLowerCase() !== 'english';

export function isoDate(value: string): string {
	const date = new Date(value);
	return Number.isNaN(date.valueOf())
		? value
		: date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

/**
 * A meeting symbol as the UN prints it.
 *
 * Corpus v6.0 writes a record's suffixes run together in brackets:
 * `S/PV.3336(Resumption2)`, `S/PV.2970(PartII)`,
 * `S/PV.2977(PartII)(closed-resumption1)`, `S/PV.618(communiqué)`. The older
 * corpus wrote `S/PV.3745Resumption1` with no brackets. Both print with a space
 * before each bracket and between a word and its number, as the record is
 * titled: `S/PV.3336 (Resumption 2)`, `S/PV.2970 (Part II)`.
 */
export function meetingLabel(spv: string): string {
	const match = /^(S\/PV\.\d+)\s*(.*)$/i.exec(spv.trim());
	if (!match || !match[2]) return spv;
	const rest = match[2].replace(/^Resumption(\d+)$/i, '(Resumption$1)');
	const parts = rest.match(/\([^)]*\)/g);
	if (!parts || parts.join('') !== rest.replace(/\s+/g, '')) return spv;
	const spaced = parts.map((part) =>
		part
			.replace(/\s+/g, '')
			.replace(/([a-zé])(\d+)/gi, '$1 $2')
			.replace(/^\(Part(I+)\)$/i, '(Part $1)')
	);
	return `${match[1]} ${spaced.join(' ')}`;
}

/** The symbol without its suffixes: what the Digital Library search indexes. */
export const meetingBase = (spv: string): string => /^S\/PV\.\d+/i.exec(spv.trim())?.[0] ?? spv;

/** The UN Digital Library record for an `S/PV.####` symbol. */
export const unSearch = (spv: string) =>
	`https://digitallibrary.un.org/search?ln=en&p=${encodeURIComponent(meetingBase(spv))}`;
