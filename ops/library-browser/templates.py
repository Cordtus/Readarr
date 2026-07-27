from html import escape


PAGE_STYLE = """
:root { color-scheme: light; --ink: #2b211b; --paper: #f3e6c7; --paper-deep: #dfc99e; --walnut: #4a291d; --brass: #c29446; --copper: #b36a42; }
* { box-sizing: border-box; }
html { min-width: 320px; }
body { margin: 0; color: var(--ink); background: #221813; font-family: Georgia, 'Times New Roman', serif; }
a { color: inherit; }
a:focus-visible { outline: 3px solid #f8d27c; outline-offset: 4px; border-radius: 2px; }
.landing { min-height: 100vh; display: grid; place-items: center; padding: clamp(1.25rem, 4vw, 4rem); background: linear-gradient(90deg, rgba(27,13,9,.72), rgba(27,13,9,.12) 55%, rgba(27,13,9,.65)), url('/library/assets/reading-room.webp') center/cover; }
.landing-card { width: min(100%, 70rem); display: grid; gap: clamp(2rem, 8vw, 7rem); align-items: end; grid-template-columns: minmax(12rem, .7fr) minmax(16rem, 1fr); }
.plaque { justify-self: start; padding: 1.1rem 1.4rem 1.25rem; color: #f8e7bd; background: rgba(52, 27, 18, .88); border: 1px solid var(--brass); box-shadow: 0 0 0 5px rgba(38, 19, 12, .45), 0 1rem 3rem rgba(0,0,0,.35); }
.plaque-kicker { margin: 0 0 .3rem; color: #e4b967; font: .7rem/1.2 Arial, sans-serif; letter-spacing: .18em; text-transform: uppercase; }
.plaque h1 { margin: 0; font-size: clamp(1.8rem, 4vw, 3.3rem); line-height: .95; font-weight: 500; }
.shelves { display: grid; gap: 1.2rem; }
.shelf-link { position: relative; display: block; padding: 1.1rem 1.3rem 1rem 4.2rem; color: #f7e4ba; text-decoration: none; background: linear-gradient(#5f3625, #352017); border: 1px solid rgba(235, 190, 105, .6); box-shadow: inset 0 -8px 0 rgba(22, 11, 7, .35), 0 10px 18px rgba(0,0,0,.32); transition: transform .18s ease, filter .18s ease; }
.shelf-link::before { content: ''; position: absolute; left: 1.25rem; top: .8rem; width: 1.8rem; height: 2.2rem; border: 2px solid var(--brass); border-radius: 2px; box-shadow: inset 5px 0 rgba(255,255,255,.12); }
.shelf-link:hover { transform: translateY(-3px); filter: brightness(1.12); }
.shelf-link strong { display: block; font-size: 1.35rem; font-weight: 500; }
.shelf-link span { display: block; margin-top: .25rem; color: #e0bd7c; font: .76rem Arial, sans-serif; letter-spacing: .08em; text-transform: uppercase; }
.request-link { border-color: rgba(235, 190, 105, .85); }
.archives-notice { margin: .2rem 0 0; padding: .9rem 1.1rem; color: rgba(248, 231, 189, .72); background: rgba(36, 19, 13, .58); border-left: 2px solid rgba(194, 148, 70, .62); font: .82rem/1.45 Arial, sans-serif; }
.archives-notice strong { display: block; color: #e4b967; font-size: .7rem; letter-spacing: .14em; text-transform: uppercase; }
.archives-notice p { margin: .3rem 0 0; }
.catalog-page { min-height: 100vh; padding: clamp(1.25rem, 4vw, 4rem); background: radial-gradient(circle at 20% 0, rgba(255,255,255,.55), transparent 35rem), var(--paper); }
.request-page { min-height: 100vh; padding: clamp(1.25rem, 4vw, 4rem); background: radial-gradient(circle at 10% 0, rgba(255,255,255,.58), transparent 32rem), var(--paper); }
.request-desk { width: min(100%, 42rem); margin: 0 auto; padding: clamp(1.4rem, 5vw, 3rem); background: rgba(255,250,235,.55); border: 1px solid rgba(74,41,29,.38); box-shadow: 0 .8rem 2.5rem rgba(50, 28, 16, .15); }
.request-desk h1 { margin: 0; color: var(--walnut); font-size: clamp(2.2rem, 7vw, 4rem); font-weight: 500; line-height: .95; }
.request-kicker { margin: 0 0 .45rem; color: #765d47; font: .72rem Arial, sans-serif; letter-spacing: .16em; text-transform: uppercase; }
.request-intro { max-width: 35rem; margin: 1rem 0 1.7rem; color: #604938; line-height: 1.5; }
.request-form { display: grid; gap: .65rem; }
.request-form label { color: var(--walnut); font: .76rem Arial, sans-serif; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.request-form input { width: 100%; padding: .8rem .9rem; color: var(--ink); background: #fffaf0; border: 1px solid rgba(74,41,29,.55); border-radius: 0; font: 1rem Georgia, 'Times New Roman', serif; }
.request-form input:focus { outline: 3px solid rgba(194,148,70,.55); outline-offset: 2px; }
.request-form button { justify-self: start; padding: .75rem 1rem; color: #f8e7bd; background: var(--walnut); border: 1px solid var(--brass); font: .75rem Arial, sans-serif; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; cursor: pointer; }
.request-form button:hover { background: #603625; }
.request-message { margin: 0 0 1.2rem; padding: .75rem .9rem; color: #5e412c; background: rgba(194,148,70,.14); border-left: 3px solid var(--copper); }
.audio-catalog { --catalog-accent: var(--copper); --paper: #f0ddc2; }
.catalog { width: min(100%, 62rem); margin: 0 auto; }
.breadcrumb { margin-bottom: 2rem; color: #765d47; font: .82rem Arial, sans-serif; }
.breadcrumb a { text-underline-offset: .2em; }
.catalog-header { display: flex; justify-content: space-between; gap: 1rem; align-items: end; border-bottom: 3px double var(--walnut); padding-bottom: 1rem; }
.catalog-header h1 { margin: 0; font-size: clamp(2.2rem, 6vw, 4.4rem); font-weight: 500; line-height: .9; }
.audio-catalog .catalog-header { border-color: var(--catalog-accent); }
.audio-catalog .download { color: var(--catalog-accent); }
.audio-detail, .bookmark-detail { display: inline-block; margin-left: .4em; color: var(--catalog-accent); font: .45em Arial, sans-serif; vertical-align: .35em; }
.bookmark-detail { display: inline-block; width: .65em; height: 1em; margin-left: .15em; background: var(--catalog-accent); clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 72%, 0 100%); }
.count { margin: 0; color: #765d47; font: .78rem Arial, sans-serif; white-space: nowrap; }
.catalog-list { margin-top: 1.2rem; border-top: 1px solid rgba(74,41,29,.35); }
.catalog-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 1.5rem; align-items: center; padding: 1rem .4rem; border-bottom: 1px solid rgba(74,41,29,.25); }
.catalog-name { min-width: 0; overflow-wrap: anywhere; font-size: 1.1rem; }
.catalog-meta { color: #765d47; font: .78rem Arial, sans-serif; white-space: nowrap; }
.download { color: var(--walnut); font: .78rem Arial, sans-serif; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; text-underline-offset: .2em; }
.empty { margin-top: 2rem; padding: 3rem 1rem; color: #765d47; border: 1px dashed rgba(74,41,29,.5); text-align: center; font-style: italic; font-size: 1.2rem; }
@media (max-width: 650px) { .landing-card { grid-template-columns: 1fr; gap: 3rem; } .plaque { justify-self: stretch; } .catalog-header { display: block; } .count { margin-top: .8rem; } .catalog-row { grid-template-columns: minmax(0, 1fr) auto; gap: .45rem 1rem; } .catalog-meta { grid-column: 1; } .download { grid-column: 2; grid-row: 1 / span 2; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }
"""


