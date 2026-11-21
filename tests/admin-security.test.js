const fs = require('fs');
const path = require('path');

const adminJs = fs.readFileSync(path.resolve(__dirname, '../admin.js'), 'utf8');
const adminHtml = fs.readFileSync(path.resolve(__dirname, '../admin.html'), 'utf8');

describe('admin dashboard security regression guards', () => {
    test('does not ship a hard-coded password hash or client-side password gate', () => {
        expect(adminJs).not.toMatch(/ADMIN_PASSWORD_HASH|function hashPassword|function checkPassword/);
        expect(adminHtml).not.toContain('id="adminPassword"');
    });

    test('never persists a GitHub token in browser storage', () => {
        expect(adminJs).not.toMatch(/(?:sessionStorage|localStorage)\.(?:getItem|setItem)\(['"]ghToken['"]/);
    });

    test('restricts admin writes to the owned Sarkari Sarthi repository', () => {
        expect(adminJs).toContain("const ADMIN_REPOSITORY = 'parya5103/sarkarisarthi'");
        expect(adminJs).toContain('function isAllowedAdminRepository');
    });

    test('documents that GitHub permissions, not a static page password, authorize writes', () => {
        expect(adminHtml).toMatch(/GitHub.*permissions/i);
        expect(adminHtml).toMatch(/noindex, nofollow/i);
    });

    test('backs up the previous manifest and refuses stale concurrent writes', () => {
        expect(adminJs).toContain('manifest_backup_admin_');
        expect(adminJs).toContain('if (latestFile.sha !== manifestSha)');
        expect(adminJs).toContain('currentManifest = JSON.parse(JSON.stringify(manifest))');
    });

    test('does not treat a manual edit as source re-verification', () => {
        expect(adminJs).toContain("merged.verification_status = 'needs_review'");
        expect(adminJs).not.toMatch(/merged\.last_verified\s*=\s*new Date/);
        expect(adminJs).toContain("newJobData.verification_status = 'needs_review'");
    });

    test('clears the in-memory token when the dashboard logs out', () => {
        const logoutBody = adminJs.match(/function logout\(\)\s*\{([\s\S]*?)\n\}/);
        expect(logoutBody).not.toBeNull();
        expect(logoutBody[1]).toContain("ghToken = ''");
    });
});
