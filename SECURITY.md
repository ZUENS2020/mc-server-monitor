# Security

## Secrets

This repository **must not** contain:

- Crafty / RCON / frp / Cloudflare / proxy API keys or passwords
- Private host documentation with internal IPs, home network layout, or personal domains
- Real `.env` files (use `.env.example` only)

Runtime secrets are read from environment variables or mounted files (`CRAFTY_CREDS_FILE`, `server.properties`, etc.) on the deployment host.

## Exposure

The dashboard can read **server logs** and show **player locations**. Do not expose port `8765` to the public internet without authentication (Cloudflare Access, reverse-proxy basic auth, VPN, etc.).

## Reporting

If you find sensitive data committed to this repo, open a GitHub issue or contact the maintainer privately so history can be scrubbed.
