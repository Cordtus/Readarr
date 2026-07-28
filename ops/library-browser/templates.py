from html import escape


PAGE_STYLE = """
:root { color-scheme: light; --ink: #2b211b; --paper: #f3e6c7; --paper-deep: #dfc99e; --walnut: #4a291d; --brass: #c29446; --copper: #b36a42; }
* { box-sizing: border-box; }
body { margin: 0; color: var(--ink); background: #221813; font-family: Georgia, 'Times New Roman', serif; }
a { color: inherit; }
a:focus-visible { outline: 3px solid #f8d27c; outline-offset: 4px; border-radius: 2px; }
.landing { min-height: 100vh; display: grid; place-items: center; padding: clamp(1.25rem, 4vw, 4rem); background: linear-gradient(90deg, rgba(27,13,9,.72), rgba(27,13,9,.12) 55%, rgba(27,13,9,.65)), url('/library/assets/reading-room.webp') center/cover; }
.plaque { justify-self: start; padding: 1.1rem 1.4rem 1.25rem; color: #f8e7bd; background: rgba(52, 27, 18, .88); border: 1px solid var(--brass); box-shadow: 0 0 0 5px rgba(38, 19, 12, .45), 0 1rem 3rem rgba(0,0,0,.35); }
.plaque-kicker { margin: 0 0 .3rem; color: #e4b967; font: .7rem/1.2 Arial, sans-serif; letter-spacing: .18em; text-transform: uppercase; }
.plaque h1 { margin: 0; font-size: clamp(1.8rem, 4vw, 3.3rem); line-height: .95; font-weight: 500; }
.archives-notice { margin: .2rem 0 0; padding: .9rem 1.1rem; color: rgba(248, 231, 189, .72); background: rgba(36, 19, 13, .58); border-left: 2px solid rgba(194, 148, 70, .62); font: .82rem/1.45 Arial, sans-serif; }
.archives-notice strong { display: block; color: #e4b967; font-size: .7rem; letter-spacing: .14em; text-transform: uppercase; }
.archives-notice p { margin: .3rem 0 0; }
.catalog-page { min-height: 100vh; padding: clamp(1.25rem, 4vw, 4rem); background: radial-gradient(circle at 20% 0, rgba(255,255,255,.55), transparent 35rem), var(--paper); }
.request-desk { width: min(100%, 42rem); margin: 0 auto; padding: clamp(1.4rem, 5vw, 3rem); background: rgba(255,250,235,.55); border: 1px solid rgba(74,41,29,.38); box-shadow: 0 .8rem 2.5rem rgba(50, 28, 16, .15); }
.request-intro { max-width: 35rem; margin: 1rem 0 1.7rem; color: #604938; line-height: 1.5; }
.request-form { display: grid; gap: .65rem; }
.request-form label { color: var(--walnut); font: .76rem Arial, sans-serif; font-weight: 700; letter-spacing: .08em; text-transform: uppercase; }
.request-form input { width: 100%; min-height: 44px; padding: .8rem .9rem; color: var(--ink); background: #fffaf0; border: 1px solid rgba(74,41,29,.55); border-radius: 0; font: 16px Georgia, 'Times New Roman', serif; }
.request-form input:focus { outline: 3px solid rgba(194,148,70,.55); outline-offset: 2px; }
.request-form button, .bookcase form button { min-width: 44px; min-height: 44px; justify-self: start; padding: .75rem 1rem; color: #f8e7bd; background: var(--walnut); border: 1px solid var(--brass); border-radius: 0; font: 700 16px/1.2 Arial, sans-serif; letter-spacing: .08em; text-transform: uppercase; cursor: pointer; touch-action: manipulation; }
.bookcase form button:active { background: #603625; transform: scale(.985); }
.request-message { margin: 0 0 1.2rem; padding: .75rem .9rem; color: #5e412c; background: rgba(194,148,70,.14); border-left: 3px solid var(--copper); }
.audio-catalog { --catalog-accent: var(--copper); --paper: #f0ddc2; }
.catalog { width: min(100%, 62rem); margin: 0 auto; }
.breadcrumb { margin-bottom: 2rem; color: #765d47; font: .82rem Arial, sans-serif; }
.breadcrumb a { min-width: 44px; min-height: 44px; display: inline-flex; align-items: center; text-underline-offset: .2em; }
.catalog-header { display: flex; justify-content: space-between; gap: 1rem; align-items: end; border-bottom: 3px double var(--walnut); padding-bottom: 1rem; }
.catalog-header h1 { margin: 0; font-size: clamp(2.2rem, 6vw, 4.4rem); font-weight: 500; line-height: .9; }
.audio-catalog .catalog-header { border-color: var(--catalog-accent); }
.audio-catalog .download { color: var(--catalog-accent); }
.audio-detail, .bookmark-detail { display: inline-block; margin-left: .4em; color: var(--catalog-accent); font: .45em Arial, sans-serif; vertical-align: .35em; }
.bookmark-detail { display: inline-block; width: .65em; height: 1em; margin-left: .15em; background: var(--catalog-accent); clip-path: polygon(0 0, 100% 0, 100% 100%, 50% 72%, 0 100%); }
.count { margin: 0; color: #765d47; font: .78rem Arial, sans-serif; white-space: nowrap; }
.catalog-list { margin-top: 1.2rem; border-top: 1px solid rgba(74,41,29,.35); }
.catalog-row { display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 1.5rem; align-items: center; padding: 1rem .4rem; border-bottom: 1px solid rgba(74,41,29,.25); }
.catalog-name { min-width: 44px; min-height: 44px; display: flex; align-items: center; overflow-wrap: anywhere; font-size: 1.1rem; }
.catalog-meta { color: #765d47; font: .78rem Arial, sans-serif; white-space: nowrap; }
.download { min-width: 44px; min-height: 44px; display: inline-flex; align-items: center; justify-content: flex-end; color: var(--walnut); font: .78rem Arial, sans-serif; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; text-underline-offset: .2em; }
.empty { margin-top: 2rem; padding: 3rem 1rem; color: #765d47; border: 1px dashed rgba(74,41,29,.5); text-align: center; font-style: italic; font-size: 1.2rem; }
@media (max-width: 650px) { .plaque { justify-self: stretch; } .catalog-header { display: block; } .count { margin-top: .8rem; } .catalog-row { grid-template-columns: minmax(0, 1fr) auto; gap: .45rem 1rem; } .catalog-meta { grid-column: 1; } .download { grid-column: 2; grid-row: 1 / span 2; } }
@media (prefers-reduced-motion: reduce) { *, *::before, *::after { scroll-behavior: auto !important; transition-duration: .01ms !important; animation-duration: .01ms !important; } }

/* The bookcase is the navigation: one piece of furniture, not a card grid. */
.landing {
  min-height: 100svh;
  min-height: 100dvh;
  place-items: center start;
  padding: max(1rem, env(safe-area-inset-top)) max(1rem, env(safe-area-inset-right)) max(1rem, env(safe-area-inset-bottom)) max(1rem, env(safe-area-inset-left));
  background-position: center;
}
.landing-card.bookcase {
  width: min(27rem, 100%);
  min-height: min(48rem, calc(100dvh - 2rem));
  display: flex;
  flex-direction: column;
  gap: 0;
  align-items: stretch;
  overflow: clip;
  border: 1px solid rgba(227, 181, 94, .58);
  border-radius: 2px;
  background:
    linear-gradient(90deg, rgba(255,255,255,.035), transparent 12%, transparent 88%, rgba(0,0,0,.18)),
    repeating-linear-gradient(2deg, #3d2118 0, #3d2118 8px, #43251a 9px, #382016 13px);
  box-shadow:
    inset 0 0 0 7px rgba(21, 10, 7, .45),
    inset 0 0 3rem rgba(8, 3, 2, .45),
    0 1.5rem 4rem rgba(0,0,0,.45);
}
.bookcase .plaque {
  justify-self: auto;
  margin: 1.25rem 1.25rem .8rem;
  padding: 1rem 1.15rem 1.1rem;
  text-align: center;
  box-shadow: inset 0 0 0 3px rgba(38,19,12,.5), 0 .7rem 1.4rem rgba(0,0,0,.26);
}
.bookcase .plaque h1 { font-size: clamp(2rem, 7vw, 3.25rem); line-height: .92; }
.bookcase .shelves { display: block; }
.shelf {
  margin: 0 1.15rem .8rem;
  border: 1px solid rgba(235,190,105,.42);
  background: rgba(20, 9, 6, .42);
  box-shadow: inset 0 -8px 0 rgba(13,6,4,.38), 0 .65rem 1rem rgba(0,0,0,.2);
}
.shelf-trigger {
  width: 100%;
  min-height: 4.25rem;
  display: none;
  padding: .85rem 1rem;
  color: #f8e7bd;
  text-align: left;
  border: 0;
  border-bottom: 1px solid rgba(235,190,105,.24);
  border-radius: 0;
  background: linear-gradient(180deg, rgba(111,64,42,.94), rgba(60,32,23,.96));
  box-shadow: inset 0 1px rgba(255,255,255,.08), inset 0 -5px rgba(14,7,5,.25);
  font-size: 16px;
  cursor: pointer;
  touch-action: manipulation;
  transition: filter 180ms cubic-bezier(.16,1,.3,1), transform 180ms cubic-bezier(.16,1,.3,1);
}
.js .shelf-trigger { display: block; }
.shelf-trigger strong { display: block; font: 500 1.2rem/1.1 Georgia, 'Times New Roman', serif; }
.shelf-trigger span { display: block; margin-top: .28rem; color: #e6c98e; font: .76rem/1.35 Arial, sans-serif; letter-spacing: .02em; }
.shelf-trigger[aria-expanded="true"] { filter: brightness(1.12); }
.shelf-trigger:active { transform: scale(.985); }
.shelf-trigger:focus-visible,
.open-shelf:focus-visible,
.bookcase form button:focus-visible { outline: 3px solid #f8d27c; outline-offset: 3px; }
.shelf-panel {
  padding: 1rem;
  color: #f7e8c7;
  background: rgba(19,9,6,.68);
  font: .9rem/1.45 Arial, sans-serif;
}
.shelf-panel ul { margin: 0 0 .85rem; padding: 0; list-style: none; }
.shelf-panel li { padding: .25rem 0; overflow-wrap: anywhere; }
.shelf-panel li + li { border-top: 1px solid rgba(231,198,135,.18); }
.shelf-count { margin: 0 0 .6rem; color: #dfbc75; font-size: .75rem; }
.shelf-empty { margin: 0 0 .8rem; color: #dec99e; font-style: italic; }
.open-shelf {
  min-height: 44px;
  display: inline-flex;
  align-items: center;
  color: #f8d27c;
  font-weight: 700;
  text-underline-offset: .22em;
}
.bookcase .request-desk { width: 100%; margin: 0; padding: 0; color: #f7e8c7; background: transparent; border: 0; box-shadow: none; }
.bookcase .request-desk h2 { margin: 0 0 .65rem; color: #f8e7bd; font: 500 1.55rem/1.05 Georgia, 'Times New Roman', serif; }
.bookcase .request-intro { margin: 0 0 1rem; color: #dec99e; }
.bookcase .request-form input { min-height: 48px; font-size: 16px; }
.bookcase .request-form button { min-height: 44px; max-width: 100%; white-space: nowrap; }
.bookcase .catalog-list { margin-top: .75rem; border: 0; }
.bookcase .catalog-row { grid-template-columns: minmax(0,1fr); gap: .65rem; padding: .85rem 0; border-bottom-color: rgba(231,198,135,.2); }
.bookcase .catalog-name { color: #f7e8c7; }
.bookcase .request-message { color: #f7e8c7; background: rgba(194,148,70,.14); }
.bookcase .empty { margin: .5rem 0; padding: 1rem; color: #dec99e; border-color: rgba(231,198,135,.4); }
.bookcase .archives-notice { margin: auto 1.25rem 1.25rem; padding: .8rem 0 0; background: transparent; border: 0; border-top: 1px solid rgba(194,148,70,.36); text-align: center; }
.js .shelf-panel { animation: shelf-enter 260ms cubic-bezier(.16,1,.3,1) both; }
@keyframes shelf-enter { from { opacity: 0; transform: translateY(7px); } to { opacity: 1; transform: translateY(0); } }
@media (hover: hover) and (pointer: fine) {
  .shelf-trigger:hover { filter: brightness(1.14); }
  .bookcase form button:hover { background: #603625; }
}
@media (max-width: 759px) {
  .landing {
    min-height: 100svh;
    display: flex;
    align-items: flex-end;
    padding: min(28svh, 12rem) 0 0;
    background-position: 58% center;
  }
  .landing-card.bookcase {
    width: 100%;
    min-height: 0;
    border-right: 0;
    border-bottom: 0;
    border-left: 0;
    padding-right: max(0px, env(safe-area-inset-right));
    padding-bottom: max(1rem, env(safe-area-inset-bottom));
    padding-left: max(0px, env(safe-area-inset-left));
    box-shadow: inset 0 0 0 6px rgba(21,10,7,.42), 0 -1rem 3rem rgba(0,0,0,.42);
  }
  .bookcase .plaque { margin-top: 1rem; }
  .shelf { margin-right: 1rem; margin-left: 1rem; }
}
@media (max-width: 319px) {
  .bookcase .plaque,
  .shelf,
  .bookcase .archives-notice { margin-right: .5rem; margin-left: .5rem; }
  .shelf-panel { padding: .75rem; }
  .bookcase .request-form button {
    width: 100%;
    padding-right: .45rem;
    padding-left: .45rem;
    white-space: normal;
  }
}
@media (prefers-reduced-motion: reduce) {
  .js .shelf-panel { animation: none; }
  .shelf-trigger { transition: none; }
}
@media (prefers-reduced-transparency: reduce) {
  .landing-card.bookcase, .shelf-panel { background-color: #342018; }
}
@media (prefers-contrast: more) {
  .shelf, .landing-card.bookcase, .shelf-trigger { border-color: #f8d27c; }
  .shelf-trigger span, .shelf-panel, .bookcase .request-intro { color: #fff0cc; }
}
"""