def page(title, body, *, body_class=""):
    return "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>{}</title><style>{}</style></head><body class='{}'>{}</body></html>".format(
        escape(title), PAGE_STYLE, body_class, body
    )


def landing():
    body = """<main class="landing"><div class="landing-card"><section class="plaque" aria-labelledby="library-title"><p class="plaque-kicker">A private collection</p><h1 id="library-title">The Library<br>of Bex</h1></section><div><nav class="shelves" aria-label="Library shelves"><a class="shelf-link" href="/library/Books/"><strong>Books</strong><span>Browse the collection</span></a><a class="shelf-link" href="/library/Audiobooks/"><strong>Audiobooks</strong><span>Listen to the collection</span></a><a class="shelf-link request-link" href="/library/request/"><strong>Request a book</strong><span>Ask the librarian</span></a></nav>{}</div></div></main>""".format(archives_notice())
    return page("The Library of Bex", body, body_class="landing-page")


def archives_notice():
    return '<aside class="archives-notice"><strong>The archives</strong><p>The archives are not yet open to the public</p></aside>'


def request_desk(message=None):
    message_html = '<p class="request-message" role="status">{}</p>'.format(escape(message)) if message else ""
    body = """<main class="request-page"><article class="request-desk"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="/library/">The Library of Bex</a> / <span aria-current="page">Request a book</span></nav><p class="request-kicker">The librarian's desk</p><h1>Request a book</h1><p class="request-intro">Tell the librarian what you would like to read, and the catalogue will be searched for a suitable edition.</p>{}<form class="request-form" action="/library/request/search/" method="get"><label for="request-query">Title, author, or ISBN</label><input id="request-query" name="term" type="search" required><button type="submit">Search the catalogue</button></form></article></main>""".format(message_html)
    return page("Request a book · The Library of Bex", body, body_class="request-page")


