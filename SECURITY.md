# Reporting security issues

For an exploitable issue, use this repository's **Security > Report a vulnerability** private reporting option. Include the game/mod versions, whether the host runs Java, a minimal reproduction and the affected authority boundary. Do not include account tokens or private saves.

Ordinary gameplay bugs belong in Issues. Review focuses on the current beta and active development branches; fixes are not guaranteed for older payloads.

The developer-only Lua endpoint executes code in a disposable local test session. Keep it on loopback, never enable the developer mod on a public server, and never expose its port through a firewall or tunnel.
