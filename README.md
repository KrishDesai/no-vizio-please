# QuietFrame v8.1 — hosted TV control test

Target: **onn W4K43M-1030**, firmware **86.920.9.3-2**, software **86.920.9.3-2.12**. This is a static, self-contained `index.html`. Its control requests target only the TV's `http://127.0.0.1:7346`; no running Mac controller is involved. **The owner confirmed YouTube launching and PS4/HDMI 3 switching from hosted HTTPS with the Mac disconnected on November 5, 2026.** Internet access to the static host is required when loading the page. This is not an offline installation or a default launcher replacement.

## Evidence and scope

| Behavior | Evidence |
| --- | --- |
| Remote navigation; YouTube 5/1, Netflix 3/1, Prime Video 3/3; PS4 `hdmi3` via fresh numeric HASHVAL | User reports successful physical-TV tests in earlier versions. |
| TV-side YouTube and PS4 control from a locally HTTP-served page | User reports v7 passed on this exact TV. |
| v8 control code matches available v7 | Compared with `~/Downloads/quietframe-vizio-v7-probe/quietframe-vizio.html`; original differences were presentation/status text only. |
| Hosted HTTPS: YouTube launch and PS4/HDMI 3 switch with Mac disconnected | **Owner-confirmed November 5, 2026**, from `https://krishdesai.github.io/no-vizio-please/`. Successful actions exercise token acquisition, app-launch PUT, and input read/modify paths. Individual HTTP responses, browser user agent, and power-probe status were not separately supplied. |
| Netflix / Prime Video from hosted HTTPS | Still untested in the hosted context; earlier native mappings remain unchanged. |
| Back/Exit from YouTube launched by hosted QuietFrame, Mac disconnected | **Owner-confirmed November 5, 2026:** returns to VIZIO Home, not QuietFrame. |
| Normal remote power off/on while hosted QuietFrame is visible, Mac disconnected | **Owner-confirmed November 5, 2026:** opens VIZIO Home. Standby does not restore QuietFrame under the tested settings. |
| QuietFrame/Conjure in the native apps or recent-apps list | **Owner-confirmed November 5, 2026:** neither appears. No selectable relaunch shortcut was found in the inspected UI. |
| HDMI 1 / HDMI 2 | Configured; physical switching still needs independent confirmation. |
| Startup into QuietFrame; Home returns to QuietFrame | **Unsolved.** User reports Home returns to VIZIO Home and reboot does not restore QuietFrame. |

The full `CODEX_CONTEXT_QUIETFRAME.md` and v6 source were unavailable. The user authorized proceeding using v8 and the pasted history; an available v7 copy was also inspected. No UI redesign was made.

Changes cover request timeouts, safe diagnostics, redirect rejection, duplicate-command prevention, and guarding dialogs against late results. The dock remains **PS4 (HDMI 3), HDMI 1, HDMI 2, YouTube, Netflix, Prime Video, Appearance**. Internal tokens are obtained per action and remain in page memory. No new TV routes, persistent configuration writes, or external scripts were added.

## Publish to GitHub Pages

1. Create or select your own trusted repository. GitHub Free requires a public repository for Pages. Upload **`index.html`** and the empty **`.nojekyll`** file at its root. Only these files are needed by the TV. Do not upload pairing credentials, shell history, or private environment files.
2. In **Settings → Pages → Build and deployment**, select **Deploy from a branch**, branch `main`, folder `/(root)`, and Save. Keep **Enforce HTTPS** enabled.
3. Wait for deployment to finish. Use the exact URL supplied by GitHub, usually `https://USERNAME.github.io/REPOSITORY/` (include the project path).
4. Open the URL on the Mac. This checks hosting, not TV control: loopback on the Mac refers to the Mac. Press **I** to verify build `v8.1-hosted-test`. For an updated deployment, append `?qf=v8.1-hosted-test` to distinguish it from a cached older page.

