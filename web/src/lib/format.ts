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
export const decimal = (n: number) => decimals.format(n);
export const signed = (n: number) => (n >= 0 ? `+${decimals.format(n)}` : decimals.format(n));

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
 * `$lib/heatmap` owned these while the grid was the only thing that counted in
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

/** Long official names are unreadable in a table cell or on an axis. */
const SHORT: Record<string, string> = {
	'United Kingdom Of Great Britain And Northern Ireland': 'United Kingdom',
	'United States Of America': 'United States',
	'Russian Federation': 'Russia',
	'Republic Of Korea': 'South Korea',
	"Democratic People'S Republic Of Korea": 'North Korea',
	'Democratic Republic Of The Congo': 'DR Congo',
	'Bolivarian Republic Of Venezuela': 'Venezuela',
	'Islamic Republic Of Iran': 'Iran',
	'Syrian Arab Republic': 'Syria',
	'United Republic Of Tanzania': 'Tanzania',
	'Bosnia And Herzegovina': 'Bosnia and Herzegovina',
	"Lao People'S Democratic Republic": 'Laos'
};

export const shortCountry = (name: string) => SHORT[name] ?? name;

export function isoDate(value: string): string {
	const date = new Date(value);
	return Number.isNaN(date.valueOf())
		? value
		: date.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric' });
}

/** The UN Digital Library record for an `S/PV.####` symbol. */
/**
 * A meeting symbol as the UN prints it.
 *
 * The corpus writes a resumed sitting as `S/PV.3745Resumption1`; the record
 * itself is `S/PV.3745 (Resumption 1)`, and a citation that carries the
 * corpus form names a document that does not exist under that name. The base
 * symbol is kept beside it for the search, which is by document symbol.
 */
export function meetingLabel(spv: string): string {
	const match = /^(.*?)Resumption(\d+)$/i.exec(spv);
	return match ? `${match[1]} (Resumption ${match[2]})` : spv;
}

/** The symbol without its resumption suffix: what the Digital Library indexes. */
export const meetingBase = (spv: string): string => spv.replace(/Resumption\d+$/i, '');

export const unSearch = (spv: string) =>
	`https://digitallibrary.un.org/search?ln=en&p=${encodeURIComponent(meetingBase(spv))}`;
