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

export function bytes(n: number): string {
	if (n >= 1e9) return `${(n / 1e9).toFixed(1)} GB`;
	if (n >= 1e6) return `${(n / 1e6).toFixed(1)} MB`;
	if (n >= 1e3) return `${(n / 1e3).toFixed(0)} kB`;
	return `${n} B`;
}

/** `crimes_against_humanity` → `crimes against humanity`. */
export const termLabel = (name: string) => name.replace(/_/g, ' ');

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
export const unSearch = (spv: string) =>
	`https://digitallibrary.un.org/search?ln=en&p=${encodeURIComponent(spv)}`;
