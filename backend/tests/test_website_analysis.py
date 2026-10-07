"""Phase 2 website analysis tests — local HTML fixtures only, no external network."""

from __future__ import annotations

import uuid
from pathlib import Path

import httpx
import pytest

from app.models.lead import Lead
from app.models.lead_opportunity import LeadOpportunity
from app.models.website_analysis import WebsiteAnalysis
from app.services.website.analyzer import analyze_lead_website, run_website_analysis_job
from app.services.website.crawler import CrawlResult, FetchedPage, WebsiteCrawler
from app.services.website.html_signals import analyze_html
from app.services.website.opportunities import detect_opportunities
from app.services.website.scoring import compute_scores
from app.services.website.url_safety import UnsafeURLError, assert_public_url, normalize_website_url

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _page(html: str, url: str = "https://brightsmile.example/") -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=200,
        html=html,
        load_time_ms=120,
        page_size_bytes=len(html.encode()),
        https_enabled=True,
    )


def _offline_crawler(html: str) -> WebsiteCrawler:
    return WebsiteCrawler(
        fetch_fn=lambda url: _page(html, url=url),
        resolve_dns=False,
        respect_robots=False,
        max_pages=1,
    )


def test_normalize_website_url_adds_https():
    assert normalize_website_url("example.com/path") == "https://example.com/path"
    assert normalize_website_url("https://Example.com") == "https://Example.com"
    assert normalize_website_url("  ") is None


def test_ssrf_blocks_localhost_and_private_ips():
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://localhost/admin", resolve_dns=False)
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://127.0.0.1/", resolve_dns=False)
    with pytest.raises(UnsafeURLError):
        assert_public_url("http://192.168.1.10/", resolve_dns=False)


def test_html_signals_good_site():
    html = (FIXTURES / "good_site.html").read_text(encoding="utf-8")
    signals = analyze_html(_page(html))
    assert signals.has_title
    assert signals.has_meta_description
    assert signals.has_h1
    assert signals.has_viewport
    assert signals.has_canonical
    assert signals.has_favicon
    assert signals.has_contact_form
    assert signals.has_booking
    assert signals.booking_evidence
    assert signals.has_chatbot
    assert signals.chatbot_provider == "tawk"
    assert "Shopify" in signals.technology_detected
    assert signals.has_clear_cta
    assert signals.has_phone
    assert signals.has_email


def test_booking_not_triggered_by_plain_text_appointment():
    html = (FIXTURES / "weak_site.html").read_text(encoding="utf-8")
    signals = analyze_html(_page(html))
    assert signals.has_booking is False
    assert signals.has_chatbot is False
    assert signals.has_title is False


def test_seo_and_mobile_scoring_explainable():
    html = (FIXTURES / "good_site.html").read_text(encoding="utf-8")
    page = _page(html)
    crawl = CrawlResult(
        start_url=page.url,
        reachable=True,
        pages=[page],
        http_status=200,
        final_url=page.final_url,
        https_enabled=True,
        load_time_ms=120,
    )
    signals = analyze_html(page)
    scores = compute_scores(crawl, signals)
    assert scores.seo_score == 100
    assert scores.mobile_score == 100
    assert scores.performance_score is None
    assert scores.website_score is not None
    assert scores.score_reasons


def test_opportunities_no_website():
    ops = detect_opportunities(has_website=False, industry="Dental Clinics", crawl=None, signals=None, scores=None)
    assert any(o.service == "website_development" and o.confidence == "high" for o in ops)


def test_crawler_uses_fetch_fn_without_network():
    html = (FIXTURES / "good_site.html").read_text(encoding="utf-8")
    with _offline_crawler(html) as crawler:
        result = crawler.crawl("brightsmile.example")
    assert result.reachable
    assert result.pages[0].html


def test_crawler_timeout():
    def fetch(_url: str) -> FetchedPage:
        raise httpx.TimeoutException("timeout")

    with WebsiteCrawler(fetch_fn=fetch, resolve_dns=False, respect_robots=False) as crawler:
        result = crawler.crawl("https://slow.example")
    assert result.reachable is False
    assert "timed out" in (result.error_message or "").lower()


