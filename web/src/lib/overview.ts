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
	return years[measure.speech_rate.indexOf(Math.max(...measure.speech_rate))];
}

/**
 * The year with the most occurrences, a raw count the page sets beside the
 * densest year to show the two disagree. The first such year on a tie.
 */
export function loudest(years: readonly number[], measure: Measure): number | undefined {
	const occurrences = measure.occurrences ?? [];
	return years[occurrences.indexOf(Math.max(...occurrences))];
}
