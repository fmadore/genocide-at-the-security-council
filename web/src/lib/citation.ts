import type { KwicLine } from './types';

/** A quotation plus enough plain-text context to trace it without special software. */
export function occurrenceQuotation(line: KwicLine, permalink: string): string {
	return [
		`“${line.sent.trim()}”`,
		'',
		`${line.country}, UN Security Council, ${line.spv} (${line.date}). ` +
			`Genocide at the Security Council, occurrence ${line.id}. ${permalink}`
	].join('\n');
}
