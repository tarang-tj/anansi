# Target selection

Every target must clear four bars: publicly accessible, outside Bright Data's
800+ pre-built scraper library, served as static HTML, and permitted by
`robots.txt`. The second bar is the one that voids a submission outright
(hackathon best-practice #1), so it is argued explicitly per target rather than
assumed.

Two shapes are usable:

- **Shape A** — a directory linking to one page per organisation. Gives both a
  Discovery scraper (the list) and a PDP scraper (the detail pages).
- **Shape B** — one page listing many organisations, each in its own repeating
  DOM block carrying per-org fields. Discovery only.

## Verified

### Fairfax County CSB Community Resources List — Shape B

- **List page:** https://www.fairfaxcounty.gov/community-services-board/publications/community-resources-list
- **Verified by:** direct `curl`. HTTP 200, 140,665 bytes, 0 `<table>`, 484
  `<li>`, 58,579 characters of visible text.
- **Structure:** service-category headings (`Basic needs (food, emergency
  financial assistance)`, `Shelters`, `Health care`, `Housing`,
  `Domestic violence resources`, `Older adults`, …) each followed by a list of
  organisations. Sampling the "Basic needs" section: 11 items, every one
  carrying an organisation name, a service description, and a phone number.
- **Extractable fields:** `name`, `phone`, `services` (from the description),
  `category` (from the parent heading). No structured address, no hours.
- **robots.txt:** standard Drupal ruleset. Disallows `/core/`, `/admin/`,
  `/search/`, `/user/*`. Nothing covers `/community-services-board/*`. Permitted.
- **Long-tail argument:** a single county behavioural-health agency's resource
  list. It is not a commercial marketplace, has no API, and no pre-built scraper
  would ever target it. A judge asking "why not use the pre-built scraper?" has
  no candidate to point at.
- **Why it is a good demo target:** the category-from-heading extraction is
  genuinely non-trivial — the category is not inside the record, it is implied by
  document position, which is exactly the kind of extraction that breaks when a
  page is restructured.
- **Risk:** the absence of an `hours` field means the headline "pantry with no
  hours" story is carried by the testbed rather than by this target. Its most
  breakable field is `phone`.

## Rejected, with reasons

| Candidate | Why rejected |
|---|---|
| LA County Services Locator | Paginated search application, not a static directory. URL structure per result is unclear and the listing is JS-driven. |
| NYC Community Fridge map | Entries link into an embedded Google Maps widget rather than internal pages. Scraping the widget is scraping Google Maps, which the pre-built library already covers. |
| Calvert County MD Community Resources | Serves 217KB of static HTML and `robots.txt` permits the path, but the per-organisation content sits behind CMS tabs and it is unconfirmed whether those produce distinct URLs. Parked, not dismissed. |

## Unverified candidates

Regional food banks commonly publish partner-agency listings, which is the most
likely source of a genuine Shape A target. These returned HTTP 200 but their
per-agency URL structure has **not** been confirmed:

- Second Harvest Food Bank of Northwest Pennsylvania
- Central Pennsylvania Food Bank
- Food Bank For New York City

**None of these may be built against until three distinct detail-page URLs are
loaded and shown to carry different organisation data.** A directory that turns
out to be a JS app or an embedded widget costs 15-25 minutes of scraper
generation to discover, which is the most expensive way to learn it.

## Why Shape A is scarce here — a finding, not a dead end

Searching for a true directory-plus-detail-pages target in this vertical kept
failing the same way, and the pattern is worth stating because it argues for the
project rather than against it.

Checked and rejected on structure:

| Site | What it actually serves |
|---|---|
| Clark County Food Bank `/our-network` | 246KB of HTML, but 93 internal links all sit at the root, there are no per-agency blocks, and the agency list arrives in a single JSON blob consumed by a map. |
| All Faiths Food Bank partner directory | 131KB, only 2 phone numbers in the markup, and an embedded map widget carrying the actual listings. |

Small aid organisations publish their directories through **embedded third-party
map widgets** or as **flat CMS pages**. Almost none of them expose a structured
per-organisation URL, because almost none of them have a CMS that would produce
one.

That is precisely why this data is the long tail, and precisely why it is worth
the project. There is no structured layer to scrape, no API, and no pre-built
scraper — the information exists only as markup that a person hand-maintained
and will hand-change without warning. It is also a reason to be careful:
scraping the embedded widget usually means scraping Google Maps, which the
pre-built library already covers and which best-practice #1 rules out.

## Current position

One verified real target (Fairfax, Shape B) plus the mutation testbed is enough
to satisfy the rules — the requirement is a custom Scraper Studio scraper, not a
large fleet. Expanding to 3-4 targets happens in Phase 1 once the account is
live, and Shape A verification is the gate for each addition.
