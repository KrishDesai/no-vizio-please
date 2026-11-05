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

## Prepared next step: read configuration on this TV

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

Only numeric app identity, selected message structure, key names and types are printed. Raw values, URLs, device identifiers and response bodies are withheld; nothing is saved or uploaded. Configuration-query access from the external paired API is untested. An HTTP rejection is a useful result; it does not prove that the corresponding internal route is unavailable. The sanitized report is **not a recovery backup**.

## Before considering a native write

An experiment needs a specific routing field or native operation, evidence of its consumer, exact model compatibility, and a target that can load QuietFrame. Its expected effect on boot, Home, app exit and HDMI must be distinguished. Capture original values privately with their types and absent-key state. Prepare exact restoration and establish that control/recovery remains reachable if Home fails. A saved value alone does not establish recovery.

Changing a startup target could leave Home blank or repeatedly restarting if the target is invalid or the host is unavailable. Recovery might require resetting the TV; no independent recovery transport has been established. Risk of a launcher failure cannot currently be bounded well enough to propose a write.

The user's original request requires a separate safety assessment and explicit approval before undocumented persistence or risky native changes. The present request authorizes this investigation; it has not been treated as approval to change unknown native settings. No approval for such a write is requested yet because there is no concrete apply/restore operation to review.

The next result should determine whether we can trace a real VIZIO Home-routing consumer. If the available descriptor is only informational or cloud-managed, further source/native analysis will be necessary; the inspector is not itself a bypass or a promise that one exists.
