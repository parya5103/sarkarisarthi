const fs = require('fs');
const vm = require('vm');

const source = fs.readFileSync(require.resolve('../script.js'), 'utf8');
const dateMatch = source.match(/function parseJobDate\(dateStr\) \{[\s\S]*?\n\}/);
const match = source.match(/function filterExpiredJobs\(jobs\) \{[\s\S]*?\n\}/);
if (!dateMatch || !match) throw new Error('job date helpers not found');
const context = {};
vm.runInNewContext(dateMatch[0] + '\n' + match[0] + '\nglobalThis.filterExpiredJobs = filterExpiredJobs;', context);

describe('filterExpiredJobs', () => {
  test('excludes expired and cancelled lifecycle states', () => {
    const result = context.filterExpiredJobs([
      { id: 'expired-status', status: 'expired' },
      { id: 'cancelled-status', status: 'cancelled' },
      { id: 'closed-status', status: 'closed' },
      { id: 'expired-verification', status: 'active', verification_status: 'expired' },
      { id: 'cancelled-verification', status: 'active', verification_status: 'cancelled' }
    ]);
    expect(result).toHaveLength(0);
  });

  test('keeps needs-review listings visible while retaining the warning state', () => {
    const result = context.filterExpiredJobs([
      { id: 'needs-review', status: 'active', verification_status: 'needs_review' }
    ]);
    expect(result.map(job => job.id)).toEqual(['needs-review']);
  });

  test('keeps active jobs with no known deadline and future deadlines', () => {
    const result = context.filterExpiredJobs([
      { id: 'unknown-deadline', status: 'active' },
      { id: 'future-deadline', status: 'active', important_dates: { last_date: '31-12-2099' } }
    ]);
    expect(result.map(job => job.id)).toEqual(['unknown-deadline', 'future-deadline']);
  });

  test('excludes a job whose application deadline has passed', () => {
    const result = context.filterExpiredJobs([
      { id: 'past-deadline', status: 'active', important_dates: { last_date: '01-01-2000' } }
    ]);
    expect(result).toHaveLength(0);
  });
});
