/**
 * The Overview's headline figures, computed from the annual series.
 *
 * The first numbers a reader meets: the size of the corpus, how much of it
 * uses the word, and the two years the page names. Each is a sum or an
 * argmax over a column of the artefact, decided here so a test can check it
 * against the column it comes from.
 */

import type { AnnualSeries, Measure } from './types';

const sum = (values: readonly number[]) => values.reduce((a, b) => a + b, 0);

/** The corpus and the headline measure, summed over every period. */
export interface OverviewTotals {
	speeches: number;
	words: number;
	meetings: number;
	/** Speeches that use the headline term. */
	bearing: number;
	occurrences: number;
	speakers: number;
}

export function overviewTotals(series: AnnualSeries, measure: Measure): OverviewTotals {
	return {
		speeches: sum(series.corpus.speeches),
		words: sum(series.corpus.words),
		meetings: sum(series.corpus.meetings),
		bearing: sum(measure.speeches),
		occurrences: sum(measure.occurrences ?? []),
		speakers: (series.meta.speakers as number) ?? 0
	};
}

/**
 * The year whose speeches most often use the term: the highest share of
 * speeches, the measure the page argues for. The first such year on a tie.
 */
export function densest(years: readonly number[], measure: Measure): number | undefined {
	// A withheld year has no rate to be the highest; it is passed over, not read as zero.
	let best = -1;
	measure.speech_rate.forEach((rate, index) => {
		if (rate != null && (best < 0 || rate > measure.speech_rate[best]!)) best = index;
	});
	return best < 0 ? undefined : years[best];
}

/**
 * The year with the most occurrences, a raw count the page sets beside the
 * densest year to show the two disagree. The first such year on a tie.
 */
export function loudest(years: readonly number[], measure: Measure): number | undefined {
	const occurrences = measure.occurrences ?? [];
	return years[occurrences.indexOf(Math.max(...occurrences))];
}

/**
 * The last year the record covers whole, and whether a later one is partial.
 *
 * The series runs over calendar years and the record does not end on one: v6.0
 * stops on 23 June 2026. Read as a year, 2026 has 3,253 speeches against
 * 2025's 7,608, and a sentence comparing "the final year" with the first, or a
 * bar drawn beside its neighbours, says the Council fell silent when the
 * record simply stops. A final year counts as whole when the record runs into
 * its December. A payload written before the artefact carried its bounds has
 * nothing to test, and its final year is taken as whole, as it always was.
 */
export function finalYear(series: AnnualSeries): {
	/** Index of the last complete year. */
	complete: number;
	/** Index of the partial year after it, or null. */
	partial: number | null;
	/** The record's last date, where the artefact gives one. */
	ends: string | null;
} {
	const last = series.periods.length - 1;
	const ends = series.record?.last_date ?? null;
	const whole =
		!ends || Number(ends.slice(0, 4)) !== Number(series.periods[last]) || ends.slice(5, 7) === '12';
	return whole || last < 1
		? { complete: last, partial: null, ends }
		: { complete: last - 1, partial: last, ends };
}
