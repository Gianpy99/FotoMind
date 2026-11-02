# FotoMind Design System v1.0

**Direction:** Professional photography workspace  
**Personality:** Precise, calm, creative and trustworthy  
**Colour identity:** Deep navy + warm orange  
**Default appearance:** Dark theme  
**Applies to:** Tauri desktop and web application

## 1. Design principles

1. Photography comes first: images and video are the primary content.
2. Professional, not intimidating: precise controls with a calm interface.
3. One product, two shells: desktop and web share tokens and components.
4. Non-destructive by default: originals are immutable; edits and AI results are derivatives.
5. AI is a tool, not the identity: integrate it into editing rather than making the app chatbot-first.
6. Make system state legible: imports, indexing, backups and AI jobs expose progress and errors.
7. Dense where useful, spacious where it matters: library grids can be dense; editing canvas should be generous.

## 2. Brand palette

### Dark theme

| Token      | Hex       | Usage                           |
| ---------- | --------- | ------------------------------- |
| navy-950   | `#081426` | Application background          |
| navy-900   | `#0D1B2A` | Navigation                      |
| navy-850   | `#12243A` | Panels and inspector            |
| navy-800   | `#19324D` | Hover and selected surfaces     |
| navy-700   | `#274663` | Borders and separators          |
| slate-600  | `#52657A` | Muted controls                  |
| slate-400  | `#9AAABD` | Secondary text                  |
| slate-200  | `#D8E1EA` | Primary text                    |
| white      | `#F7F9FC` | High-emphasis text              |
| orange-500 | `#F28C28` | Main accent and primary actions |
| orange-400 | `#FFA64D` | Accent hover                    |
| orange-600 | `#D96F12` | Accent pressed                  |
| orange-100 | `#FFF0DF` | Soft accent surface             |

### Semantic colours

| Token   | Hex       | Usage                        |
| ------- | --------- | ---------------------------- |
| success | `#38B781` | Completed jobs / healthy     |
| warning | `#E8B04B` | Attention required           |
| danger  | `#E36B6B` | Errors / destructive actions |
| info    | `#62A9E8` | Informational state          |

### Light theme

| Token         | Hex       | Usage                  |
| ------------- | --------- | ---------------------- |
| light-bg      | `#F3F6FA` | Application background |
| light-surface | `#FFFFFF` | Panels                 |
| light-raised  | `#E9EFF5` | Secondary surfaces     |
| light-border  | `#D5DEE8` | Borders                |
| light-text    | `#142235` | Main text              |
| light-muted   | `#5C6B7D` | Secondary text         |
| light-navy    | `#10243B` | Navigation             |
| light-orange  | `#D96F12` | Accent                 |

## 3. Colour rules

- Use navy for structure and orange selectively for actions, selected states and focus.
- Do not make every icon, label or border orange.
- Avoid pure-black surfaces and large saturated-orange panels.
- Pair colour with text or icons; never rely on colour alone to communicate status.
- Dark is the default. Light mode maps the same semantic tokens to light values.

## 4. Typography

**Preferred font:** Inter, with system sans-serif fallbacks.

| Style       |     Size | Weight | Use                   |
| ----------- | -------: | -----: | --------------------- |
| Display     | 28–32 px |    600 | Rare page-level title |
| Page title  | 22–24 px |    600 | Workspace title       |
| Section     | 16–18 px |    600 | Panel heading         |
| Body        |    14 px |    400 | Standard UI           |
| Compact     | 12–13 px |    400 | Metadata              |
| Micro label |    11 px |    600 | Compact status        |

Use sentence case. Use tabular numerals for dates, file sizes, durations and adjustment values. Keep metadata readable.

## 5. Layout and spacing

