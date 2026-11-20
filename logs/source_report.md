# Sarkari Sarthi daily source report

Run started: 2026-11-20T19:51:35

## Run totals

- archived expired: 0
- duplicates: 23
- expired now: 21
- merged: 0
- new jobs: 17
- raw candidates: 40
- rejected unsafe ids: 0

## Sources

| Source | Status | Duration | Found | New | Dup | Merged | Errors | Notes |
|---|---|---|---|---|---|---|---|---|
| allgovernmentjobs.in | ok | 4.43 | 9 |  |  |  |  |  |
| employmentnews.gov.in | ok |  | 14 |  |  |  |  | official adapter; robots-checked, honest user-agent |
| linkingsky.com | no-jobs | 3.61 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| sarkariprep.in | ok | 7.34 | 17 | 17 |  |  |  |  |
| www.freejobalert.com | no-jobs | 4.28 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.fresherslive.com | fetch-failed | 10.41 | 0 |  |  |  |  | listing page unreachable or blocked |
| www.freshersnow.com | no-jobs | 4.13 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.rojgarresult.com | no-jobs | 4.09 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.sarkarinaukridaily.in | no-jobs | 3.65 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |

## Needs attention

- linkingsky.com: no-jobs
- www.freejobalert.com: no-jobs
- www.fresherslive.com: fetch-failed
- www.freshersnow.com: no-jobs
- www.rojgarresult.com: no-jobs
- www.sarkarinaukridaily.in: no-jobs

A source returning HTTP 200 with zero extracted jobs still appears above: extraction success is measured by parsed jobs, not by HTTP status alone.