BOOKCASE_SCRIPT = """
<script>
(() => {
  const root = document.documentElement;
  const triggers = [...document.querySelectorAll('.shelf-trigger')];
  if (!triggers.length) return;
  root.classList.add('js');
  let pinned = triggers.find((trigger) => trigger.getAttribute('aria-expanded') === 'true') || triggers[0];
  const panelFor = (trigger) => document.getElementById(trigger.getAttribute('aria-controls'));
  const showOnly = (active) => {
    triggers.forEach((trigger) => {
      const selected = trigger === active;
      trigger.setAttribute('aria-expanded', String(selected));
      panelFor(trigger).hidden = !selected;
    });
  };
  showOnly(pinned);
  triggers.forEach((trigger) => {
    trigger.addEventListener('click', () => {
      pinned = trigger;
      showOnly(pinned);
    });
  });
})();
</script>
"""


def page(title, body, *, body_class=""):
    return "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1, viewport-fit=cover'><title>{}</title><style>{}</style></head><body class='{}'>{}{}</body></html>".format(
        escape(title), PAGE_STYLE, body_class, body, BOOKCASE_SCRIPT
    )


SHELVES = (
    ("books", "Books", "Open the shelves and see what is ready to read."),
    ("audiobooks", "Audiobooks", "Settle in with something worth hearing."),
    ("request", "Request a book", "Search by title, author, or ISBN without leaving the room."),
)


