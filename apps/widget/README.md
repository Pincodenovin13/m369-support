# M369 Support Widget — Embeddable Widget

> **Path:** `apps/widget/`
> **Status:** ⚠️ `[PLANNED]` — NOT IMPLEMENTED
> **Parent docs:** [`/REPOSITORY_MAP.md`](../../REPOSITORY_MAP.md) · [`/STATE.md`](../../STATE.md)

The embeddable customer-facing chat widget for M369 Support. This is a future product component.

## Current State

This directory currently contains only a placeholder:

```
apps/widget/
└── src/
    └── .gitkeep    # "# Future: embeddable widget"
```

**No source code, no build config, no package.json.** The widget is planned but not yet implemented.

## When Implementation Begins

When the widget is implemented, it will likely include:

```
apps/widget/
├── src/
│   ├── index.ts          # Widget entry point
│   ├── components/        # React components for the chat UI
│   └── api.ts            # API client (talks to M369 backend)
├── public/
│   └── widget.js         # Compiled embeddable bundle
├── package.json          # Build deps
└── README.md             # Widget-specific docs
```

## Do NOT Add Fake Code

Per M369 project rules: "Do not create fake widget functionality. The widget is still a future product component and must be clearly marked as such."

Until real implementation begins, this README and the `.gitkeep` placeholder are the only files in this directory.
