import type { ParamMatcher } from '@sveltejs/kit';
import { DEFAULT_LOCALE, isLocale } from '$lib/i18n/locales';

/**
 * Matches a language prefix, and only a real one.
 *
 * The default locale is excluded on purpose: English is served unprefixed, so `/en/boards`
 * must not be a second address for `/boards`. Without that exclusion every page would have
 * two URLs, which is two entries in a browser's history and two rows in any analytics.
 *
 * A matcher rather than a check inside the load, because a matcher makes `/nonsense/boards`
 * a 404 instead of a page that quietly renders in English under a wrong URL.
 */
export const match: ParamMatcher = (param) => isLocale(param) && param !== DEFAULT_LOCALE;
