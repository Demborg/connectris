import { formatTime } from '$lib/format';
import type { Best } from '$lib/game/log';
import type { Marked, Strings } from './en';

/**
 * Svenska.
 *
 * Typed as `Strings`, so anything added to `en.ts` and forgotten here fails the build
 * rather than surfacing as an English sentence in the middle of a Swedish page.
 *
 * Two vocabulary decisions run through the whole file and are worth stating once.
 *
 * A *check* is `rättning`, and the button is `Rätta`. It is what a teacher does to an
 * answer, which is exactly what the button does, and it gives a noun for the budget that
 * is a real word rather than a borrowed one. `kontroll` was the alternative and is
 * colourless; `kolla` is the right register but has no comfortable plural.
 *
 * A *board* is `bräde` (plural `bräden`), matching the generator's own docs, and a
 * *puzzle* stays `pussel`. English mixes the two words already and Swedish can too, in the
 * same places.
 */

export const sv: Strings = {
	brand: 'CONNECTRIS',
	title: {
		board: (name: string) => `Connectris — ${name}`,
		boards: 'Connectris — Bräden',
		standings: 'Connectris — Topplista',
		hello: 'Connectris — Välj ett namn'
	},
	nav: {
		today: 'Dagens bräde',
		standings: 'Topplista',
		boards: 'Välj ett bräde',
		allBoards: 'Alla bräden →'
	},
	game: {
		none: 'Inget bräde på svenska än. Det kommer ett i morgon.',
		goal: 'Bilda fem rader om fyra — säkrast överst',
		howToPlay: 'Så spelar du',
		closeRules: 'Stäng reglerna',
		check: 'Rätta',
		checksLeft: (left: number, of: number) => `${left} av ${of} rättningar kvar`,
		tile: (word: string, row: number, rows: number) => `${word}, rad ${row} av ${rows}`,
		closeCategory: 'Stäng kategorin',
		rules: [
			{
				before: 'Sortera alla 20 orden i 5 rader om fyra. Ordningen ',
				mark: 'inuti',
				after: ' en rad spelar ingen roll.',
				style: 'em'
			},
			{
				mark: 'Dra ett ord på ett annat för att byta plats, eller tryck på de två i tur och ordning.',
				style: 'em'
			},
			{
				mark: 'Rättningen rensar bara uppifrån och ner.',
				after:
					' En rad som är rätt men ligger under en felaktig rensas inte. Lägg raden du är säkrast på överst.',
				style: 'strong'
			},
			{
				mark: 'Varje rättning kostar en.',
				after:
					' Att rensa flera rader på en gång är så du behåller dem — och det är vad rätt ordning ger dig.',
				style: 'strong'
			},
			{ mark: 'En rättning säger hur många rader som är rätt — aldrig vilka.', style: 'em' }
		] as Marked[]
	},
	verdict: {
		outOfOrder: 'fler rätt · fel ordning',
		rightNoneAtTop: (count: number) => `${count === 1 ? 'rad' : 'rader'} rätt · ingen överst`,
		right: (count: number) => `${count === 1 ? 'rad' : 'rader'} rätt`
	},
	combo: { 2: 'DUBBEL', 3: 'TRIPPEL', 4: 'QUAD', 5: 'CONNECTRIS' },
	end: {
		won: 'Löst',
		lost: 'Slut på rättningar',
		seeBoard: 'Se brädet',
		questions: 'Frågor',
		score: (time: number, left: number) => `${formatTime(time)} · ${left} kvar`,
		best: (time: number) => ` · bäst ${formatTime(time)}`,
		next: 'Nästa pussel',
		howWasThat: 'Hur var det?',
		// "Lagom" is the word Swedish has and English does not, and this is exactly the
		// question it answers.
		levels: { easy: 'För lätt', right: 'Lagom', hard: 'För svårt' },
		wasItFair: 'Var det rättvist?',
		yes: 'Ja',
		no: 'Nej',
		commentLabel: 'Något mer om det här brädet?',
		commentPlaceholder: 'Något mer? (frivilligt)',
		top: (of: number) => `Etta på topplistan, av ${of}`,
		place: (place: number, of: number) => `${place}${ordinal(place)} av ${of} på topplistan`
	},
	boards: {
		heading: 'Bräden',
		note: 'Alla bräden som fortfarande är i spel. Dina är märkta, oavsett var du spelar dem.',
		today: 'Idag',
		solved: 'Löst',
		played: 'Spelat',
		notPlayed: 'Ospelat',
		record: (time: number, left: number) => `${formatTime(time)} · ${left} kvar`,
		label: (name: string, today: boolean, said: string, best: Best | null) =>
			`${name}${today ? ', dagens bräde' : ''}, ${said}${
				best ? `, bäst ${formatTime(best.timeMs)} med ${best.checksLeft} rättningar kvar` : ''
			}`,
		none: 'Inga bräden på svenska än. Det kommer ett i morgon.'
	},
	top: {
		heading: 'Topplista',
		rule: 'Lösta bräden, sedan rättningar kvar, sedan tid.',
		players: (n: number) => (n === 1 ? 'En spelare hittills.' : `${n} spelare.`),
		empty: 'Ingen har löst något än. Det är en lucka du skulle kunna fylla.',
		you: ' (du)',
		notYet: 'Inte än',
		detail: (checksLeft: number, timeMs: number) =>
			`${checksLeft} rättningar kvar · ${formatTime(timeMs)}`,
		boards: (n: number) => `${n} bräde${n === 1 ? '' : 'n'}`
	},
	hello: {
		heading: 'Välj ett namn',
		why: 'Det står på dina lösningar och på topplistan. Inget lösenord, ingen e-post — bara något för oss andra att kalla dig.',
		field: 'Ditt namn',
		placeholder: 'Ada',
		submit: 'Börja spela',
		submitting: 'Ett ögonblick…',
		note: 'Sparas i den här webbläsaren. Spelar du någon annanstans får du välja ett namn där också — tills vidare.',
		taken: 'Någon har redan det namnet. Välj ett annat.'
	},
	alias: {
		empty: 'Välj ett namn.',
		short: (min: number) => `Minst ${min} tecken.`,
		long: (max: number) => `Högst ${max} tecken.`,
		charset: 'Endast bokstäver, siffror, mellanslag och - _ .',
		substantial: 'Måste innehålla en bokstav eller en siffra.'
	},
	switcher: { label: 'Språk', to: { en: 'English', sv: 'Svenska' } }
};

/**
 * Swedish ordinals: 1:a, 2:a, 3:e … and 11:e, 12:e, which are the exceptions the way the
 * English teens are. Written as a suffix because that is how Swedish abbreviates them.
 */
function ordinal(n: number): string {
	const tens = n % 100;
	if (tens === 11 || tens === 12) return ':e';
	return n % 10 === 1 || n % 10 === 2 ? ':a' : ':e';
}
