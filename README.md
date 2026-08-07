# pp-pdf

Two PDF utilities packaged as an installable Flask app:

- **PDF Booklet Maker** — imposes an A4 document four-up onto A4 sheets so that
  each group of eight pages forms a signature, returned as a zip of the odd and
  even sides for duplex printing.
- **PDF Page Splitter** — explodes a PDF into one file per page, returned as a
  zip.

Extracted from [holdenweb.com](https://holdenweb.com) with its history intact. It
answers to two contracts and requires neither: a plain Flask blueprint, and a
[podpack](https://github.com/holdenweb/podpack) app.

## Install

```bash
uv add pp-pdf
```

The distribution is `pp-pdf`; the module, and the app's name everywhere podpack
needs one, is `pp_pdf`.

---

## As a plain Flask blueprint

```python
from flask import Flask
from pp_pdf import pdf_blueprint

app = Flask(__name__)
app.config["SECRET_KEY"] = "..."          # required: the forms are CSRF-protected
app.register_blueprint(pdf_blueprint, url_prefix="/pdf/")
```

That yields three endpoints under the prefix you chose:

| Route | Purpose |
| --- | --- |
| `/` | Index listing both tools |
| `/booklet` | Upload a PDF, receive a zip of imposed odd/even sides |
| `/pagezip` | Upload a PDF, receive a zip of one file per page |

Here the mount point is yours: the blueprint is relocatable, so mount it at
`/tools/pdf` or anywhere else and its internal links follow, because they are
generated with `url_for`.

### Discovery

```toml
[project.entry-points."holdenweb.apps"]
pdf = "pp_pdf:pdf_blueprint"
```

A host site can enumerate its installed apps rather than hard-coding imports:

```python
from importlib.metadata import entry_points

for entry_point in entry_points(group="holdenweb.apps"):
    app.register_blueprint(entry_point.load(), url_prefix=f"/{entry_point.name}/")
```

The entry point resolves to the **blueprint itself**, not to a bespoke
`register()` callable, so the contract is expressed in Flask's own vocabulary.
The entry-point *name* is only a mount hint for that loop; it is not the app's
name.

### Setup hooks

Anything needed at registration time goes through Flask's own deferred-
registration hook, which is the equivalent of Django's `AppConfig.ready`. This
package uses it on itself, to settle its two config keys:

```python
@pdf_blueprint.record_once
def _defaults(state):
    state.app.config.setdefault("PP_PDF_BASE_TEMPLATE", STANDALONE_LAYOUT)
    state.app.config.setdefault("PP_PDF_MAX_PAGES", DEFAULT_MAX_PAGES)
```

---

## As a podpack app

Add the package's **import name** to the site's config file and restart:

```toml
[site]
apps = ["pp_pdf"]

[apps.pp_pdf]
max_pages = 200
```

There is no second step. podpack imports the package, reads its module-level
`site_app`, and takes the mount point, the nav entry and the config namespace
from it:

```python
site_app = SiteApp(
    name="pp_pdf",
    blueprint=pdf_blueprint,
    url_prefix="/pdf",
    nav=(Section("PDF tools", "pp_pdf.root_page"),),
    init=_init,
)
```

`url_prefix` is what this app asks for, not what it is entitled to. A site that
wants these pages somewhere else in its address space says so, and the nav entry
follows without either side restating it — a `Section` names an endpoint, so
podpack resolves it with `url_for` as the chrome renders:

```toml
[apps.pp_pdf]
url_prefix = "/tools/pdf"
```

So the mount point is the host's under either contract; only the way of saying
so differs — an argument to `register_blueprint` there, a line of config here.

`name` must equal the blueprint's own name, because podpack resolves an app's
data directory and config namespace from `request.blueprint`. Nothing checks that
they agree; if they diverge, `app_config()` returns `{}` and the data directory
silently does not exist. There is a test for it.

podpack is an **optional** import here — it is on no package index, and this
package's first contract is to need no framework at all. Where it is absent,
`pp_pdf.site_app` is `None` and everything else works unchanged.

---

## How one package serves both

|  | Plain Flask | podpack |
| --- | --- | --- |
| Discovery | `holdenweb.apps` entry point, or a direct import | import name in the site's `apps` list |
| What is discovered | the `Blueprint` | `site_app: SiteApp` |
| Mount point | the host's argument to `register_blueprint` | `[apps.pp_pdf] url_prefix`, defaulting to the app's own |
| Setup hook | `pdf_blueprint.record_once` | `SiteApp.init` |
| Page layout | `pp_pdf/standalone.html`, shipped here | the site's `base.html` |
| Configuration | `app.config["PP_PDF_…"]` | `[apps.pp_pdf]` in the site's TOML |
| Navigation | the host's business | `nav=(Section(…),)` |

The two coexist because the podpack half is a **config translator, not a second
code path**. Both hosts settle the same two keys before the first request, and
the views, forms and templates read only those.

### Templates, and the layout ladder

All templates ship namespaced under `templates/pp_pdf/`, so nothing can collide
with a host site's own template names. Every page extends `pp_pdf/base.html`,
which is one line: it extends whatever the host has said should wrap it.

```
a site's own templates/pp_pdf/base.html   shadows this package's entirely
podpack                                   "base.html" -- the site's chrome
plain Flask                               pp_pdf/standalone.html, shipped here
```

A host of either kind overrides any template here — including the whole page
layout — by placing a file at the same path in its own template folder. Flask
searches the application's templates before any blueprint's, so no configuration
is involved. To wrap these pages in a plain-Flask site's furniture, that is a
one-line file:

```jinja
{# templates/pp_pdf/base.html in the host site #}
{% extends "site-base.html" %}
```

or a single config key, set before the blueprint is registered:

```python
app.config["PP_PDF_BASE_TEMPLATE"] = "site-base.html"
```

Standalone mode does **not** go looking for a `base.html` of its own accord. A
host opts in, by one of those two routes. Adopting an unrelated layout
automatically would reparent these pages onto blocks that may not match and
context this package cannot supply — and a Jinja block that no ancestor renders
is dropped in silence, so the failure would have no error message.

For the same reason this package ships no template called `base.html`: Flask
searches *every* blueprint's templates for a name the application does not
supply, so one here would become the site-wide base for a podpack site and
reparent every other installed app. A test pins that.

**Which blocks a child may fill:** `content` and `title`. Both known layouts
define them. `scripts` exists only in `standalone.html` and vanishes without
warning under podpack.

### A note on upload size

A podpack site's `[limits] max_upload_bytes` becomes Flask's
`MAX_CONTENT_LENGTH`. podpack's lab config sets it to 1 MiB, which will reject
most real PDFs with a 413 before this app ever sees them. Raise it there.

Separately, `max_pages` bounds the splitter: it builds its zip entirely in
memory, one member per page, so an unbounded document is a way to exhaust the
process rather than a document that cannot be read. Over the limit it declines
with a message instead of trying.

---

## Development

```bash
uv sync
uv run pytest
```

That runs the standalone suite: it registers the blueprint on a **bare** `Flask`
app with no framework of any kind, pushes real reportlab-generated PDFs through
both tools, and asserts that mounting at a non-default prefix, overriding the
layout, and refusing an oversized document all work. If it passes, the package
is genuinely self-contained.

The podpack conformance suite installs the app into a real podpack site and
checks the other contract. podpack is deliberately not a declared dependency —
every way of declaring it binds at *lock* time, which would make the framework
mandatory for anyone merely working on this package. So it goes into the venv
and not into the lock file:

```bash
uv pip install -e ../podpack
uv run pytest
```

`tests/test_podpack.py` skips itself when that has not been run.

To look at the pages without a host site of any kind:

```bash
uv run python devserver.py     # http://127.0.0.1:8459/pdf/
```
