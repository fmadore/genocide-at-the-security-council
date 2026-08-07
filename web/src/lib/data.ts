/**
 * Fetching the pipeline's artefacts.
 *
 * Everything is a static JSON file under `static/data/`, so there is no API and
 * no server. What there is instead is a cache: the concordance for one term is
 * up to 10 MB, and a reader who moves between views should not pay for it
 * twice.
 */

import { base } from '$app/paths';
import type {
	AnnualSeries,
	Breakdowns,
	ChangePoints,
	Collocates,
	Events,
	Keyness,
	KwicFile,
	KwicIndex,
	Meeting,
	MeetingIndex,
	Network,
	SlicedCollocates
} from './types';

const cache = new Map<string, Promise<unknown>>();

/** Fetch and cache a JSON payload, keyed on its path. */
export function json<T>(path: string, fetcher: typeof fetch = fetch): Promise<T> {
	const url = `${base}/data/${path}`;
	if (!cache.has(url)) {
		cache.set(
			url,
			fetcher(url).then((response) => {
				if (!response.ok) {
					// A 404 here almost always means the pipeline has not been run,
					// so say that rather than letting a parse error surface.
					throw new Error(
						`${path} is missing (${response.status}). Run the pipeline and ` +
							`scripts/export_web.py to build web/static/data/.`
					);
				}
				return response.json();
			})
		);
	}
	return cache.get(url) as Promise<T>;
}

export const annual = (f?: typeof fetch) => json<AnnualSeries>('series/annual.json', f);
export const quarterly = (f?: typeof fetch) => json<AnnualSeries>('series/quarterly.json', f);
export const breakdowns = (f?: typeof fetch) => json<Breakdowns>('series/breakdowns.json', f);
export const changePoints = (f?: typeof fetch) =>
	json<ChangePoints>('series/change_points.json', f);
export const events = (f?: typeof fetch) => json<Events>('series/events.json', f);

export const collocates = (f?: typeof fetch) => json<Collocates>('lexical/collocates.json', f);
export const slicedCollocates = (f?: typeof fetch) =>
	json<SlicedCollocates>('lexical/collocates_sliced.json', f);
export const keyness = (f?: typeof fetch) => json<Keyness>('lexical/keyness.json', f);
export const network = (f?: typeof fetch) => json<Network>('lexical/network.json', f);

export const kwicIndex = (f?: typeof fetch) => json<KwicIndex>('kwic/index.json', f);
export const kwic = (term: string, f?: typeof fetch) => json<KwicFile>(`kwic/${term}.json`, f);

export const meetingIndex = (f?: typeof fetch) => json<MeetingIndex>('meetings.json', f);
export const meeting = (basename: string, f?: typeof fetch) =>
	json<Meeting>(`speeches/${basename}.json`, f);

/** `UNSC_2015_SPV.7481_spch0007#3` → the meeting file that speech lives in. */
export function meetingOf(lineId: string): string {
	const speech = lineId.split('#')[0];
	return speech.replace(/_spch\d+$/, '');
}

/** `UNSC_2015_SPV.7481_spch0007#3` → `UNSC_2015_SPV.7481_spch0007`. */
export function speechOf(lineId: string): string {
	return lineId.split('#')[0];
}
