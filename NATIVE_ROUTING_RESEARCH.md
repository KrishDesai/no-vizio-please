# QuietFrame native Home research

Assessment date: November 5, 2026. Target: onn W4K43M-1030, reported firmware 86.920.9.3-2 / software 86.920.9.3-2.12.

**An unofficial research path exists; a working VIZIO Home/startup bypass has not been identified.** The normal-interface tests establish the limit of the current launcher, not that every native mechanism is impossible. This assessment expands the investigation beyond supported interfaces, as requested. No experimental TV writes were performed.

## What CleanFrame actually changes

CleanFrame separates app installation from Home routing. Its [native control source](https://github.com/nthnclrk/CleanFrame/blob/main/scripts/native-home/Control.cs) invokes Tizen's native Home-operation setter, changes `db/appfw/home_appid`, and enables Home autostart through vconf. It checks its reference firmware, user identity, installed app and saved original values, and includes restore logic. These are Tizen-specific functions and configuration names; copying them into VIZIO JavaScript would not supply equivalent VIZIO services.

Its [runner](https://github.com/nthnclrk/CleanFrame/blob/main/scripts/native-home/run.py) stages a temporary helper and uses a package-installer argument command-execution workaround through Samsung's developer connection. It is an undocumented device operation, not just a webpage preference. The [reference test record](https://github.com/nthnclrk/CleanFrame/blob/main/docs/tv-status.md) confirms physical Home routing from Netflix but still lists ordinary power-on checks as pending. Its success does not establish a portable cross-brand boot mechanism.

Reviewed file identities: `Control.cs` Git blob `f738252e21ceb09da170c0295881c12b11d1db61`; `run.py` blob `e125de46f1ccefb9ef15170494aae3f294f06058`. Copies were read offline in a temporary directory. None of their tools were executed.

## VIZIO evidence and candidate

The [sibling-model report](https://github.com/vindeckyy/smartcast-backdoor) describes configuration-store writes on W4K65M-1030 with the same base firmware. It demonstrates configuration retention after page exit, not a custom Home handler; store persistence across reboot is explicitly an open test. It also reports no successful native execution through the older `/install` technique. These limits matter when comparing it with CleanFrame.

Offline review of the [published companion SDK](https://github.com/vindeckyy/smartcast-backdoor/blob/master/extracted/companion-lib.js) found a `SmartCastHome.AppInfo` descriptor, configuration-property reads, separate device-store reads/writes, and app-launch/key-event interfaces. It does not establish which native component consumes Home routing, whether configuration-store writes override these configuration properties, or whether a background page survives other apps. **The candidate is investigation of Home configuration and its consumer, not a proposed setting to change.** SDK blob: `cd996a4e453749954191e6095572029d9e366130`.

Do not equate a successful store write with an effective Home override. A key can exist without any native code reading it. Likewise, registering key events does not establish receipt or interception of the system Home key while another app is active.

## First report from the exact TV

The owner supplied the sanitized inspector report on November 5, 2026. All four external paired queries succeeded. With VIZIO Home visible, `/app/current` returned namespace **4**, app **1**, and the message identifying `app: home`, `bundle: bundles/home`. In contrast, `SmartCastHome.AppInfo` described namespace **2**, app **1**, with an empty message. These are distinct app identities. The report therefore does not establish that the `SmartCastHome` descriptor controls the active native Home; a legacy or indirect role is a hypothesis, not a confirmed explanation.

`AppConfigs` contains `VIZIOHome` and `SystemUI` objects. The first inspector deliberately omitted most of their child structure. The next bounded inspection expands those two sections and selected asset-related fields, still using the same successful read requests. It also labels built-in apps by CNAME when present and excludes HomeKit matches from Home-routing candidates. HomeKit fields concern a different feature and do not establish launcher routing.

No change to namespace 2/app 1, no replacement of `bundles/home`, and no store override is proposed from this report. We need to identify the actual consumer and recovery mechanism before designing any native write.

## Expanded report and alternative implementation evidence

The corrected version-2 report succeeded on all four reads. `VIZIOHome` exposes Sentry settings; the reported `SystemUI` structure exposes Sentry, notification, logging/debug and UI feature fields, without a visible Home-app assignment. `VIZIOApps` identifies namespace 2/app 1 as `sctv`; its configured endpoint is `/scfs/sctv/main.html`, whereas current Home still identifies `bundles/home` at namespace 4/app 1. These observations do not establish a writable native routing field. No further version of the configuration inspector is needed for the same sections at this point.

A separate project, [Vizio Open Home](https://github.com/jordanmateo-byte/vizio-open-home), reports autonomous Home/startup replacement on older M657-G0 firmware using USB-served CGI execution and a backed-up HTML entrypoint modification. This is a concrete VIZIO implementation to assess, but it does not validate that CGI route, file layout, or Home patch for our model. A minimal USB marker and identity-only probe have been prepared for review, with a [separate compatibility and risk assessment](USB_PROBE_ASSESSMENT.md). They have not been launched on the TV, and exploit-based testing still requires the owner's explicit approval under the original project instructions.

## Current constraint and network-only source audit

The owner has no USB drive. The USB compatibility probe remains unapproved and unrun. Hosting a CGI on GitHub or the Mac does not substitute for executing it through the TV's local USB-serving handler. The reviewed same-base-firmware [LAN research](https://github.com/vindeckyy/smartcast-backdoor) demonstrates webview/configuration access, but does not establish a native shell, writable Home files, or a working permanent launcher replacement. No USB-free permanent method is verified for this TV.

The prepared alternative is **read-only investigation**, using the existing namespace 4/app 17 launch context, not a new privileged context. Launch [native-audit.html](native-audit.html) from GitHub Pages using the ordinary helper:

```sh
python3 scripts/launch-quietframe.py
```

At its URL prompt, enter `https://krishdesai.github.io/no-vizio-please/native-audit.html`. Keep the Mac and TV connected for the one-shot launch. No USB is needed. The audit page itself obtains no control/authentication token.

The page reads the confirmed TV-local `/scfs/sctv/main.html` as text and at most three directly linked local JavaScript assets under `/scfs/`. It prints configuration-key references, a few routing-related presence flags, and sanitized public VIZIO script URLs for later source inspection. It does not execute those assets, load the SDK, fetch remote scripts, transmit source or reports, register keys, write settings, or connect to LOKI. A restrictive content policy permits fetches only to `http://127.0.0.1:12345`. Requests time out; oversized documents are rejected for inspection.

Read access to port 12345 from our exact hosted app context is untested. A failure is recorded without enabling flags or switching to the system-modal context. A successful read only establishes access to those web assets; it does not prove they drive the native `bundles/home` UI. Coverage excludes native bundle files, external scripts and recursively imported modules. Absence of routing references in this bounded scan is not proof that no override exists.

## Paired configuration inspector (completed, available to rerun)

Leave the TV on **VIZIO Home**. From this project's directory on the Mac, while both devices are on the LAN:

```sh
python3 scripts/inspect-native-routing.py
```

Python 3.8+ is required. Enter the numeric TV IP and external pairing token at the hidden local prompt, or use already exported `TV_IP` / `VIZIO_TOKEN`. Do not paste the token into chat or source files.

The inspector makes exactly four allowlisted queries:

| Method and route | Purpose |
| --- | --- |
| `GET /app/current` | Identify the currently running native Home app |
| `PUT /app/config/get_property`, `VALUE: SmartCastHome` | Inspect the Home descriptor's structure |
| Same read route, `VALUE: AppConfigs` | Find relevant field names and types |
| Same read route, `VALUE: VIZIOApps` | Summarize numeric built-in app identities |

The PUT method here follows the SDK's **read** implementation. There are no setting writes, launches, installs, reboots, debug flags, key registration, or exploit payloads. The helper does not execute VIZIO's SDK, whose initialization includes telemetry code. It uses the paired LAN HTTPS endpoint directly, rejects redirects, bypasses system proxies, and handles the same TV certificate limitation as the existing launch helper.

Inspector version 2 prints numeric app identity, app CNAMEs, selected message structure, and key names/types. For the selected sections it also prints recognized VIZIO/loopback source origins and static asset URLs with queries/fragments removed. URL credentials, unknown-host URLs, sensitive-field values, other scalar values, device identifiers and response bodies are withheld; nothing is saved or uploaded. External paired access to these four reads is now owner-confirmed. A future HTTP rejection would not prove that an internal route is unavailable. The sanitized report is **not a recovery backup**.

## Before considering a native write

An experiment needs a specific routing field or native operation, evidence of its consumer, exact model compatibility, and a target that can load QuietFrame. Its expected effect on boot, Home, app exit and HDMI must be distinguished. Capture original values privately with their types and absent-key state. Prepare exact restoration and establish that control/recovery remains reachable if Home fails. A saved value alone does not establish recovery.

Changing a startup target could leave Home blank or repeatedly restarting if the target is invalid or the host is unavailable. Recovery might require resetting the TV; no independent recovery transport has been established. Risk of a launcher failure cannot currently be bounded well enough to propose a write.

The user's original request requires a separate safety assessment and explicit approval before undocumented persistence or risky native changes. The present request authorizes this investigation; it has not been treated as approval to change unknown native settings. No approval for such a write is requested yet because there is no concrete apply/restore operation to review.

The configuration inspection has not exposed a Home override. Further native/source analysis is necessary; neither inspector is a bypass. The network-only source audit can advance that analysis without a USB, but does not yet supply installation, boot integration or Home interception.
