import { describe, expect, it } from 'vitest';
import { nextFrom } from './next';

const next = (query: string) => nextFrom(new URL(`http://localhost/hello${query}`));

describe('where registering sends you', () => {
	it('resumes the page you were trying to reach', () => {
		expect(next('?next=%2Fp%2Fgen-1')).toBe('/p/gen-1');
	});

	it('falls back to today’s board when it was not told', () => {
		expect(next('')).toBe('/');
		expect(next('?next=')).toBe('/');
	});

	it('refuses to send anyone off this site', () => {
		// `next` is written by whoever wrote the link. An absolute URL here is the standard
		// open-redirect shape, and `//host` is the case that looks relative and is not.
		expect(next('?next=https%3A%2F%2Felsewhere.example')).toBe('/');
		expect(next('?next=%2F%2Felsewhere.example')).toBe('/');
		expect(next('?next=javascript%3Aalert(1)')).toBe('/');
	});
});