No build process or Python server is required. See [GitHub's Pages guide](https://docs.github.com/en/pages/getting-started-with-github-pages/creating-a-github-pages-site) and [branch-source instructions](https://docs.github.com/en/pages/getting-started-with-github-pages/configuring-a-publishing-source-for-your-github-pages-site).

The source repository is [KrishDesai/no-vizio-please](https://github.com/KrishDesai/no-vizio-please). With the owner's approval, it was made public because the current GitHub plan does not support Pages from a private repository. Pages is configured for `main` at `/(root)`, with HTTPS enforced, at [QuietFrame](https://krishdesai.github.io/no-vizio-please/). Confirm deployment succeeds before using it on the TV. The page requires no GitHub sign-in. GitHub CLI authentication works when network access is permitted. Source publication is performed from a temporary checkout; this local workspace does not need a running Git or Python service.

## One-time launch from the Mac

While the TV is powered on and both devices are on the LAN, run from this folder:

```sh
python3 scripts/launch-quietframe.py
```

The helper asks for the TV's numeric LAN IP, your actual HTTPS Pages URL, and the external pairing token using a hidden prompt. It also accepts already **exported** `TV_IP` and `VIZIO_TOKEN` variables. Shell variables from another Terminal do not carry over; use the prompts if needed. Do not put your token in the command line or source files.

It sends one paired `PUT https://TV_IP:7345/app/launch` with:

```json
{"VALUE":{"MESSAGE":"YOUR_HTTPS_PAGES_URL","NAME_SPACE":4,"APP_ID":"17"}}
```

It then exits. It does not run a server, save tokens, use system proxies, follow redirects, or print response bodies. Like the previous `curl -k` command, it skips certificate validation for the paired LAN endpoint because its certificate does not match the IP. This changes no browser or TV setting; [the API reference describes this limitation](https://github.com/exiva/Vizio_SmartCast_API#overview).

`Launch accepted` means the API reported success. Confirm that the page actually appears on the TV. Failure to read a launch response can still mean it launched; check the screen before retrying.

## Reproducible physical-TV test

Record the current firmware/software first. Stop previous QuietFrame HTTP/controller servers. Keep the TV connected to the router/internet throughout. The Mac must not have Ethernet, tethering, or another active network route during independence tests.

1. Deploy the files and launch the **HTTPS hosted URL** using the helper. Confirm QuietFrame appears, PS4 is initially focused, and remote arrows, OK and Back work.
2. Open diagnostics using remote **Info**, if the webview delivers it. Record the build, `Page: https:`, secure-context value, browser user agent, power-probe result, and last-request summary. **I** on a keyboard or clicking the status chip are fallbacks. Info delivery has not been tested on this firmware. Back/Escape closes the dialog. Nothing is uploaded or logged.
3. `Power read OK` establishes only an unauthenticated JSON power read. It does **not** establish token acquisition, authenticated input reads, or PUT/preflight access.
4. Turn **Mac Wi-Fi off** and disconnect every other Mac network connection. Select **YouTube**. Record whether the actual native app opens, rather than only an accepted-command overlay.
5. Reconnect the Mac solely to relaunch the hosted URL, then disconnect it **before selecting each next tile**. Repeat for PS4/HDMI 3, Netflix, Prime Video, HDMI 1 and HDMI 2. Connect/power a known source for HDMI tests. If already on the target HDMI, QuietFrame intentionally sends no switching PUT; select another input using the original remote, then relaunch and repeat.
6. For one fresh page load, leave QuietFrame open **more than five minutes** before selecting a tile, with the Mac disconnected. This exercises fresh per-action token acquisition after idle; it does not prove an exact token lifetime.
7. Record failures before relaunching: action, failing method/path, HTTP status if visible, or timeout/no-readable-response. Diagnostics exist only in page memory and disappear on reload. Do not share token responses or network headers.

A blank result is untested:

| Check | Mac fully disconnected? | API/UI summary | Actual TV behavior | Pass/fail |
| --- | --- | --- | --- | --- |
| Hosted page/build + navigation | Initial launch uses Mac | | | |
| Power probe from hosted HTTPS | | | | |
| YouTube | Yes, owner-confirmed | Not separately recorded | Native app works | Pass, November 5, 2026 |
| PS4 / HDMI 3, from another input | Yes, owner-confirmed after requesting this procedure | Not separately recorded | Owner confirmed input test works | Pass, November 5, 2026 |
| Netflix | | | | |
| Prime Video | | | | |
| HDMI 1, from another input | | | | |
| HDMI 2, from another input | | | | |
| First action after >5 minutes idle | | | | |

Passing these rows demonstrates **hosted-page and active-session control independence**. Requiring the Mac to relaunch after leaving the page still prevents an independent daily launcher experience. Do not mark the full goal complete on this basis.

## Interpret failures without guessing

| Observation | What it establishes / next step |
| --- | --- |
| Page never appears | Check deployment/URL and TV internet first; accepted external launch does not verify loading. |
| Probe reports HTTP status or non-JSON | A response was readable; record the summary. Do not label it a browser block. |
| `No readable response` | Could be CORS, mixed content, local-network policy, redirect rejection, or service reachability. Record browser version and failing method/path. |
| Power works; token GET fails | Token endpoint access differs from power-read access. No authenticated command was sent by this action. |
| Token works; authenticated input GET fails | AUTH-bearing cross-origin requests need separate verification. |
| Reads work; PUT fails | The write/preflight path needs verification. Do not assume app IDs are wrong. |
| Input HASHVAL error | Each attempt reads a fresh numeric HASHVAL. Record the rejection; there is no blind retry. |
| PUT times out or response is unreadable | The command may have executed. Check the TV before retrying. Abort does not undo an accepted command. |

AUTH-bearing GETs and JSON PUTs can require CORS preflights because of the header, method, and content type. Pages cannot change the TV service's CORS responses. `no-cors` cannot supply readable JSON/token/HASHVAL responses or the required request contract. See the [Fetch standard](https://fetch.spec.whatwg.org/#http-cors-protocol).

Do not assume HTTPS must fail solely because loopback uses HTTP. [Secure Contexts](https://www.w3.org/TR/secure-contexts/#is-origin-trustworthy) classifies loopback origins as potentially trustworthy; [Chrome's local-network documentation](https://developer.chrome.com/blog/local-network-access) describes additional version-dependent restrictions. These are browser references, **not evidence of the TV's browser version or permissions**. No security flags, alternate privileged launcher contexts, or speculative compatibility options were added.

Precise diagnosis of a generic policy/network failure requires a console/preflight trace from an already available, supported debugging session or vendor guidance. This project enables no debugging listener. Re-running v7 over local HTTP provides a reversible comparison but reintroduces the Mac for that comparison and does not establish why HTTPS failed.

## Startup and Home: next gate after hosted controls pass

Hosted YouTube and PS4 tests now pass. The owner confirmed that both Back/Exit from YouTube and normal remote standby/wake return to VIZIO Home with the Mac disconnected. Neither restores QuietFrame under the tested settings. The owner also confirmed that neither QuietFrame nor Conjure appears in the native apps/recent-apps list. A full restart remains untested in the hosted context. Direct Home-button/reboot behavior in the original history remains the only supplied evidence for those paths.

Current feasibility assessment: page delivery and the tested controls operate independently of the Mac, but the daily launcher experience does not. No TV-only relaunch path has been verified, and the inspected native apps/recents UI provides no QuietFrame/Conjure entry. The current hosted-page approach does not meet the default-interface objective. Further changes to the static page alone do not establish OS startup integration or Home-button behavior; those require an OS mechanism. No supported owner-configurable mechanism has been found in the reviewed public documentation. This is a limitation of the verified approach and available documentation, not proof that every possible firmware/vendor-assisted mechanism is impossible. Vendor-supported app registration is an avenue for inquiry, not an established solution. UI redesign is deferred because it would not resolve this blocker.

The user has now requested investigation of an unofficial approach comparable to Samsung CleanFrame. See [native-routing research and the prepared read-only inspector](NATIVE_ROUTING_RESEARCH.md). This identifies a VIZIO configuration lead without claiming a working bypass or changing TV state. The existing hosted launcher is unchanged.

The first exact-TV inspector report confirmed paired configuration reads and identified active Home as namespace 4/app 1 (`bundles/home`), differing from `SmartCastHome.AppInfo` at namespace 2/app 1. Inspector version 2 expands the `VIZIOHome`/`SystemUI` configuration structure through the same four reads. This mismatch is a reason to trace the actual native handler, not to try a guessed persistent override.

The expanded report exposes telemetry/UI flags rather than a Home assignment. A newly reviewed older-model VIZIO replacement project provides an alternative lead using USB-served CGI. See the [prepared USB compatibility probe and risk assessment](USB_PROBE_ASSESSMENT.md). It is unverified on this firmware and has not been authorized or run on the TV. The probe and launcher are isolated from the working hosted page.

The owner has no USB drive. The current alternative is the [network-only read-only source audit](native-audit.html), launched with the same one-shot helper using `https://krishdesai.github.io/no-vizio-please/native-audit.html`. It reads bounded local web assets as text and reports source references, without credentials, vendor script execution, uploads or settings changes. This is an investigation tool; a USB-free permanent replacement remains unverified. See [scope and limitations](NATIVE_ROUTING_RESEARCH.md#current-constraint-and-network-only-source-audit).

The owner confirmed the first source audit could read `/scfs/sctv/main.html` (1,092 characters). It found no recognized direct script links. Audit version 2 adds wrapper/redirect/inline-script structure inspection with a four-asset read limit. Relaunch using `https://krishdesai.github.io/no-vizio-please/native-audit.html?audit=2` and check `audit_version: 2`; no native write or code-execution test is involved.

No supported boot launch or Home replacement has been established for this model/firmware. A webpage cannot relaunch itself after destruction; receiving DOM keys while visible does not establish system Home interception.

The [Conjure client reference](https://github.com/get-air/vizio#smart-app-cast--conjure) distinguishes URL launch from installation or adding a tile. The [onn/VIZIO OS manual](https://onntvsupport.com/sites/default/files/products/docs/onn_Vizio_User_Manual.pdf) describes Home opening the built-in screen; it does not document an owner-installed replacement. This absence does not prove every vendor-assisted option impossible.

After hosted controls pass, record these **observations**, with the Mac disconnected:

| Safe check | Question |
| --- | --- |
| Home while QuietFrame is open | Does it still open VIZIO Home? Do not attempt remapping. |
| Original Back/Exit after apps and HDMI | YouTube returns to VIZIO Home (owner-confirmed); other apps/HDMI remain untested. No automatic relaunch code is included. |
| Normal standby/wake with QuietFrame open | Returns to VIZIO Home under tested settings (owner-confirmed). QuietFrame is not restored. |
| Normal restart using a visible TV menu, if present | Does a fresh OS session restore it? Avoid factory reset/service menus. |
| Visible apps/recents | Neither QuietFrame nor Conjure is listed (owner-confirmed). No relaunch shortcut was found in the inspected UI; arbitrary URL bookmarking is not established. |
| Visible startup/input settings | Record offered choices before changing anything. Last HDMI input could help PS4 but does not install QuietFrame or remap Home. Restore test settings. |

If normal settings provide no URL shortcut/startup choice, the next supported avenue is asking VIZIO about owner app registration, URL shortcuts, startup eligibility, and Home behavior for this firmware. [VIZIO's developer-program announcement](https://platformplus.vizio.com/news/vizio-welcomes-developers-through-first-ever-conference-and-preferred-developer-program) describes partner integration/certification; it does **not** promise acceptance of a personal launcher or Home override. No vendor messages were sent.

Research checked November 5, 2026: [VIZIO's current Home FAQ](https://www.vizio.com/en/home-screen) describes adding apps from its catalog and arranging them, without documenting arbitrary URL tiles or remapping Home. The [official content-partner page](https://www.vizio.com/en/content-partners) offers app submission and partner onboarding. Its developer-specification link, [docs.developer.vizio.com](https://docs.developer.vizio.com/), redirects to sign-in; those specifications were not accessible in this session. Public materials therefore do not establish an owner-installation, autostart, or Home-override API for this firmware. This is a documentation/access limit, not proof of impossibility. No app-submission or support forms were sent.

The [sibling-model research](https://github.com/vindeckyy/smartcast-backdoor) describes internal access and undocumented persistence. This does not establish a supported installation method or safe Home replacement here. No config-store writes, service activation, exploit chain, firmware changes, or always-on watcher are included. Without a supported relaunch path, hosted QuietFrame remains manually launched.

## Local verification

```sh
node --test tests/tv-control.test.cjs
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_*.py'
```

JavaScript tests execute the inline script with mock DOM/fetch and simulated timers. They cover mappings, HASHVALs, navigation, token-safe diagnostics, timeouts (including body reads and browsers without AbortController), duplicate commands and late completion. Python tests mock the one-shot launcher. Neither suite contacts a TV, deploys a page, or verifies browser policy in VIZIO's real webview.
