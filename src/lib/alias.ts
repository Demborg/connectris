/**
 * What a player is allowed to call themselves.
 *
 * The name is the whole of registration, so this is the whole of its validation. Two
 * jobs: say no to a name in words a person can act on, and fold a name down to the key
 * uniqueness is decided on.
 *
 * Deliberately generous about letters. The generator writes Swedish boards and the people
 * playing them have å, ä and ö in their names — a rule that only knows about ASCII would
 * be a rule that tells half the intended audience their name is invalid. Deliberately
 * mean about everything else: no emoji, no control characters, nothing that renders as
 * one thing in a form and another in a list.
 */

export const ALIAS_MIN = 2;
export const ALIAS_MAX = 20;

/** Letters, marks and digits from any script, plus the punctuation names actually use. */
const ALLOWED = /^[\p{L}\p{M}\p{N} '._-]+$/u;

/** A name has to be *something*, not just spacing and dashes. */
const SUBSTANTIAL = /[\p{L}\p{N}]/u;

/**
 * One name, spelled one way.
 *
 * NFKC first, so a name typed with combining accents and the same name typed with
 * precomposed ones are the same name rather than two players. Runs of whitespace collapse
 * to one space, which is what stops "Ada  Lovelace" standing beside "Ada Lovelace".
 */
export function normalizeAlias(raw: string): string {
	return raw.normalize('NFKC').replace(/\s+/gu, ' ').trim();
}

/**
 * The comparison key. Lowercased with `toLowerCase` rather than a locale-aware fold,
 * because the answer has to be the same on every machine that ever writes this key —
 * a Turkish locale lowercasing "I" to "ı" would make one name two.
 */
export function handleOf(alias: string): string {
	return normalizeAlias(alias).toLowerCase();
}

/**
 * Why a name cannot be used, as a code rather than a sentence.
 *
 * It used to be the sentence. That was fine while the game spoke one language and wrong
 * the moment it spoke two: this function runs on the server, which knows the URL's
 * language but has no business holding a copy of the words, and the same code is rendered
 * by whichever catalogue the page is already using.
 */
export type AliasProblem = 'empty' | 'short' | 'long' | 'charset' | 'substantial';

/**
 * Why this name cannot be used, or null if it can. Length is counted in code points: an
 * emoji-free name is still not a run of `char` values, and `.length` would let a name of
 * accented characters run long.
 */
export function aliasProblem(raw: unknown): AliasProblem | null {
	if (typeof raw !== 'string') return 'empty';

	const alias = normalizeAlias(raw);
	const length = [...alias].length;

	if (length === 0) return 'empty';
	if (length < ALIAS_MIN) return 'short';
	if (length > ALIAS_MAX) return 'long';
	if (!ALLOWED.test(alias)) return 'charset';
	if (!SUBSTANTIAL.test(alias)) return 'substantial';

	return null;
}
