# Real Vehicle Interiors contributor guidance

Read README.md, docs/DEVELOPMENT.md and docs/COMPATIBILITY.md before changes. Production source lives in `mod/` and `src/`; developer tools live in `dev/`, `scripts/` and `tools-src/`.

- Keep game installs, Steam Workshop downloads, saves and launcher load orders unchanged unless explicitly authorized. Deployment is a separate step; the default build writes only under `build/`.
- Preserve save-facing `MELens`/`me.lens.rv` identifiers. Project and developer folders use Real Vehicle Interiors naming. Prefer shared profiles/contracts and repeatable generators.
- Animals support belongs on `codex/animals-support` until fully implemented and tested. Do not merge it into the release branch as part of unrelated work.
- Exclude game/dependency binaries, keys, credentials, personal logs and saves from commits. Shader reconstruction must use a local game install and match its pinned hashes.
- On the maintainer's shared Windows machine, launch every test, build, lint, typecheck, capture, Blender task and native harness with `node C:/Users/erika/.codex/tools/run-heavy.mjs -- <program> <args>`. A full child tree is limited to 16 GiB; admission requires 8 GiB/25% free RAM and 8 GiB free commit. Exit 75 is deferred/unverified; do not retry immediately or bypass/increase limits. Stop only task-owned processes and keep test servers/clients in the guarded lifetime.
- Prefer isolated native harnesses; do not take over the user's desktop. Prove actual UI inputs for interactive changes and distinguish automated, native, visual, multiplayer, persistence, performance and owner acceptance.
- Use ImageGen for authored artwork changes. Inspect existing art first, preserve masters/prompts, export suitable POT derivatives, compress derivatives through TinyPNG and inspect at native display size. Report unavailable compression explicitly.
- Stage only related paths and leave unrelated dirty work intact.
