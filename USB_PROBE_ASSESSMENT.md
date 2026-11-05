# Proposed USB compatibility test — not yet approved or run

Prepared November 5, 2026 for the owner's onn W4K43M-1030, firmware 86.920.9.3-2 / software 86.920.9.3-2.12. The purpose is to determine whether a minimal USB-hosted CGI can execute on this firmware, not to install QuietFrame or change Home.

## Evidence behind the proposal

[Vizio Open Home](https://github.com/jordanmateo-byte/vizio-open-home) reports Home and normal power-on replacement on an M657-G0 / SX7B with firmware 7.0.120.1-1. Its owner confirmed operation after removing the USB and installation computer. That is meaningful evidence for that device, not compatibility with this onn model.

Its [root notes](https://github.com/jordanmateo-byte/vizio-open-home/blob/main/docs/ROOT.md) describe the TV's local HTTP server executing a shell CGI from the mounted USB as root. The underlying [ELTON advisory L9-44-477](https://www.eltoncyber.com/advisories/vizio-tv-code-execution-from-a-usb-drive) lists older E50x-E1 firmware and reports execution on a P65-F1. Neither establishes exposure on firmware 86.920.9.3-2.

The older project's [installation procedure](https://github.com/jordanmateo-byte/vizio-open-home/blob/main/docs/INSTALL.md) modifies the HTML Home entrypoint after backups and readback verification. Our TV reports a different active Home: namespace 4/app 1 with `bundles/home`. The existing namespace 2/app 1 `sctv` entry and `/scfs/sctv/main.html` are not proof that this older entrypoint controls modern Home. Even a successful root probe would not authorize or validate that installation method here.

## Exact proposed operations

No TV operations have been performed by these prepared files. No source from the third-party installer is executed. The owner's initial instruction requires a separate assessment and explicit approval before exploit-based testing; this document and the small local files make that approval concrete. Source preparation and local tests are complete. Device execution remains pending.

The test requires an existing FAT32 USB flash drive temporarily, plus the Mac for the one-shot launch. No drive is formatted or erased by these tools. Copy only the following two files to the USB root after approval:

- [quietframe-usb-marker.html](usb-probe/quietframe-usb-marker.html): a static page with no scripts or external assets.
- [quietframe-identity.cgi](usb-probe/quietframe-identity.cgi): a fixed shell script that prints markers, `id -u`, `uname -s`, and `uname -m`, then exits. It accepts no commands, parameters, uploads, or request body.

The proposed launcher, [launch-usb-check.py](scripts/launch-usb-check.py), sends one paired launch to the already tested namespace 4/app 17. It accepts only `--marker` or `--identity`, with fixed TV-loopback URLs. It does not select a privileged system-modal app, replace a system service, or alter the existing QuietFrame page.

## Risk and reversibility

Static marker viewing tests file serving only. Identity viewing attempts a device-code-execution mechanism and might execute as root if this firmware is vulnerable. The prepared CGI contains no writes to TV storage, networking commands, persistent process, reboot, firmware operation, or setting change. Expected impact is a temporary change of the displayed page. Firmware behavior is untested: an error, blank page, or webview crash is possible; risk cannot be guaranteed zero.

Exiting via the normal Home/Input controls and removing the USB are the expected recovery steps. They have not been independently verified for a failed CGI on this firmware. The test deliberately avoids modifications to boot, Home routing, browser security, debug flags, accounts, and internal files. No bind shell or general command receiver is provided. The pairing token goes only to the paired LAN control endpoint and is not copied onto USB; the CGI does not read environment variables or credentials.

Do not run this during a firmware update. If the marker fails, CGI is unavailable, the source text appears instead of results, or the identity is non-root, stop and record it. Do not try alternate mount names, system-modal contexts, payloads, configuration writes, or the other project's installer as an automatic fallback.

## Sequence after explicit approval

1. Copy the two probe files to the root of an existing FAT32 USB without replacing unrelated files. Attach it to the TV; keep the Mac and TV on the same LAN.
2. From the QuietFrame project directory, run `python3 scripts/launch-usb-check.py --marker`. Enter the TV's current IP and pairing token privately. Continue only if the TV visibly shows `QUIETFRAME_USB_MARKER_V1`.
3. Run `python3 scripts/launch-usb-check.py --identity`. Confirm the TV shows `QUIETFRAME_IDENTITY_BEGIN`, a numeric UID, OS, architecture, and `QUIETFRAME_IDENTITY_END`. A successful API response alone is insufficient.
4. Report only that short on-screen result. `uid=0` would establish root execution for this CGI; seeing the file contents would establish only file serving. Neither establishes persistence or a Home override.
5. Return to native Home using the original remote and remove the USB. No further native operations are included in the approval scope.

If root execution works, the next separately scoped task would be read-only mapping of this TV's native bundle paths and mount layout. A permanent Home patch would still require exact originals, a verified restoration path, model-specific source review, and separate approval. The older model's files and configuration must not be copied onto this TV.
