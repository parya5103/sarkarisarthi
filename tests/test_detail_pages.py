"""Tests for static job detail pages and sitemap generation."""
import os

from detail_pages import (
    BASE_URL, SITEMAP_FILE, detail_url, job_posting_jsonld,
    render_detail_page, write_detail_pages,
)


def sample_job(job_id='en_sample1', **overrides):
    job = {
        'id': job_id,
        'title': 'Sainik School Nagrota Recruitment 2026 - Apply Online',
        'job_title': 'Trained Graduate Teacher - Computer Science',
        'organization': 'SAINIK SCHOOL NAGROTA',
        'location': 'Nagrota',
        'state': 'Himachal Pradesh',
        'country': 'India',
        'work_mode': 'onsite',
        'description_complete': True,
        'date_posted_verified': True,
        'official_notification_url': 'https://example.gov.in/notice.pdf',
        'advertisement_no': 'SSN-2026-01',
        'employment_type': 'FULL_TIME',
        'url': 'https://example.gov.in/job/1',
        'source': 'employmentnews.gov.in',
        'description': 'Sainik School Nagrota invites eligible candidates to apply for a teaching position. The notification describes the role, required qualifications, selection process and application instructions. Candidates should review the official notification and confirm all details before applying.',
        'important_dates': {'last_date': '21-11-2026', 'found_date': '02-11-2026'},
        'published_date': '02-11-2026',
        'category': 'Teaching',
        'skills': [],
        'scraped_at': '2026-11-03T10:00:00',
        'last_verified': '2026-11-03T10:00:00',
        'status': 'active',
        'verification_status': 'official_verified',
    }
    job.update(overrides)
    return job


class TestJobPostingJsonld:
    def test_verified_fields_included(self):
        job = sample_job()
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert ld['@type'] == 'JobPosting'
        assert ld['title'] == job['job_title']
        assert '<p>' in ld['description'] and '</p>' in ld['description']
        assert ld['identifier']['value'] == 'SSN-2026-01'
        assert ld['employmentType'] == 'FULL_TIME'
        assert 'directApply' not in ld
        assert ld['validThrough'].startswith('2026-11-21T23:59')
        assert ld['hiringOrganization']['name'] == 'SAINIK SCHOOL NAGROTA'
        assert ld['datePosted'] == '2026-11-02'


    def test_non_official_application_url_cannot_enable_job_posting(self):
        job = sample_job(official_notification_url=None,
                         official_application_url='https://exampleportal.in/apply')
        assert job_posting_jsonld(job, detail_url(job['id'])) is None

    def test_truncated_summary_suppresses_job_posting_rich_result(self):
        job = sample_job(description='A detailed recruitment summary with role responsibilities, required qualifications, selection process and application instructions for candidates who meet the published criteria...')
        assert job_posting_jsonld(job, detail_url(job['id'])) is None

    def test_missing_required_job_posting_facts_suppress_rich_result(self):
        for missing in ('verification_status', 'published_date', 'date_posted_verified', 'job_title', 'description_complete', 'organization', 'location', 'country', 'official_notification_url'):
            job = sample_job(**{missing: None})
            assert job_posting_jsonld(job, detail_url(job['id'])) is None

    def test_physical_location_is_structured_without_invented_address_parts(self):
        ld = job_posting_jsonld(sample_job(), detail_url('en_sample1'))
        assert ld['jobLocation']['address']['addressLocality'] == 'Nagrota'
        assert ld['jobLocation']['address']['addressRegion'] == 'Himachal Pradesh'
        assert ld['jobLocation']['address']['addressCountry'] == 'India'
        assert 'streetAddress' not in ld['jobLocation']['address']

    def test_remote_job_uses_remote_location_requirements(self):
        job = sample_job(work_mode='fully_remote', employment_type='FULL_TIME', description='This is a fully remote role. Sainik School Nagrota invites eligible candidates to apply for a teaching position. The notification describes the role, required qualifications, selection process and application instructions. Candidates should review the official notification and confirm all details before applying.')
        job['location'] = None
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert ld['jobLocationType'] == 'TELECOMMUTE'
        assert ld['applicantLocationRequirements']['name'] == 'India'
        assert 'jobLocation' not in ld

    def test_schema_uses_explicit_job_title_and_full_description(self):
        job = sample_job(title='Long recruitment announcement title', job_title='Assistant Teacher')
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert ld['title'] == 'Assistant Teacher'
        assert 'Long recruitment announcement title' not in ld['title']
        assert ld['description'].startswith('<p>')

    def test_unverified_or_unknown_employment_type_is_not_marked_up(self):
        job = sample_job(employment_type='Permanent')
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert 'employmentType' not in ld
        assert 'directApply' not in ld

    def test_remote_job_requires_explicit_remote_description(self):
        job = sample_job(work_mode='fully_remote', employment_type='FULL_TIME')
        assert job_posting_jsonld(job, detail_url(job['id'])) is None

    def test_no_valid_through_without_last_date(self):
        job = sample_job(important_dates={'found_date': '02-11-2026'})
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert 'validThrough' not in ld

    def test_no_organization_without_verified_org(self):
        job = sample_job(organization=None)
        ld = job_posting_jsonld(job, detail_url(job['id']))
        assert ld is None

    def test_no_invented_salary_or_location(self):
        ld = job_posting_jsonld(sample_job(), detail_url('en_sample1'))
        assert 'baseSalary' not in ld
        assert 'streetAddress' not in ld['jobLocation']['address']

    def test_none_when_title_or_description_missing(self):
        assert job_posting_jsonld({'id': 'x'}, 'u') is None


