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
 * Why this name cannot be used, phrased to be shown to the person who typed it, or null
 * if it can. Length is counted in code points: an emoji-free name is still not a run of
 * `char` values, and `.length` would let a name of accented characters run long.
 */
export function aliasProblem(raw: unknown): string | null {
	if (typeof raw !== 'string') return 'Pick a name.';

	const alias = normalizeAlias(raw);
	const length = [...alias].length;

	if (length === 0) return 'Pick a name.';
	if (length < ALIAS_MIN) return `At least ${ALIAS_MIN} characters.`;
	if (length > ALIAS_MAX) return `At most ${ALIAS_MAX} characters.`;
	if (!ALLOWED.test(alias)) return 'Letters, numbers, spaces and - _ . only.';
	if (!SUBSTANTIAL.test(alias)) return 'Needs a letter or a number in it.';

	return null;
}