def preview_panel(preview):
    entries = "".join(
        "<li>{}</li>".format(escape(entry["name"]))
        for entry in preview["entries"]
    )
    if preview.get("error"):
        contents = '<p class="shelf-empty" role="alert">{}</p>'.format(
            escape(preview["error"])
        )
    elif entries:
        contents = "<ul>{}</ul>".format(entries)
    else:
        contents = '<p class="shelf-empty">{}</p>'.format(
            "No recordings catalogued yet."
            if preview["id"] == "audiobooks"
            else "No volumes catalogued yet."
        )
    return '<p class="shelf-count">{} {}</p>{}<a class="open-shelf" href="{}">Open shelf</a>'.format(
        preview["count"],
        "item" if preview["count"] == 1 else "items",
        contents,
        escape(preview["href"], quote=True),
    )


def library_shell(previews, *, active_shelf="books", request_content="", title="The Library of Bex"):
    preview_by_id = {preview["id"]: preview for preview in previews or ()}
    shelves = []
    for shelf_id, label, description in SHELVES:
        expanded = shelf_id == active_shelf
        if shelf_id == "request":
            panel_content = request_content or request_form()
        else:
            preview = preview_by_id.get(shelf_id, {
                "id": shelf_id,
                "href": "/library/{}/".format(label),
                "count": 0,
                "entries": (),
            })
            panel_content = preview_panel(preview)
        shelves.append(
            '<section class="shelf" data-shelf="{}">'
            '<button class="shelf-trigger" type="button" id="shelf-{}-trigger" '
            'aria-label="{}" aria-expanded="{}" aria-controls="shelf-{}-panel">'
            '<strong>{}</strong><span>{}</span></button>'
            '<div class="shelf-panel" id="shelf-{}-panel" role="region" '
            'aria-labelledby="shelf-{}-trigger">{}</div></section>'.format(
                shelf_id,
                shelf_id,
                escape(label, quote=True),
                str(expanded).lower(),
                shelf_id,
                escape(label),
                escape(description),
                shelf_id,
                shelf_id,
                panel_content,
            )
        )
    body = (
        '<main class="landing"><div class="landing-card bookcase">'
        '<header class="plaque"><p class="plaque-kicker">A private collection</p>'
        '<h1 id="library-title">The Library<br>of Bex</h1></header>'
        '<nav class="shelves" aria-label="Library shelves">{}</nav>{}</div></main>'
    ).format("".join(shelves), archives_notice())
    return page(title, body, body_class="landing-page")


