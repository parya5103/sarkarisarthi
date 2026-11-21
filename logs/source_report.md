# Sarkari Sarthi daily source report

Run started: 2026-11-21T11:16:46

## Run totals

- archived expired: 0
- duplicates: 36
- expired now: 21
- merged: 0
- new jobs: 0
- raw candidates: 36
- rejected unsafe ids: 0

## Sources

| Source | Status | Duration | Found | New | Dup | Merged | Errors | Notes |
|---|---|---|---|---|---|---|---|---|
| allgovernmentjobs.in | ok | 4.88 | 5 |  |  |  |  |  |
| employmentnews.gov.in | ok |  | 14 |  |  |  |  | official adapter; robots-checked, honest user-agent |
| linkingsky.com | no-jobs | 4.69 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| sarkariprep.in | ok | 2.79 | 17 |  |  |  |  |  |
| www.freejobalert.com | no-jobs | 3.84 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.fresherslive.com | fetch-failed | 9.65 | 0 |  |  |  |  | listing page unreachable or blocked |
| www.freshersnow.com | no-jobs | 36.51 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.rojgarresult.com | no-jobs | 41.63 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |
| www.sahisarkarijobs.in | no-jobs | 4.18 | 0 |  |  |  |  | listing fetched but no vacancy links parsed |

## Needs attention

- linkingsky.com: no-jobs
- www.freejobalert.com: no-jobs
- www.fresherslive.com: fetch-failed
- www.freshersnow.com: no-jobs
- www.rojgarresult.com: no-jobs
- www.sahisarkarijobs.in: no-jobs

A source returning HTTP 200 with zero extracted jobs still appears above: extraction success is measured by parsed jobs, not by HTTP status alone.
