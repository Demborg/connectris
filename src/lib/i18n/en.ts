import { formatTime } from '$lib/format';
import type { Best } from '$lib/game/log';

/**
 * Every word the interface says, in English.
 *
 * This file is the shape; `sv.ts` is checked against it by the type system, so a string
 * added here and forgotten there is a build error rather than an English sentence
 * appearing in the middle of a Swedish page.
 *
 * Anything that varies with a number or a name is a function. Pluralisation and word order
 * are not the same in two languages, and a template assembled at the call site would put
 * English grammar into every translation of it.
 */

/** A sentence with one emphasised run in it, so markup stays out of the strings. */
export type Marked = { before?: string; mark: string; after?: string; style: 'em' | 'strong' };

export const en = {
	/** The wordmark is a name, not a word — it is never translated. */
	brand: 'CONNECTRIS',
	title: {
		board: (name: string) => `Connectris — ${name}`,
		boards: 'Connectris — Boards',
		standings: 'Connectris — Standings',
		hello: 'Connectris — Pick a name'
	},
	nav: {
		today: "Today's board",
		standings: 'Standings',
		boards: 'Pick a board',
		allBoards: 'All boards →'
	},
	game: {
		none: 'No board in this language yet. There will be one tomorrow.',
		goal: 'Make five rows of four — surest at the top',
		howToPlay: 'How to play',
		closeRules: 'Close the rules',
		check: 'Check',
		checksLeft: (left: number, of: number) => `${left} of ${of} checks left`,
		/** Read out after a swap. The board is a flat run of buttons otherwise. */
		tile: (word: string, row: number, rows: number) => `${word}, row ${row} of ${rows}`,
		closeCategory: 'Close the category',
		rules: [
			{
				before: 'Sort all 20 words into 5 rows of four. Order ',
				mark: 'inside',
				after: " a row doesn't matter.",
				style: 'em'
			},
			{
				mark: 'Drag a word onto another to swap them, or tap the two of them in turn.',
				style: 'em'
			},
			{
				mark: 'Check clears from the top down only.',
				after:
					" A correct row sitting below a wrong one doesn't clear. Put the row you're surest about first.",
				style: 'strong'
			},
			{
				mark: 'Every check costs one.',
				after:
					' Clearing several rows in one go is how you keep them — which is what getting the order right buys you.',
				style: 'strong'
			},
			{ mark: 'A check tells you how many rows are right — never which ones.', style: 'em' }
		] as Marked[]
	},
	verdict: {
		outOfOrder: 'more right · wrong order',
		/** The count is set beside this, so these say only the words around it. */
		rightNoneAtTop: (count: number) => `${count === 1 ? 'row' : 'rows'} right · none at the top`,
		right: (count: number) => `${count === 1 ? 'row' : 'rows'} right`
	},
	/** Shouted when several rows clear at once. Names, so they stay as they are. */
	combo: { 2: 'DOUBLE', 3: 'TRIPLE', 4: 'QUAD', 5: 'CONNECTRIS' } as Record<number, string>,
	end: {
		won: 'Solved',
		lost: 'Out of checks',
		seeBoard: 'See the board',
		questions: 'Questions',
		score: (time: number, left: number) => `${formatTime(time)} · ${left} left`,
		best: (time: number) => ` · best ${formatTime(time)}`,
		next: 'Next puzzle',
		howWasThat: 'How was that?',
		levels: { easy: 'Too easy', right: 'Just right', hard: 'Too hard' },
		wasItFair: 'Was it fair?',
		yes: 'Yes',
		no: 'No',
		commentLabel: 'Anything else about this board?',
		commentPlaceholder: 'Anything else? (optional)',
		top: (of: number) => `Top of the standings, of ${of}`,
		place: (place: number, of: number) => `${place}${ordinal(place)} of ${of} in the standings`
	},
	boards: {
		heading: 'Boards',
		note: 'Every board still in play. Yours are marked, on whatever you play them on.',
		today: 'Today',
		solved: 'Solved',
		played: 'Played',
		notPlayed: 'Not played',
		record: (time: number, left: number) => `${formatTime(time)} · ${left} left`,
		/** The whole card, said in words, because a coloured mark alone is not readable. */
		label: (name: string, today: boolean, said: string, best: Best | null) =>
			`${name}${today ? ", today's board" : ''}, ${said}${
				best ? `, best ${formatTime(best.timeMs)} with ${best.checksLeft} checks left` : ''
			}`,
		/** Said when a language has boards on the way but none playable yet. */
		none: 'No boards in this language yet. There will be one tomorrow.'
	},
	top: {
		heading: 'Standings',
		rule: 'Boards solved, then checks left, then time.',
		players: (n: number) => (n === 1 ? 'One player so far.' : `${n} players.`),
		empty: 'Nobody has solved anything yet. That is a gap you could close.',
		you: ' (you)',
		notYet: 'Not yet',
		detail: (checksLeft: number, timeMs: number) =>
			`${checksLeft} checks left · ${formatTime(timeMs)}`,
		boards: (n: number) => `${n} board${n === 1 ? '' : 's'}`
	},
	hello: {
		heading: 'Pick a name',
		why: 'It goes on your solves and on the standings. No password, no email — just something for the rest of us to call you.',
		field: 'Your name',
		placeholder: 'Ada',
		submit: 'Start playing',
		submitting: 'Just a moment…',
		note: 'Kept in this browser. Playing somewhere else means picking a name there too — for now.',
		taken: 'Someone already has that one. Try another.'
	},
	alias: {
		empty: 'Pick a name.',
		short: (min: number) => `At least ${min} characters.`,
		long: (max: number) => `At most ${max} characters.`,
		charset: 'Letters, numbers, spaces and - _ . only.',
		substantial: 'Needs a letter or a number in it.'
	},
	/** Names the *other* language, in that language, so it reads to whoever wants it. */
	switcher: { label: 'Language', to: { en: 'English', sv: 'Svenska' } }
};

/** English ordinal suffix. Swedish has its own rule, which is why this is not shared. */
function ordinal(n: number): string {
	if (n % 100 >= 11 && n % 100 <= 13) return 'th';
	return ['th', 'st', 'nd', 'rd'][n % 10] ?? 'th';
}

export type Strings = typeof en;