def test_analyze_missing_website(db_session):
    lead = Lead(
        id=uuid.uuid4(),
        company_name="No Site LLC",
        industry="Dental Clinics",
        website=None,
        source="google_places_mock",
    )
    db_session.add(lead)
    db_session.commit()

    analysis = analyze_lead_website(db_session, lead.id, crawler=_offline_crawler("<html></html>"))
    assert analysis.analysis_status == "not_available"
    ops = db_session.query(LeadOpportunity).filter(LeadOpportunity.lead_id == lead.id).all()
    assert any(o.service == "website_development" for o in ops)


def test_analyze_and_reanalyze(db_session):
    html = (FIXTURES / "good_site.html").read_text(encoding="utf-8")
    lead = Lead(
        id=uuid.uuid4(),
        company_name="Bright Smile",
        industry="Dental Clinics",
        website="https://brightsmile.example",
        source="google_places_mock",
    )
    db_session.add(lead)
    db_session.commit()

    crawler = _offline_crawler(html)
    first = analyze_lead_website(db_session, lead.id, crawler=crawler)
    assert first.analysis_status == "completed"
    assert first.seo_score == 100
    assert first.has_booking is True
    assert first.performance_score is None
    assert db_session.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead.id).count() == 1

    second = analyze_lead_website(db_session, lead.id, crawler=crawler)
    assert second.id == first.id
    assert db_session.query(WebsiteAnalysis).filter(WebsiteAnalysis.lead_id == lead.id).count() == 1


def test_website_api_endpoints(client, SessionLocal, monkeypatch):
    html = (FIXTURES / "good_site.html").read_text(encoding="utf-8")
    weak = (FIXTURES / "weak_site.html").read_text(encoding="utf-8")
    db = SessionLocal()
    lead = Lead(
        id=uuid.uuid4(),
        company_name="API Dental",
        industry="Dental Clinics",
        country="USA",
        website="https://brightsmile.example",
        source="google_places_mock",
    )
    weak_lead = Lead(
        id=uuid.uuid4(),
        company_name="Weak Clinic",
        industry="Dental Clinics",
        country="USA",
        website="https://weak.example",
        source="google_places_mock",
    )
    db.add_all([lead, weak_lead])
    db.commit()
    lead_id = lead.id
    weak_id = weak_lead.id
    db.close()

    import app.services.website.analyzer as analyzer_mod

    original_analyze = analyzer_mod.analyze_lead_website

    def run_job(job_id):
        monkeypatch.setattr(analyzer_mod, "SessionLocal", SessionLocal)

        def analyze(db, lid, crawler=None):
            fixture = weak if lid == weak_id else html
            return original_analyze(db, lid, crawler=_offline_crawler(fixture))

        monkeypatch.setattr(analyzer_mod, "analyze_lead_website", analyze)
        analyzer_mod.run_website_analysis_job(job_id)

    monkeypatch.setattr("app.api.routes.websites.run_website_analysis_job", run_job)

    started = client.post(f"/api/websites/analyze/{lead_id}")
    assert started.status_code == 202
    job_id = started.json()["job_id"]

    status = client.get(f"/api/websites/jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    analysis = client.get(f"/api/websites/{lead_id}")
    assert analysis.status_code == 200
    assert analysis.json()["analysis_status"] == "completed"
    assert analysis.json()["performance_score"] is None

    detail = client.get(f"/api/leads/{lead_id}")
    assert detail.status_code == 200
    assert detail.json()["website_analysis"]["seo_score"] == 100

    weak_job = client.post(f"/api/websites/analyze/{weak_id}")
    assert weak_job.status_code == 202
    assert client.get(f"/api/websites/jobs/{weak_job.json()['job_id']}").json()["status"] == "completed"
    weak_detail = client.get(f"/api/leads/{weak_id}")
    assert weak_detail.json()["opportunities"]

    batch = client.post(
        "/api/websites/analyze-batch",
        json={"lead_ids": [str(lead_id)], "not_analyzed": False},
    )
    assert batch.status_code == 202

    listed = client.get("/api/leads?website_analysis_status=completed")
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1

    reanalyze = client.post(f"/api/leads/{lead_id}/reanalyze-website")
    assert reanalyze.status_code == 202
