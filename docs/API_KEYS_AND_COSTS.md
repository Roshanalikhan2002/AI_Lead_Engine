# API keys, what they unlock, and expected cost

Product code is already built. **LIVE data needs keys in `backend/.env`.** Keys never go in the frontend.

Prices change — confirm on each vendor’s billing page before committing. Figures below are **planning estimates (USD, 2026)**, not invoices.

---

## Must-have for real lead discovery

| Provider | Env vars | What it does | Typical cost |
|----------|----------|--------------|--------------|
| **Google Places API (New)** | `GOOGLE_PLACES_API_KEY` and `GOOGLE_PLACES_MOCK=false` | Find businesses (name, address, rating, website, phone) | Text Search **Pro** ~ **$32 / 1,000** after **5,000 free/month**. If you request website / rating / phone, Google bills **Enterprise** ~ **$35 / 1,000** after **1,000 free**. **Places never returns emails.** |

**Example:** 250 leads ≈ 13 search pages (20 results each). Usually **$0** inside the free allowance. 5,000 leads ≈ 250 searches → still often **$0–$10** depending on fields.

Enable in Google Cloud: Places API (New), billing account, API key restricted to that API + your server IPs.

---

## Must-have for AI qualification + email drafts

| Provider | Env vars | What it does | Typical cost |
|----------|----------|--------------|--------------|
| **OpenAI** | `AI_PROVIDER=openai` `AI_API_KEY=` `AI_MODEL=gpt-4o-mini` | Qualify leads, write outreach drafts, classify replies | **gpt-4o-mini** is cheap: on the order of **~$0.15 / 1M input tokens** and **~$0.60 / 1M output**. |

**Example:** ~1,000 qualifications ≈ **$1–$8** depending on prompt size. Use `gpt-4o-mini` for production volume, not GPT-4o, unless quality requires it.

---

## Needed only when you send real email

| Provider | Env vars | What it does | Typical cost |
|----------|----------|--------------|--------------|
| **Resend** or **SendGrid** (HTTP sending) | `EMAIL_SENDING_PROVIDER=` `EMAIL_SENDING_API_KEY=` `SENDER_EMAIL=` then explicitly `EMAIL_SEND_ENABLED=true` and `EMAIL_TEST_MODE=false` | Send approved outreach | **Resend:** often **3,000 emails/month free**, then low cents per extra. **SendGrid:** free tier then paid plans. |
| **Inbound webhooks** | `REPLY_INBOUND_ENABLED=true` `EMAIL_WEBHOOK_SECRET=` | Receive replies | Usually included with the ESP; no extra SKU. |

Keep defaults (`EMAIL_SEND_ENABLED=false`) until you are ready. Campaign bulk send is still gated.

---

## Optional (quality / SaaS)

| Provider | Env vars | What it does | Typical cost |
|----------|----------|--------------|--------------|
| **Email verification** (ZeroBounce, NeverBounce, Abstract, or custom `http`) | `EMAIL_VERIFICATION_PROVIDER=` `EMAIL_VERIFICATION_API_KEY=` `PROVIDER_TEST_EMAIL=` | Don’t treat “MX exists” as valid | Often **~$0.004–$0.01 per lookup**; some give a free trial (e.g. 100 credits). |
| **Stripe TEST** | `BILLING_PROVIDER=stripe` `STRIPE_SECRET_KEY=sk_test_…` `STRIPE_WEBHOOK_SECRET=` | Subscriptions for *your* customers | **Test mode $0**. Live Stripe: **2.9% + $0.30** per card charge (region varies) — only when you sell LeadFlow as SaaS. |
| **Calendar (Google/Outlook)** | Not live-implemented | Book meetings | Live adapters are **NOT IMPLEMENTED**. Mock only. Google Calendar API itself is typically **free** within quota once OAuth is built. |

Website crawling / contact scraping on public pages uses **your own crawler** — no extra paid API.

---

## Suggested order to “complete” live

1. **Google Places** — real Find Leads  
2. **OpenAI** — qualification + drafts  
3. **Resend + verified sender domain** — one test email to `PROVIDER_TEST_EMAIL`  
4. Verification provider — before volume outreach  
5. Stripe test keys — only if you will charge agencies  
6. Calendar — later (needs implementation)

---

## What you do **not** need yet

- Frontend `VITE_*` provider secrets — never  
- Live Stripe `sk_live_` — do not use during testing  
- Calendar OAuth — product cannot book live Google/Outlook yet  

---

## Monthly planning (small agency)

| Mix | Rough monthly |
|-----|----------------|
| 2,000 Places searches + 2,000 AI quals + 500 emails | **~$5–$40** (often near $0 on Places/OpenAI if volume is low) |
| 20,000 Places Enterprise searches | **hundreds of USD** — this is the expensive SKU; keep field masks tight |

Set Google Cloud **budget alerts**. Cap `quantity` in the UI (already 50–5,000) so one click cannot burn a huge Places bill.