def landing(previews=None):
    return library_shell(previews or (), active_shelf="books")


def archives_notice():
    return '<aside class="archives-notice"><strong>The archives</strong><p>The archives are not yet open to the public</p></aside>'


def request_form(message=None):
    message_html = '<p class="request-message" role="status">{}</p>'.format(escape(message)) if message else ""
    return """<div class="request-desk"><h2>Request a book</h2><p class="request-intro">Tell the librarian what you would like to read, and the catalogue will be searched for a suitable edition.</p>{}<form class="request-form" action="/library/request/search/" method="get"><label for="request-query">Title, author, or ISBN</label><input id="request-query" name="term" type="search" enterkeyhint="search" autocomplete="off" required><button type="submit">Search the catalogue</button></form></div>""".format(message_html)


def request_desk(message=None, previews=None):
    return library_shell(
        previews or (),
        active_shelf="request",
        request_content=request_form(message),
        title="Request a book - The Library of Bex",
    )


def request_results(results, previews=None):
    rows = []
    for token, candidate in results:
        author = " by {}".format(escape(candidate.author_name)) if candidate.author_name else ""
        action = (
            '<p class="request-message" role="status">Already in the library</p>'
            if candidate.is_existing
            else '<form action="/library/request/confirm/" method="get"><input type="hidden" name="token" value="{}"><button type="submit">Review request</button></form>'.format(
                escape(token, quote=True)
            )
        )
        rows.append(
            '<div class="catalog-row"><div class="catalog-name"><strong>{}</strong>{}</div>{}</div>'.format(
                escape(candidate.title), author, action
            )
        )
    content = "".join(rows) or '<p class="empty">No suitable editions were found. Try another title, author, or ISBN.</p>'
    request_content = '<div class="request-desk"><h2 tabindex="-1" autofocus>Search results</h2><section class="catalog-list" aria-label="Request search results">{}</section></div>'.format(content)
    return library_shell(previews or (), active_shelf="request", request_content=request_content, title="Search results - The Library of Bex")