Use a 4 px base scale: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64 px`.

- Left navigation: 220–250 px expanded; 64–72 px collapsed.
- Right inspector: 300–360 px, resizable where practical.
- Top toolbar: 48–56 px.
- Main content padding: 16 px minimum; 24 px on wide layouts.
- Panel padding: 12–16 px.
- Standard control height: 32–36 px.
- Primary button height: 36–40 px.
- Central canvas flexes to use available space.
- Navigation and inspector can collapse; avoid fixed layouts that fail on laptop screens.

## 6. Shape and elevation

- Control radius: 6 px.
- Panel radius: 8 px.
- Dialog radius: 10–12 px.
- Prefer thin borders to heavy shadows.
- Elevation is reserved for menus, popovers and dialogs.
- Use pill shapes only for tags, filters and compact status labels.

## 7. Information architecture

Four primary workspaces:

1. **Library** — browse, filter, rate and organise photographs and videos.
2. **Develop** — conventional non-destructive photo adjustments.
3. **AI Studio** — restoration and enhancement with explicit review.
4. **Media** — video-focused browsing, playback and technical metadata.

Persistent navigation includes workspaces, albums/collections, storage locations, saved searches, recent imports and favourites. Global search is reachable from every workspace.

## 8. Screen patterns

### Library

- Central thumbnail grid with adjustable density.
- Photos and videos appear in one catalogue.
- Video thumbnails show a play marker and duration.
- Offer grid and optional filmstrip/list modes.
- Filters: date, camera, lens, media type, rating, tags and storage availability.
- Keep filenames and technical metadata secondary to the image.

### Viewer

- Maximise the image/video canvas.
- Support fit, fill and 100% zoom.
- Provide previous/next navigation and collapsible filmstrip.
- Clearly identify original versus derivative.
- Avoid persistent controls over important image content.

### Develop

- Large central preview and right-side inspector.
- Group controls into crop/rotate, exposure, tone, colour, detail and lens correction.
- Sliders show numeric values and support precise keyboard adjustment.
- Provide per-control reset, section reset, undo/redo and edit history.
- Never overwrite source files.

### AI Studio

- Show source and proposed operation before processing.
- Display provider, model, settings and local/cloud execution location.
- Require explicit confirmation before cloud processing.
- Show progress, queue state, cancellation where supported and actionable errors.
- Compare original and result side-by-side or with a comparison slider.
- Require approval before accepting an output.
- Label reconstructed details; do not imply generated detail is factual recovery.

### Video detail

- Show poster frame, duration, resolution, frame rate, codec, file size and audio presence when available.
- Play the original where the runtime supports its codec.
- Explain unsupported codecs clearly.
- Video enhancement and editing remain outside the initial release.

## 9. Component standards

**Buttons**

- Primary: orange fill, dark text where contrast permits.
- Secondary: navy surface with subtle border.
- Tertiary: ghost/text style.
- Destructive: semantic danger treatment and confirmation.
- Avoid multiple competing primary buttons in one view.

**Inputs and sliders**

- Consistent height, border and focus treatment.
- Visible labels; placeholders are not labels.
- Numeric values editable where practical.
- Keyboard operation and visible focus state.

**Navigation**

- Selected workspace uses a raised navy surface plus orange marker/accent.
- Labels visible when expanded; tooltips in collapsed mode.

**Cards and thumbnails**

- Avoid generic dashboard cards in the library.
- Use image-led tiles with restrained metadata overlays.
- Preserve aspect ratio or make crop behaviour clear.
- Explicitly show loading, missing-original and offline-volume states.

**Tags and filters**

- Compact chips with clear selected/unselected states.
- Visible clear-filters action.
- Distinguish user tags from AI-generated labels.

**Dialogs and notifications**

- State the consequence of an action.
- Toasts are for brief confirmation, not important errors.
- Persistent job failures belong in the job centre.

## 10. Iconography and imagery

Use Lucide consistently: 16 px compact controls, 18–20 px navigation, 24 px larger empty states. Prefer one icon style. Orange icons are reserved for active or important states. Use real photographs and useful empty-state explanations rather than decorative illustrations.

## 11. Accessibility and interaction

- Full keyboard navigation for core workflows.
- Visible focus ring in both themes.
- Aim for 32 px minimum pointer targets in dense desktop UI and 40–44 px for touch-oriented UI.
- Maintain readable contrast.
- Never use colour as the only indicator of selection, error or completion.
- Respect reduced-motion preferences.
- Provide tooltips for unfamiliar editing controls.
- Support undo for non-destructive edits.

## 12. Responsive behaviour

- Wide desktop: navigation + canvas + inspector.
- Medium width: collapsible navigation and inspector.
- Narrow width: one primary panel at a time; editing controls become a drawer or dedicated panel.
- Do not simply shrink the three-column layout.
- On narrow screens prioritise browsing, search, review and playback over advanced editing.

## 13. Implementation rules for coding agents

- Implement tokens as CSS custom properties; do not scatter hard-coded colours.
- Use semantic variables such as `--color-bg`, `--color-surface`, `--color-text-primary`, `--color-accent` and `--color-danger`.
- Dark and light themes are token maps, not separate designs.
- Build shared components before individual workspaces.
- Include default, hover, focus, active, selected, disabled, loading, error and empty states.
- Add visual regression screenshots for the main screens.
- Agents must not invent new colours, radii, typography or button styles without updating this specification.

## 14. CSS token starter

```css
:root,
[data-theme="dark"] {
  color-scheme: dark;
  --color-bg: #081426;
  --color-nav: #0d1b2a;
  --color-surface: #12243a;
  --color-surface-hover: #19324d;
  --color-border: #274663;
  --color-text-primary: #f7f9fc;
  --color-text-secondary: #d8e1ea;
  --color-text-muted: #9aaabd;
  --color-accent: #f28c28;
  --color-accent-hover: #ffa64d;
  --color-accent-pressed: #d96f12;
  --color-success: #38b781;
  --color-warning: #e8b04b;
  --color-danger: #e36b6b;
  --color-info: #62a9e8;
  --radius-control: 6px;
  --radius-panel: 8px;
  --radius-dialog: 12px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
}

[data-theme="light"] {
  color-scheme: light;
  --color-bg: #f3f6fa;
  --color-nav: #10243b;
  --color-surface: #ffffff;
  --color-surface-hover: #e9eff5;
  --color-border: #d5dee8;
  --color-text-primary: #142235;
  --color-text-secondary: #33465b;
  --color-text-muted: #5c6b7d;
  --color-accent: #d96f12;
  --color-accent-hover: #f28c28;
  --color-accent-pressed: #b95a0b;
}
```

## 15. First implementation acceptance checklist

- [ ] Dark theme is the default and uses the navy/orange palette.
- [ ] Light theme uses the same semantic token structure.
- [ ] Typography, spacing, radii and icon sizing are centralised.
- [ ] Shared buttons, inputs, sliders, tabs, chips, dialogs and notifications exist.
- [ ] Library screen demonstrates both photo and video thumbnails.
- [ ] Viewer screen demonstrates a large image canvas.
- [ ] Develop screen demonstrates grouped adjustment controls.
- [ ] AI Studio demonstrates a local/cloud job and before/after review.
- [ ] Loading, empty, offline, missing-file, error and disabled states are designed.
- [ ] Desktop and web share the same component language.
- [ ] No workspace introduces unapproved colours or styles.

**Design decision:** FotoMind uses a deep navy foundation with a warm orange action accent. It should feel like a focused professional photography application: precise enough for serious editing, calm enough for long library sessions, and modern without chasing short-lived UI trends.
