import { describe, expect, it } from 'vitest';
import { buildDay, buildLine, readBuild } from './build';

const REPO = 'https://github.com/fmadore/genocide-at-the-security-council';
const COMMIT = 'd2b9a55a137c2806b3e7a4c55d4d77c0cc545459';

describe('reading the payload manifest', () => {
	it('takes the build time and the commit, and notices a dirty tree', () => {
		expect(
			readBuild({ generated: '2026-09-14T08:58:33Z', git_commit: `${COMMIT}-dirty`, files: 9771 })
		).toEqual({ release: null, generated: '2026-09-14T08:58:33Z', commit: COMMIT, dirty: true });
	});

	it('drops what is missing or of the wrong kind rather than printing it', () => {
		expect(readBuild(null)).toBeNull();
		expect(readBuild([])).toBeNull();
		expect(readBuild({ generated: 7, git_commit: '' })).toBeNull();
		expect(readBuild({ git_commit: COMMIT })).toMatchObject({ generated: null, commit: COMMIT });
	});

	it('reads a release once the manifest names one', () => {
		expect(readBuild({ release: 'v0.1', git_commit: COMMIT })?.release).toBe('v0.1');
	});
});

describe('the footer’s build line', () => {
	it('names the day, the commit and the lexicon in one line', () => {
		const line = buildLine(
			readBuild({ generated: '2026-10-09T08:00:00Z', git_commit: COMMIT }),
			8,
			REPO
		);
		expect(line).toEqual({
			before: 'Data built 9 October 2026 from commit ',
			commit: { short: 'd2b9a55', href: `${REPO}/commit/${COMMIT}` },
			after: ' · lexicon 8'
		});
	});

	it('leads with the release when there is one', () => {
		const line = buildLine(
			readBuild({ release: 'v0.1', generated: '2026-10-09T08:00:00Z', git_commit: COMMIT }),
			8,
			REPO
		);
		expect(line?.before).toBe('Release v0.1 · Data built 9 October 2026 from commit ');
	});

	it('says when the build carried local changes, and links only a commit GitHub can find', () => {
		const dirty = buildLine(readBuild({ git_commit: `${COMMIT}-dirty` }), 8, REPO);
		expect(dirty?.after).toBe(' with local changes · lexicon 8');
		const odd = buildLine(readBuild({ git_commit: 'fixture' }), null, REPO);
		expect(odd?.commit).toEqual({ short: 'fixture', href: null });
		expect(odd?.after).toBe('');
	});

	it('is absent without a manifest', () => {
		expect(buildLine(null, 8, REPO)).toBeNull();
	});

	it('dates the build in UTC, so the server and the browser agree near midnight', () => {
		expect(buildDay('2026-10-09T23:30:00Z')).toBe('9 October 2026');
		expect(buildDay('not a date')).toBeNull();
	});
});
