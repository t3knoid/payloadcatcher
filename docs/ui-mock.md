# PayloadCatcher UI Mock

## 1. Goals

1. Keep interface simple and easy to scan.
2. Make callback URL copy action obvious.
3. Support desktop and small devices using a baseline mobile portrait viewport.

## 2. Layout Summary

1. Header row:
   - App logo + title
   - Optional status badge
2. First-visit privacy notice:
   - Clear disclosure that connection and browser metadata are collected when an inbox is provisioned
   - Explicit GPS opt-in control
   - Link to the operator privacy notes page
3. Callback URL row:
   - Clickable URL control
   - Click action copies URL to clipboard
4. Main content:
   - Desktop: two columns (narrow left list + wide right payload)
   - Mobile: stacked list first, payload second

## 3. Desktop Mock (>= 1024px)

```text
+----------------------------------------------------------------------------------+
| [Logo] PayloadCatcher                                                 [Active]  |
+----------------------------------------------------------------------------------+
| Privacy notice: browser and connection metadata is collected on provisioning.    |
| [ ] Allow one-time GPS capture    [Review and start inbox]   [Privacy notes]     |
+----------------------------------------------------------------------------------+
| Callback URL: [ https://payloadcat.ch/hook/550e...4000 ] [Copy]                 |
+-------------------------------------+--------------------------------------------+
| Search requests                     | Payload (YAML) [Copy payload]              |
| [ Search by id, ip, method... ]     | ----------------------------------------   |
| [Prev] Page 1 [Next]                | id: 01jv4d6...                             |
| > 12:03:02 POST                     | received_at: 2026-05-15T12:03:02Z          |
|   req-003... 203.0.113.10           | headers:                                    |
|   type: patch id: 3 status: queued  |   content-type: application/json            |
|   12:01:55 POST                     | payload:                                    |
|   req-002... 203.0.113.10           |   foo: bar                                  |
|   type: signup email: ada@...       |   count: 2                                  |
|                                     |   foo: bar                                  |
|                                     |   count: 2                                  |
+-------------------------------------+--------------------------------------------+
```

Column ratio target: left 30% and right 70%.

## 4. Mobile Mock (Small-Device Baseline)

```text
+--------------------------------------+
| [Logo] PayloadCatcher      [Active]  |
+--------------------------------------+
| Privacy notice                        |
| browser + connection metadata         |
| [ ] GPS opt-in                        |
| [Review and start inbox]              |
+--------------------------------------+
| Callback URL                          |
| [ https://payloadcat.ch/hook/550e... ]
| [Tap to Copy]                         |
+--------------------------------------+
| Search requests                       |
| [ Search... ]                         |
| [Prev] Page 1 [Next]                  |
| > 12:03:02 POST                       |
|   req-003... 203.0.113.10             |
|   type: patch id: 3 status: queued    |
|   12:01:55 POST                       |
|   req-002... 203.0.113.10             |
|   type: signup email: ada@...         |
+--------------------------------------+
| Selected payload (YAML) [Copy]        |
| id: 01jv4d6...                        |
| received_at: 2026-05-15T12:03:02Z     |
| headers:                              |
|   content-type: application/json      |
| payload:                              |
|   foo: bar                            |
|   count: 2                            |
+--------------------------------------+
```

Mobile behavior notes:

1. Keep controls full-width and touch-friendly.
2. Preserve selected request while scrolling.
3. Keep copy action visible without opening additional menus.
4. Show a readable loading state while the selected payload detail is fetched.
5. Show a safe inline error message in the payload panel when the selected payload detail is unavailable.
6. For very large payloads, show the selected payload incrementally with a visible "Show more" control.

## 5. Interaction Notes

1. Callback URL click behavior:
   - Primary interaction copies URL to clipboard.
   - Show non-blocking confirmation (for example "Copied").
2. First-visit privacy behavior:
   - Show the privacy notice before provisioning the first inbox in the browser.
   - Keep GPS collection disabled unless the operator explicitly opts in.
   - Continue provisioning even when the browser does not return geolocation data.
   - Keep a readable informational message visible after provisioning if geolocation is denied, unavailable, or the GPS metadata update cannot be saved.
3. Request row click behavior:
   - Update selected row style.
   - Load the selected request detail into the payload panel.
   - Show a readable loading state while the detail request is pending.
   - Surface a safe inline error if the detail request fails.
4. Search behavior:
   - Filter left list by request id, method, source IP, and payload preview text.
5. Pagination behavior:
   - Show previous and next controls with the current page indicator.
   - Preserve the active filter and cursor-backed page when the direct inbox route reloads.
6. Payload panel behavior:
   - Show captured request metadata including request ID, received time, method, content type, and sanitized headers.
   - Copy the full selected payload to the clipboard without opening a secondary menu.
   - Reveal very large payloads incrementally so the panel stays responsive on desktop and mobile.