class TestRenderDetailPage:
    def test_job_detail_search_title_is_concise_and_full_heading_is_preserved(self):
        job = sample_job(title='DHFWS Rampurhat Notification 2026 - Apply Online for Various Community Health Assistant Posts')
        page = render_detail_page(job, [])
        title = page.split('<title>', 1)[1].split('</title>', 1)[0]
        assert len(title) <= 60
        assert 'Trained Graduate Teacher - Computer Science' in page
        assert '<meta property="og:title"' in page
        assert '<meta name="twitter:title"' in page

    def test_contains_canonical_and_breadcrumb(self):
        job = sample_job()
        page = render_detail_page(job, [])
        assert 'rel="canonical" href="' + detail_url(job['id']) + '"' in page
        assert 'Breadcrumb' in page
        assert 'href="/sarkari-sarthi/"' in page

    def test_html_escaped(self):
        job = sample_job(title='X <script>alert(1)</script>')
        page = render_detail_page(job, [])
        assert '<script>alert(1)</script>' not in page
        assert '&lt;script&gt;' in page

    def test_jsonld_script_injection_escaped(self):
        job = sample_job(title='X Job', description='Y </script><script>alert(1)</script> This notification describes the role, required qualifications, selection process and application instructions for eligible candidates.')
        page = render_detail_page(job, [])
        assert '</script><script>' not in page
        assert 'u003c' in page

    def test_not_specified_shown_for_missing_last_date(self):
        job = sample_job(important_dates={'found_date': '02-11-2026'})
        page = render_detail_page(job, [])
        assert 'Not specified in official notification' in page

    def test_cancelled_banner(self):
        page = render_detail_page(sample_job(status='cancelled'), [])
        assert 'cancelled' in page

    def test_related_links_only_same_category_active(self):
        rel_a = sample_job('en_rel_a', category='Teaching', title='Related Teaching Job')
        rel_b = sample_job('en_rel_b', category='Banking', title='Banking Job')
        rel_c = sample_job('en_rel_c', category='Teaching', status='cancelled', title='Cancelled Job')
        page = render_detail_page(sample_job(), [rel_a, rel_b, rel_c])
        assert 'Related Teaching Job' in page
        assert 'Banking Job' not in page
        assert 'Cancelled Job' not in page

    def test_links_use_verified_urls(self):
        job = sample_job(
            official_notification_url='https://ssc.gov.in/notice.pdf',
            official_application_url='https://ssc.gov.in/apply',
        )
        page = render_detail_page(job, [])
        assert 'https://ssc.gov.in/notice.pdf' in page
        assert 'https://ssc.gov.in/apply' in page


class TestClosedJobHandling:
    """Expired and cancelled vacancies: honest banners, no misleading
    JobPosting metadata, no active sitemap entries."""

    def test_expired_and_cancelled_get_no_jsonld(self):
        expired = job_posting_jsonld(
            sample_job(status='expired'), detail_url('en_sample1'))
        cancelled = job_posting_jsonld(
            sample_job(status='cancelled'), detail_url('en_sample1'))
        assert expired is None
        assert cancelled is None

    def test_active_job_still_gets_jsonld(self):
        ld = job_posting_jsonld(sample_job(), detail_url('en_sample1'))
        assert ld is not None
        assert ld['@type'] == 'JobPosting'

    def test_closed_job_pages_are_noindex_and_keep_reference_content(self):
        for status in ('expired', 'cancelled'):
            page = render_detail_page(sample_job(status=status), [])
            assert '<meta name="robots" content="noindex,follow">' in page
            assert 'Sarkari Sarthi' in page
            assert 'SarkariSarthi 2.0' not in page

    def test_unverified_job_pages_are_noindex_until_officially_backed(self):
        for verification_status in ('secondary_source_only', 'official_link_pending', 'needs_review'):
            page = render_detail_page(
                sample_job(verification_status=verification_status), []
            )
            assert '<meta name="robots" content="noindex,follow">' in page

    def test_active_job_pages_remain_indexable_by_default(self):
        page = render_detail_page(sample_job(status='active'), [])
        assert 'name="robots" content="noindex' not in page
        assert '<title>' in page and ' | Sarkari Sarthi</title>' in page

    def test_expired_banner_on_detail_page(self):
        page = render_detail_page(sample_job(status='expired'), [])
        assert 'no longer open for' in page
        assert 'kept for reference only' in page

    def test_cancelled_banner_on_detail_page(self):
        page = render_detail_page(sample_job(status='cancelled'), [])
        assert 'marked cancelled' in page

    def test_sitemap_excludes_unverified_job_pages(self, tmp_path):
        verified = sample_job('en_verified1')
        unverified = sample_job(
            'en_unverified1',
            verification_status='secondary_source_only',
        )
        write_detail_pages([verified, unverified], out_root=str(tmp_path))
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert detail_url('en_verified1') in sitemap
        assert detail_url('en_unverified1') not in sitemap
        assert (tmp_path / 'job' / 'en_unverified1' / 'index.html').exists()

    def test_sitemap_excludes_closed_jobs(self, tmp_path):
        active = sample_job('en_open1')
        expired = sample_job('en_closed1', status='expired')
        cancelled = sample_job('en_cancel1', status='cancelled')
        written = write_detail_pages([active, expired, cancelled], out_root=str(tmp_path))
        # Closed jobs still get a reference page (with honest banner)...
        assert written == 3
        assert (tmp_path / 'job' / 'en_closed1' / 'index.html').exists()
        assert (tmp_path / 'job' / 'en_cancel1' / 'index.html').exists()
        # ...but never an active-job sitemap entry.
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert detail_url('en_open1') in sitemap
        assert detail_url('en_closed1') not in sitemap
        assert detail_url('en_cancel1') not in sitemap


