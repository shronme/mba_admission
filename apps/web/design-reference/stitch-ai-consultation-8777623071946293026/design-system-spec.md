# Design System Specification: The Academic Editorial

## 1. Overview & Creative North Star
**Creative North Star: "The Digital Curator"**
This design system moves away from the "template" look of standard SaaS platforms, instead drawing inspiration from high-end editorial journals and the architectural permanence of Ivy League institutions. It is designed to feel like a bespoke consultancy experience—authoritative, quiet, and deeply intentional.

To achieve this, we reject rigid, boxed-in grids in favor of **Intentional Asymmetry**. By utilizing generous whitespace (negative space) as a functional element rather than a void, we guide the user’s eye through a curated narrative. Elements should feel like they are "resting" on a surface rather than being "trapped" in a container. Overlapping elements and high-contrast typography scales are the primary tools for establishing a sophisticated visual hierarchy.

---

## 2. Colors
The palette is rooted in a deep, authoritative Navy, balanced by the warmth of a refined Gold and the academic neutrality of Slate Blue.

### The "No-Line" Rule
**Borders are strictly prohibited for sectioning.** To move beyond a generic UI, boundaries must be defined solely through background color shifts. For example, a section using `surface_container_low` (#f3f4f5) should sit directly against a `surface` (#f8f9fa) background. This creates a seamless, modern transition that feels architectural rather than digital.

### Surface Hierarchy & Nesting
Treat the UI as a series of physical layers, like stacked sheets of fine heavy-weight paper.
- **Layer 0 (Base):** `surface` (#f8f9fa)
- **Layer 1 (Sectioning):** `surface_container_low` (#f3f4f5)
- **Layer 2 (Feature Cards):** `surface_container_lowest` (#ffffff)
- **Layer 3 (Floating Elements):** `surface_bright` (#f8f9fa) with ambient shadows.

### The "Glass & Gradient" Rule
To add "soul" to the interface, main CTAs or Hero sections should utilize a subtle linear gradient transitioning from `primary` (#041627) to `primary_container` (#1a2b3c). For floating navigation or modal overlays, use **Glassmorphism**: a semi-transparent `surface_container_lowest` with a 20px backdrop-blur to allow the rich brand colors to bleed through softly.

---

## 3. Typography
The typographic voice is a dialogue between tradition (the serif) and modern precision (the sans-serif).

- **Display & Headlines (Noto Serif):** These are the "Editorial" moments. Use `display-lg` (3.5rem) for hero statements to convey a sense of heritage and elite status. The high contrast of Noto Serif commands attention and establishes an immediate tone of expertise.
- **Body & Titles (Inter):** For all functional data, navigation, and long-form reading, Inter provides surgical legibility. The `body-md` (0.875rem) should be the workhorse for consultancy reports and student portals.
- **Labels (Inter):** Small, all-caps or high-tracking labels in `label-md` (0.75rem) using the `secondary` (#4a6077) color provide a technical, "organized" feel to the data.

---

## 4. Elevation & Depth
We eschew traditional structural lines for **Tonal Layering**.

- **The Layering Principle:** Depth is achieved by stacking the surface-container tiers. Placing a `surface_container_lowest` card on a `surface_container_low` background creates a natural "lift" that mimics high-end stationery.
- **Ambient Shadows:** When an element must float (e.g., a primary dropdown), use an extra-diffused shadow.
    - *Formula:* `0px 12px 32px rgba(25, 28, 29, 0.06)`. The shadow color is a tinted version of `on_surface` at a very low opacity to mimic natural ambient light.
- **The "Ghost Border" Fallback:** If a border is required for accessibility in input fields, use the `outline_variant` (#c4c6cd) at **15% opacity**. Never use 100% opaque, high-contrast borders.
- **Glassmorphism:** For top-level navigation, use `surface_container_lowest` with 80% opacity and a `backdrop-filter: blur(12px)`. This integrates the UI into the background, preventing it from feeling like a separate "plugin."

---

## 5. Components

### Buttons
- **Primary:** Background: `primary` (#041627); Text: `on_primary` (#ffffff). Shape: `lg` (0.5rem). Use a subtle gradient for depth.
- **Secondary:** Background: `transparent`; Border: Ghost Border (15% `outline_variant`); Text: `primary`.
- **Tertiary:** Text: `tertiary_fixed_dim` (#e9c176) with a `label-md` weight. No background.

### Cards & Lists
**Forbid the use of divider lines.**
- Use the `16` (5.5rem) spacing token to separate major content blocks.
- For list items, use a background shift to `surface_container_high` (#e7e8e9) on hover rather than a bottom-border.
- Content should be grouped by proximity, not by containment.

### Input Fields
- **State:** Unfocused inputs use `surface_container_highest` (#e1e3e4) with no border.
- **Focus:** Transition to a 1px `tertiary_fixed_dim` (#e9c176) border to signify the "Gold Standard" of service.

### Specialized Component: The "Insight Hero"
A signature component for this design system: A large-scale card using `primary_container` (#1a2b3c) with Noto Serif text in `tertiary_fixed_dim` (#e9c176). This component should use asymmetrical padding (e.g., `12` on the left, `24` on the right) to create a premium, "magazine" feel.

---

## 6. Do's and Don'ts

### Do:
- **Embrace White Space:** Use the `20` (7rem) and `24` (8.5rem) spacing tokens for top/bottom section padding.
- **Use Tonal Shifts:** Define layout areas by alternating between `surface` and `surface_container_low`.
- **Mix Type Weights:** Pair a `display-sm` (Noto Serif) headline with a `title-sm` (Inter) sub-label for a sophisticated hierarchy.

### Don't:
- **No Hard Borders:** Never use a 1px solid border to separate sections.
- **No Pure Black:** Always use `primary` (#041627) or `on_surface` (#191c1d) for text to maintain a soft, premium feel.
- **No Standard Grids:** Avoid perfectly symmetrical 3-column grids. Try a 2/3 vs 1/3 layout to create visual interest and an editorial "flow."
- **No Heavy Shadows:** If the shadow is clearly visible, it is too dark. It should be felt, not seen.