def request_confirmation(candidate, token, previews=None):
    author = " by {}".format(escape(candidate.author_name)) if candidate.author_name else ""
    request_content = '<div class="request-desk"><h2 tabindex="-1" autofocus>Confirm request</h2><p class="request-intro">Ask Readarr to add <strong>{}</strong>{} to the library?</p><form class="request-form" action="/library/request/confirm/" method="post"><input type="hidden" name="token" value="{}"><button type="submit">Confirm request</button></form></div>'.format(
        escape(candidate.title), author, escape(token, quote=True)
    )
    return library_shell(previews or (), active_shelf="request", request_content=request_content, title="Confirm request - The Library of Bex")


def request_success(candidate, previews=None):
    request_content = '<div class="request-desk"><h2 tabindex="-1" autofocus>Request received</h2><p class="request-message" role="status">Readarr accepted your request.</p><p class="request-intro"><strong>{}</strong> has been passed to the librarian.</p></div>'.format(escape(candidate.title))
    return library_shell(previews or (), active_shelf="request", request_content=request_content, title="Request received - The Library of Bex")


def request_error(title, message, previews=None):
    request_content = '<div class="request-desk"><h2 tabindex="-1" autofocus>{}</h2><p class="request-message" role="alert">{}</p><p><a class="open-shelf" href="/library/request/">Return to the request desk</a></p></div>'.format(
        escape(title), escape(message)
    )
    return library_shell(previews or (), active_shelf="request", request_content=request_content, title="{} - The Library of Bex".format(title))


def catalog(title, entries, *, theme="books", breadcrumbs=None):
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
