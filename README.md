# Hermes Gateway Control

Custom setup page buat Hermes Agent di Railway. Halaman kita jadi front publik
(login, setup custom provider, restart gateway), Hermes dashboard aslinya
tetap jalan tapi di-bind ke loopback dan diakses lewat reverse proxy `/dashboard`.

## Environment Variables

| Variable | Wajib | Keterangan |
|---|---|---|
| `DASHBOARD_USER` | tidak | default `admin` |
| `DASHBOARD_PASSWORD` | ya | password login page kita |
| `COOKIE_SECRET` | disarankan | signing key sesi, kalau kosong di-generate acak tiap boot (sesi hilang tiap redeploy) |

## Volume

Attach Railway volume ke `/data` — ini `HERMES_HOME`, isinya config.yaml, .env, sessions, memory.

## Alur

1. Deploy, isi `DASHBOARD_PASSWORD` dan `COOKIE_SECRET` (`openssl rand -base64 32`)
2. Buka domain Railway, login
3. Isi form Custom Provider (base URL, API key, model)
4. Klik Restart Gateway
5. Klik "Buka Hermes Dashboard" buat akses sessions/MCP/skills/logs penuh
