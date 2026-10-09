/**
 * When the data on this site were built, and from what.
 *
 * `export_web.py` closes every payload with `data/manifest.json`: the time the
 * export started and the commit it ran from. That is the build a reader is
 * looking at, and the footer says so in one line. The lexicon version is not in
 * the manifest; it travels in every artefact's `meta`, and the layout already
 * holds one of those.
 *
 * Read leniently, on purpose. The manifest is not one of the contracted
 * artefacts in `data.ts`: nothing on a page is drawn from it, and a payload
 * without one (a development tree, an old build) loses the line rather than
 * the page. A field of the wrong kind is dropped, never printed.
 *
 * **The release goes first, when there is one.** No citable release exists yet
 * (`docs/RELEASING.md`). When one does, it can arrive as `release` in the
 * manifest, and the footer leads with it; until then the field is absent and
 * nothing is shown in its place.
 */

export interface BuildStamp {
	/** A release name such as `v0.1`, once releases exist. Null until then. */
	release: string | null;
	/** ISO 8601, as the manifest writes it. */
	generated: string | null;
	/** The full commit, as `git rev-parse` gave it. */
	commit: string | null;
	/** True when the export ran from a tree with uncommitted changes. */
	dirty: boolean;
}

const text = (value: unknown): string | null =>
	typeof value === 'string' && value.trim() !== '' ? value.trim() : null;

/** The manifest's own fields, or null when it carries none this line can use. */
export function readBuild(manifest: unknown): BuildStamp | null {
	if (typeof manifest !== 'object' || manifest === null || Array.isArray(manifest)) return null;
	const record = manifest as Record<string, unknown>;
	const generated = text(record.generated);
	const raw = text(record.git_commit);
	const dirty = raw?.endsWith('-dirty') ?? false;
	const commit = raw ? raw.replace(/-dirty$/, '') : null;
	const release = text(record.release);
	if (!generated && !commit && !release) return null;
	return { release, generated, commit, dirty };
}

/**
 * A day as the site writes one: `14 September 2026`.
 *
 * In UTC, because the manifest's time is UTC and the page is rendered once on
 * the build machine and again in the reader's browser: a local time zone would
 * let the two disagree about the date of a build made near midnight.
 */
export function buildDay(iso: string): string | null {
	const date = new Date(iso);
	if (Number.isNaN(date.valueOf())) return null;
	return date.toLocaleDateString('en-GB', {
		day: 'numeric',
		month: 'long',
		year: 'numeric',
		timeZone: 'UTC'
	});
}

/** The seven characters a commit is cited by. */
export const shortCommit = (commit: string): string => commit.slice(0, 7);

/** A commit GitHub can resolve: forty hex characters, nothing else. */
export const isFullCommit = (commit: string): boolean => /^[0-9a-f]{40}$/i.test(commit);

/**
 * The footer's one line, in three pieces so the commit can be a link:
 * `Data built 14 September 2026 from commit ` · `d2b9a55` · ` · lexicon 8`.
 *
 * Null without a manifest: the lexicon version alone is not a build line, and
 * a footer that half-describes the build is worse than one that says nothing.
 */
export interface BuildLine {
	before: string;
	commit: { short: string; href: string | null } | null;
	after: string;
}

export function buildLine(
	stamp: BuildStamp | null,
	lexicon: number | null,
	repository: string
): BuildLine | null {
	if (!stamp) return null;
	const day = stamp.generated ? buildDay(stamp.generated) : null;
	const built =
		day || stamp.commit
			? `Data built${day ? ` ${day}` : ''}${stamp.commit ? ' from commit ' : ''}`
			: '';
	const before = [stamp.release ? `Release ${stamp.release}` : '', built]
		.filter(Boolean)
		.join(' · ');
	const commit = stamp.commit
		? {
				short: shortCommit(stamp.commit),
				href: isFullCommit(stamp.commit) ? `${repository}/commit/${stamp.commit}` : null
			}
		: null;
	const after =
		(commit && stamp.dirty ? ' with local changes' : '') +
		(lexicon !== null && Number.isFinite(lexicon) ? ` · lexicon ${lexicon}` : '');
	return { before, commit, after };
}
