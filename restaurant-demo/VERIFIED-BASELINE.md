# Verified restaurant-demo v0.1 baseline

Verified: 2026-10-24 against user-provided `restaurant-demo-v0.1.zip` (5,649 bytes).

Archive SHA-256: `9b26285d5c17371e9469046eccc577ed971c46a62b724581b75cb808faa7b087`

Archive entries:

- `restaurant-demo/` directory
- `restaurant-demo/index.html`: 8,819 bytes
- `restaurant-demo/README.md`: 2,811 bytes

ZIP CRC/integrity test: passed (`testzip() == None`).

## Verified implementation

- Static single-file HTML/CSS/JavaScript site configurator.
- Six editable fields: name, cuisine/tagline, description, phone, address, hours.
- Three visual themes: rustic, modern, midnight.
- Live preview via textContent, generated `tel:` and Google Maps search links.
- Export-only JSON settings payload with `version: 1`, selected theme, and entered fields.
- No localStorage persistence, no JSON import, no publishing endpoint, no external scripts, no backend or Docker requirement.
- Responsive layout, basic mobile stacking.
- Built-in `noindex` robots meta tag. Private access requires server-side configuration.

## Security/deployment notes

- Untrusted field content is assigned with `textContent` rather than HTML injection.
- No backend attack surface in the original prototype.
- Secure private deployment should preserve existing Caddy site blocks, add a distinct hostname, use HTTPS + Basic Auth + response security headers, and verify unauthorized 401/authorized 200.
- Do not conflate the marketing/sales editor with an automatically published restaurant site.
- Do not extract into `/srv` or modify VPS configuration until original source is committed and reviewed.

## Source control status

This document verifies **inspected source**, but does not itself import `index.html` and `README.md` from the ZIP into Git. Preserve the archive exactly; import the unmodified files before any feature development and record their hashes. Original files should be committed at `restaurant-demo/index.html` and `restaurant-demo/README.md`.