def request_results(results):
    rows = []
    for token, candidate in results:
        author = " by {}".format(escape(candidate.author_name)) if candidate.author_name else ""
        rows.append(
            '<div class="catalog-row"><div class="catalog-name"><strong>{}</strong>{}</div><form action="/library/request/confirm/" method="get"><input type="hidden" name="token" value="{}"><button type="submit">Review request</button></form></div>'.format(
                escape(candidate.title), author, escape(token, quote=True)
            )
        )
    content = "".join(rows) or '<p class="empty">No suitable editions were found. Try another title, author, or ISBN.</p>'
    body = '<main class="request-page"><article class="request-desk"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="/library/">The Library of Bex</a> / <a href="/library/request/">Request a book</a> / <span aria-current="page">Search results</span></nav><p class="request-kicker">The librarian\'s desk</p><h1>Search results</h1><section class="catalog-list" aria-label="Request search results">{}</section></article></main>'.format(content)
    return page("Search results · The Library of Bex", body, body_class="request-page")


def request_confirmation(candidate, token):
    author = " by {}".format(escape(candidate.author_name)) if candidate.author_name else ""
    body = '<main class="request-page"><article class="request-desk"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="/library/">The Library of Bex</a> / <a href="/library/request/">Request a book</a> / <span aria-current="page">Confirm request</span></nav><p class="request-kicker">The librarian\'s desk</p><h1>Confirm request</h1><p class="request-intro">Ask Readarr to add <strong>{}</strong>{} to the library?</p><form class="request-form" action="/library/request/confirm/" method="post"><input type="hidden" name="token" value="{}"><button type="submit">Confirm request</button></form></article></main>'.format(
        escape(candidate.title), author, escape(token, quote=True)
    )
    return page("Confirm request · The Library of Bex", body, body_class="request-page")


def request_success(candidate):
    body = '<main class="request-page"><article class="request-desk"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="/library/">The Library of Bex</a> / <a href="/library/request/">Request a book</a> / <span aria-current="page">Request received</span></nav><p class="request-kicker">The librarian\'s desk</p><h1>Request received</h1><p class="request-message" role="status">Readarr accepted your request.</p><p class="request-intro"><strong>{}</strong> has been passed to the librarian.</p></article></main>'.format(escape(candidate.title))
    return page("Request received · The Library of Bex", body, body_class="request-page")


def request_error(title, message):
    body = '<main class="request-page"><article class="request-desk"><nav class="breadcrumb" aria-label="Breadcrumb"><a href="/library/">The Library of Bex</a> / <a href="/library/request/">Request a book</a> / <span aria-current="page">Request desk</span></nav><p class="request-kicker">The librarian\'s desk</p><h1>{}</h1><p class="request-message" role="alert">{}</p><p><a class="download" href="/library/request/">Return to the request desk</a></p></article></main>'.format(
        escape(title), escape(message)
    )
    return page("{} · The Library of Bex".format(title), body, body_class="request-page")


def catalog(title, root_url, entries, *, theme="books", breadcrumbs=None):
    count = len(entries)
    noun = "item" if count == 1 else "items"
    rows = []
    for entry in entries:
        name = escape(entry["name"])
        href = escape(entry["href"], quote=True)
        if entry["is_dir"]:
            label = "Open"
        else:
            label = "Download"
        rows.append(
            '<div class="catalog-row"><a class="catalog-name" href="{}">{}</a><span class="catalog-meta">{} · {}</span><a class="download" href="{}">{}</a></div>'.format(
                href, name, escape(entry["size"]), escape(entry["modified"]), href, label
            )
        )
    content = "".join(rows) or '<p class="empty">Awaiting new stock</p>'
    audio_theme = theme == "audio"
    body_class = "catalog-page audio-catalog" if audio_theme else "catalog-page"
    heading_detail = '<span class="audio-detail" aria-hidden="true">♫</span><span class="bookmark-detail" aria-hidden="true"></span>' if audio_theme else ""
    if breadcrumbs is None:
        breadcrumbs = [("The Library of Bex", "/library/"), (title, None)]
    breadcrumb_html = " / ".join(
        '<a href="{}">{}</a>'.format(escape(href, quote=True), escape(label))
        if href
        else '<span aria-current="page">{}</span>'.format(escape(label))
        for label, href in breadcrumbs
    )
    body = '<main class="{}"><article class="catalog"><nav class="breadcrumb" aria-label="Breadcrumb">{}</nav><header class="catalog-header"><h1>{}{}</h1><p class="count">{} {}</p></header><section class="catalog-list" aria-label="{} catalog">{}</section></article></main>'.format(
        body_class, breadcrumb_html, escape(title), heading_detail, count, noun, escape(title), content
    )
    return page("{} · The Library of Bex".format(title), body, body_class=body_class)
