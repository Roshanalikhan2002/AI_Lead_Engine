"""Phase 3 contact discovery tests — offline HTML fixtures only."""

from __future__ import annotations

import uuid
from pathlib import Path

from app.models.lead import Lead
from app.models.lead_contact import LeadContact
from app.services.contacts.discovery import discover_lead_contacts
from app.services.contacts.email_extract import (
    classify_contact_type,
    compute_confidence,
    domains_match,
    extract_emails_from_html,
    guess_contact_name,
    normalize_email,
)
from app.services.website.crawler import FetchedPage, WebsiteCrawler

FIXTURES = Path(__file__).parent / "fixtures" / "html"


def _page(html: str, url: str = "https://brightsmile.example/contact") -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        status_code=200,
        html=html,
        load_time_ms=50,
        page_size_bytes=len(html.encode()),
        https_enabled=True,
    )


def test_mailto_and_visible_and_obfuscated_extraction():
    html = """
    <html><body>
      <a href="mailto:sales@brightsmile.example">Email sales</a>
      <p>Reach us at support@brightsmile.example today.</p>
      <p>Obfuscated: booking [at] brightsmile [dot] example</p>
      <p>Ignore test@example.com and user@domain.com</p>
      <img alt="x" src="photo@cdn.com.png" />
    </body></html>
    """
    found = extract_emails_from_html(html, "https://brightsmile.example/contact")
    emails = {e.normalized_email for e in found}
    assert "sales@brightsmile.example" in emails
    assert "support@brightsmile.example" in emails
    assert "booking@brightsmile.example" in emails
    assert "test@example.com" not in emails
    assert "user@domain.com" not in emails


def test_normalize_rejects_invalid():
    assert normalize_email("not-an-email") is None
    assert normalize_email("javascript:alert(1)") is None
    assert normalize_email("test@localhost") is None
    assert normalize_email("name@example.com") is None  # placeholder local+domain
    assert normalize_email("OFFICE@BrightSmile.Example") == "office@brightsmile.example"


def test_classification_and_names():
    assert classify_contact_type("info@x.com") == "business"
    assert classify_contact_type("sales@x.com") == "sales"
    assert classify_contact_type("support@x.com") == "support"
    assert classify_contact_type("booking@x.com") == "booking"
    assert classify_contact_type("john.smith@x.com") == "personal"
    assert guess_contact_name("john.smith@x.com") == "John Smith"
    assert guess_contact_name("info@x.com") is None


def test_domain_match_and_confidence():
    assert domains_match("sales@brightsmile.example", "https://www.brightsmile.example")
    assert not domains_match("owner@gmail.com", "https://brightsmile.example")
    assert (
        compute_confidence(method="mailto", page_kind="contact", domain_match=True) == "high"
    )
    assert compute_confidence(method="obfuscated", page_kind="home", domain_match=False) == "low"


def test_discover_persists_contacts(db_session):
    html = (FIXTURES / "contact_page.html").read_text(encoding="utf-8")
    lead = Lead(
        id=uuid.uuid4(),
        company_name="Bright Smile",
        industry="Dental Clinics",
        website="https://brightsmile.example",
        source="google_places_mock",
    )
    db_session.add(lead)
    db_session.commit()

    def fetch(url: str) -> FetchedPage:
        return _page(html, url=url)

    crawler = WebsiteCrawler(fetch_fn=fetch, resolve_dns=False, respect_robots=False, max_pages=8)
    discovery = discover_lead_contacts(db_session, lead.id, crawler=crawler)
    assert discovery.status == "completed"
    assert discovery.emails_found >= 2
    contacts = db_session.query(LeadContact).filter(LeadContact.lead_id == lead.id).all()
    assert contacts
    assert all(c.source_url for c in contacts)
    assert any(c.domain_match for c in contacts)
    emails = {c.normalized_email for c in contacts}
    # rediscovery should not duplicate
    discover_lead_contacts(db_session, lead.id, crawler=crawler)
    assert db_session.query(LeadContact).filter(LeadContact.lead_id == lead.id).count() == len(emails)


def test_discover_missing_website(db_session):
    lead = Lead(
        id=uuid.uuid4(),
        company_name="No Site",
        website=None,
        source="google_places_mock",
    )
    db_session.add(lead)
    db_session.commit()
    discovery = discover_lead_contacts(db_session, lead.id)
    assert discovery.status == "not_available"
    assert db_session.query(LeadContact).filter(LeadContact.lead_id == lead.id).count() == 0


def test_discover_no_public_email(db_session):
    html = "<html><body><p>No emails here</p></body></html>"
    lead = Lead(
        id=uuid.uuid4(),
        company_name="Quiet Co",
        website="https://quiet.example",
        source="google_places_mock",
    )
    db_session.add(lead)
    db_session.commit()
    crawler = WebsiteCrawler(
        fetch_fn=lambda url: _page(html, url=url),
        resolve_dns=False,
        respect_robots=False,
        max_pages=3,
    )
    discovery = discover_lead_contacts(db_session, lead.id, crawler=crawler)
    assert discovery.status == "no_public_email"


def test_contact_api(client, SessionLocal, monkeypatch):
    html = (FIXTURES / "contact_page.html").read_text(encoding="utf-8")
    db = SessionLocal()
    lead = Lead(
        id=uuid.uuid4(),
        company_name="API Contact Co",
        industry="Dental Clinics",
        website="https://brightsmile.example",
        source="google_places_mock",
    )
    db.add(lead)
    db.commit()
    lead_id = lead.id
    db.close()

    import app.services.contacts.discovery as discovery_mod

    original = discovery_mod.discover_lead_contacts

    def run_job(job_id):
        monkeypatch.setattr(discovery_mod, "SessionLocal", SessionLocal)

        def discover(db, lid, crawler=None, replace_existing=True):
            return original(
                db,
                lid,
                crawler=WebsiteCrawler(
                    fetch_fn=lambda url: _page(html, url=url),
                    resolve_dns=False,
                    respect_robots=False,
                    max_pages=8,
                ),
                replace_existing=replace_existing,
            )

        monkeypatch.setattr(discovery_mod, "discover_lead_contacts", discover)
        discovery_mod.run_contact_discovery_job(job_id)

    monkeypatch.setattr("app.api.routes.contacts.run_contact_discovery_job", run_job)

    started = client.post(f"/api/leads/{lead_id}/discover-contacts")
    assert started.status_code == 202
    job_id = started.json()["job_id"]
    status = client.get(f"/api/leads/contact-jobs/{job_id}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"

    contacts = client.get(f"/api/leads/{lead_id}/contacts")
    assert contacts.status_code == 200
    assert len(contacts.json()) >= 1
    assert all(item["source_url"] for item in contacts.json())

    detail = client.get(f"/api/leads/{lead_id}")
    assert detail.status_code == 200
    assert detail.json()["contact_discovery_status"] in {"completed", "no_public_email"}
    assert detail.json()["contacts"]

    batch = client.post(
        "/api/leads/contacts/discover-batch",
        json={"lead_ids": [str(lead_id)], "without_contacts": False},
    )
    assert batch.status_code == 202

    listed = client.get("/api/leads?contact_discovery_status=completed")
    assert listed.status_code == 200
