# hwpdf

Two PDF utilities packaged as an installable Flask blueprint:

- **PDF Booklet Maker** — imposes an A4 document four-up onto A4 sheets so that
  each group of eight pages forms a signature, returned as a zip of the odd and
  even sides for duplex printing.
- **PDF Page Splitter** — explodes a PDF into one file per page, returned as a
  zip.

Extracted from [holdenweb.com](https://holdenweb.com) with its history intact.
It is the first app built to the site-platform contract described below.

## Install

```bash
uv add hwpdf
```

## Use

```python
from flask import Flask
from hwpdf import pdf_blueprint

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

The blueprint is relocatable — mount it at `/tools/pdf` or anywhere else and its
internal links follow, because they are generated with `url_for`.

## The app contract

This package is deliberately a plain Flask blueprint plus one line of packaging
metadata. It invents no framework of its own.

### Discovery

```toml
[project.entry-points."holdenweb.apps"]
pdf = "hwpdf:pdf_blueprint"
```

A host site enumerates its installed apps rather than hard-coding imports:

```python
from importlib.metadata import entry_points

for entry_point in entry_points(group="holdenweb.apps"):
    app.register_blueprint(entry_point.load(), url_prefix=f"/{entry_point.name}/")
```

The entry point resolves to the **blueprint itself**, not to a bespoke
`register()` callable, so the contract is expressed in Flask's own vocabulary.
Where an app is mounted is the site's decision, as it is in Django.

### Setup hooks

Anything an app needs done at registration time goes through Flask's own
deferred-registration hook, which is the equivalent of Django's
`AppConfig.ready`:

```python
pdf_blueprint.record_once(
    lambda state: state.app.config.setdefault("PDF_MAX_PAGES", 64)
)
```

### Templates, and overriding them

All templates ship namespaced under `templates/hwpdf/`, so nothing can collide
with a host site's own template names.

A site overrides any of them — including the whole page layout — by placing a
file at the same path in its own template folder. Flask searches the
application's templates before any blueprint's, so no configuration is
involved. To wrap these pages in the site's furniture, that is a one-line file:

```jinja
{# templates/hwpdf/base.html in the host site #}
{% extends "site-base.html" %}
```

The layout shipped here is a minimal fallback used only when the site supplies
nothing. It loads Bootstrap from a CDN, because the form templates use Bootstrap
classes, and defines `title`, `content` and `scripts` blocks.

## Development

```bash
uv sync
uv run pytest
```

The test suite registers the blueprint on a **bare** `Flask` app with no
holdenweb configuration, pushes real reportlab-generated PDFs through both
tools, and asserts that mounting at a non-default prefix and overriding the
layout both work. If it passes, the package is genuinely self-contained.
