/**
 * @jest-environment jsdom
 */

// Define window.location with an absolute base
Object.defineProperty(window, 'location', {
  value: {
    href: 'http://localhost/'
  }
});

const fs = require('fs');
const path = require('path');

const scriptContent = fs.readFileSync(path.resolve(__dirname, '../script.js'), 'utf8');

// Load script.js functions into the global scope
eval(scriptContent);

describe('sanitizeURL', () => {
    test('should return "#" for falsy urls', () => {
        expect(sanitizeURL('')).toBe('#');
        expect(sanitizeURL(null)).toBe('#');
        expect(sanitizeURL(undefined)).toBe('#');
    });

    test('should return correct URL for http and https with proper URL resolution', () => {
        // Because the implementation uses \`new URL(url, window.location.href).href\`,
        // simple http:// URLs will have a trailing slash appended.
        expect(sanitizeURL('http://example.com')).toBe('http://example.com/');
        expect(sanitizeURL('https://example.com')).toBe('https://example.com/');
        expect(sanitizeURL('http://example.com/path?query=1')).toBe('http://example.com/path?query=1');
    });

    test('should resolve relative paths against window.location.href safely', () => {
        // Since we mocked window.location.href to 'http://localhost/', relative paths will resolve against it.
        expect(sanitizeURL('/path/to/resource')).toBe('http://localhost/path/to/resource');
        expect(sanitizeURL('./path/to/resource')).toBe('http://localhost/path/to/resource');
        expect(sanitizeURL('../path/to/resource')).toBe('http://localhost/path/to/resource');
    });

    test('should return "#" for blocked protocols like javascript:', () => {
        expect(sanitizeURL('javascript:alert(1)')).toBe('#');
        expect(sanitizeURL('  JaVaScRiPt:alert(1)')).toBe('#');
        expect(sanitizeURL('data:text/html,<html>')).toBe('#');
        expect(sanitizeURL('vbscript:msgbox("hello")')).toBe('#');
    });

    test('should fallback to escaping for unparseable URLs that start with relative characters', () => {
        // An invalid URL format might cause `new URL` to throw. We can force a throw by overriding `URL`
        // or passing a completely broken URL. However, the browser's URL parser is very permissive.
        // Let's create a test case that forces an error.
        const originalURL = global.URL;
        global.URL = function() { throw new Error('mock error'); };

        expect(sanitizeURL('/relative-path')).toBe('/relative-path');
        expect(sanitizeURL('./relative-path')).toBe('./relative-path');

        // Restore URL
        global.URL = originalURL;
    });
});

describe('getVerificationInfo', () => {
    test('returns the official label for official_verified', () => {
        const info = getVerificationInfo('official_verified');
        expect(info).not.toBeNull();
        expect(info.text).toBe('Official Source');
        expect(info.cls).toContain('trust-official');
    });

    test('is case-insensitive for known statuses', () => {
        const info = getVerificationInfo('SECONDARY_SOURCE_ONLY');
        expect(info.text).toBe('Secondary Source');
    });

    test('returns null for missing, empty or unknown statuses', () => {
        expect(getVerificationInfo(null)).toBeNull();
        expect(getVerificationInfo(undefined)).toBeNull();
        expect(getVerificationInfo('')).toBeNull();
        expect(getVerificationInfo('totally-unknown-status')).toBeNull();
    });
});

describe('bookmarks', () => {
    beforeEach(() => {
        localStorage.clear();
    });

    test('empty storage means no bookmarks', () => {
        expect(getBookmarks()).toEqual([]);
        expect(isBookmarked('job-1')).toBe(false);
    });

    test('toggleBookmark adds then removes a job id', () => {
        expect(toggleBookmark('job-1')).toBe(true);
        expect(isBookmarked('job-1')).toBe(true);
        expect(getBookmarks()).toEqual(['job-1']);

        expect(toggleBookmark('job-1')).toBe(false);
        expect(isBookmarked('job-1')).toBe(false);
        expect(getBookmarks()).toEqual([]);
    });

    test('corrupt stored JSON degrades to an empty list', () => {
        localStorage.setItem('sarkariBookmarks', 'not-json{{');
        expect(getBookmarks()).toEqual([]);
        expect(isBookmarked('job-1')).toBe(false);
    });

    test('non-array stored value degrades to an empty list', () => {
        localStorage.setItem('sarkariBookmarks', '12345');
        expect(getBookmarks()).toEqual([]);
    });

    test('toggleBookmark ignores falsy ids', () => {
        expect(toggleBookmark('')).toBe(false);
        expect(toggleBookmark(null)).toBe(false);
    });
});

describe('getRecordTimestamp', () => {
    test('newer record sorts later than older record', () => {
        const newer = getRecordTimestamp({ last_verified: '2026-11-03T10:00:00' });
        const older = getRecordTimestamp({ last_verified: '2026-10-01T10:00:00' });
        expect(newer).toBeGreaterThan(older);
    });

    test('falls back to scraped_at then found_date', () => {
        const viaScraped = getRecordTimestamp({ scraped_at: '2026-11-02T08:00:00' });
        expect(viaScraped).toBeGreaterThan(0);
        const viaFound = getRecordTimestamp({
            important_dates: { found_date: '2026-11-01' }
        });
        expect(viaFound).toBeGreaterThan(0);
    });

    test('returns 0 when no usable timestamp exists', () => {
        expect(getRecordTimestamp({})).toBe(0);
        expect(getRecordTimestamp(null)).toBe(0);
        expect(getRecordTimestamp({ last_verified: 'not-a-date' })).toBe(0);
    });
});
