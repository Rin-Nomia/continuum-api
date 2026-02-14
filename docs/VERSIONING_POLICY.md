# Continuum Versioning Policy

## 1. Version format

Use semantic style:

`MAJOR.MINOR.PATCH`

- **MAJOR**: breaking API contract change
- **MINOR**: backward-compatible feature addition
- **PATCH**: backward-compatible fix

`APP_VERSION` in runtime must reflect deployed artifact version.

## 2. Contract change rules

Any change to `/api/v1/analyze` response requires:

1. Update `AnalyzeResponse` schema in `app.py`
2. Update `README.md` response example
3. Update `test_deployment.py`
4. Add entry in `CHANGELOG.md`

## 3. Evidence Schema governance

Evidence schema is versioned separately (currently `1.0`).

- Additive field changes: allowed under minor release
- Required field removal or rename: requires major release
- Schema validator must remain backward compatible during migration window

## 4. Release gate checklist

Before release:

- `decision_state` values strictly in `ALLOW|GUIDE|BLOCK`
- no raw input text in logs
- ops metrics endpoint healthy
- stability tests pass
- changelog updated

