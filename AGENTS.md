# Repository Guidelines

## Project Structure & Module Organization

This repository packages `cfdiclient`, a Python client for SAT CFDI web services.
Source code lives in `cfdiclient/`, with one module per service concern: authentication
(`autenticacion.py`), signing (`signer.py`, `fiel.py`), mass download flows
(`solicitadescarga*.py`, `verificasolicituddescarga.py`, `descargamasiva.py`), and
shared helpers (`utils.py`, `webservicerequest.py`). SOAP/XML templates are bundled
beside the modules as `cfdiclient/*.xml`; keep template edits synchronized with the
Python code that loads them. Tests are in `tests/`. Example usage is in
`README.md` and `ejemplo_completo.py`. Sample certificate files are under
`certificados/` and should not be replaced with real private credentials.

## Build, Test, and Development Commands

Create an isolated environment and install development dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Run the test suite:

```bash
pytest
```

Build distributable artifacts in `dist/`:

```bash
python -m build
```

Optionally lint with the included Pylint configuration:

```bash
pylint --rcfile=pylint.rc cfdiclient tests
```

## Coding Style & Naming Conventions

Follow `.editorconfig`: UTF-8, LF line endings, final newline, and 4-space
indentation for Python. Prefer clear snake_case for functions, variables, and module
names. Preserve the existing public API names and Spanish SAT domain terminology
(`Fiel`, `Autenticacion`, `SolicitaDescarga`, `rfc_solicitante`) unless a change is
explicitly intended to be breaking. Keep XML template filenames aligned with their
service modules.

## Testing Guidelines

Tests use `pytest`, with discovery configured for `tests/` in `pyproject.toml`.
Name test files `test_*.py` and test functions `test_*`. Add focused unit tests for
parsing, request construction, signature behavior, and error handling when changing
service modules. Avoid tests that require live SAT credentials or network access;
mock HTTP responses and use fixture data instead.

## Commit & Pull Request Guidelines

The project is configured for `python-semantic-release` with conventional commits.
Use tags such as `fix:`, `feat:`, `perf:`, `docs:`, `test:`, `refactor:`, `ci:`,
`build:`, `style:`, and `chore:`. `feat` creates minor releases; `fix` and `perf`
create patch releases. Pull requests should describe the behavioral change, mention
affected SAT service flows, link related issues, and include the commands run
(`pytest`, `python -m build`, linting when relevant). Do not include real RFC keys,
FIEL passwords, tokens, or downloaded CFDI data in commits, logs, or PR text.