class TestWriteDetailPages:
    def test_writes_pages_and_sitemap(self, tmp_path):
        jobs = [sample_job('en_a1'), sample_job('en_a2', category='Banking')]
        written = write_detail_pages(jobs, out_root=str(tmp_path))
        assert written == 2
        assert (tmp_path / 'job' / 'en_a1' / 'index.html').exists()
        assert (tmp_path / 'job' / 'en_a2' / 'index.html').exists()
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert BASE_URL + '/' in sitemap
        assert detail_url('en_a1') in sitemap
        assert detail_url('en_a2') in sitemap
        assert '<urlset' in sitemap and '</urlset>' in sitemap

    def test_sitemap_lastmod_prefers_meaningful_modification_date(self, tmp_path):
        job = sample_job('en_modified1', last_verified='2026-11-05T10:00:00')
        job['modified_at'] = '2026-11-18T09:30:00'
        write_detail_pages([job], out_root=str(tmp_path))
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert '<lastmod>2026-11-18</lastmod>' in sitemap

    def test_sitemap_omits_invalid_lastmod_instead_of_using_build_time(self, tmp_path):
        job = sample_job('en_invaliddate', last_verified='not-a-date')
        write_detail_pages([job], out_root=str(tmp_path))
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert detail_url('en_invaliddate') in sitemap
        assert '<lastmod>' not in sitemap

    def test_orphan_dirs_removed(self, tmp_path):
        stale = tmp_path / 'job' / 'en_gone'
        stale.mkdir(parents=True)
        (stale / 'index.html').write_text('stale', encoding='utf-8')
        write_detail_pages([sample_job('en_keep')], out_root=str(tmp_path))
        assert not stale.exists()
        assert (tmp_path / 'job' / 'en_keep' / 'index.html').exists()

    def test_unsafe_ids_skipped(self, tmp_path):
        evil = sample_job('../evil')
        written = write_detail_pages([evil, sample_job('en_ok1')], out_root=str(tmp_path))
        assert written == 1
        assert (tmp_path / 'job' / 'en_ok1' / 'index.html').exists()
        job_root = tmp_path / 'job'
        assert sorted(p.name for p in job_root.iterdir()) == ['en_ok1']

    def test_lastmod_from_last_verified(self, tmp_path):
        write_detail_pages([sample_job('en_lm1')], out_root=str(tmp_path))
        sitemap = (tmp_path / SITEMAP_FILE).read_text(encoding='utf-8')
        assert '<lastmod>2026-11-03</lastmod>' in sitemap


class TestVerificationChip:
    """Phase 3: honest source-of-information chip on detail pages.

    Known statuses get a labelled chip; unknown or missing statuses
    get nothing (no invented labels)."""

    def test_official_verified_chip(self):
        page = render_detail_page(
            sample_job(verification_status='official_verified'), [])
        assert 'Official source' in page
        assert 'trust-official' in page
        assert 'job-verification' in page

    def test_secondary_source_chip(self):
        page = render_detail_page(
            sample_job(verification_status='secondary_source_only'), [])
        assert 'Secondary source' in page
        assert 'trust-secondary' in page

    def test_unknown_status_gets_no_chip(self):
        page = render_detail_page(
            sample_job(verification_status='some-future-status'), [])
        assert 'job-verification' not in page

    def test_missing_status_gets_no_chip(self):
        page = render_detail_page(sample_job(verification_status=None), [])
        assert 'job-verification' not in page


class TestHomepageSeoMetadata:
    def test_homepage_has_product_name_and_descriptive_search_snippet(self):
        with open(os.path.join(os.path.dirname(__file__), '..', 'index.html'), encoding='utf-8') as handle:
            page = handle.read()
        assert '<title>Sarkari Sarthi: Latest Government Jobs &amp; Results in India</title>' in page
        assert 'name="description"' in page
        assert 'Check eligibility, important dates and source links before applying.' in page
        assert '"name": "Sarkari Sarthi"' in page
