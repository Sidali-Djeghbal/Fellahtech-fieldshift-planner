---
name: FieldShift Earth Observation
colors:
  surface: '#0c1511'
  surface-dim: '#0c1511'
  surface-bright: '#323b36'
  surface-container-lowest: '#07100c'
  surface-container-low: '#141d19'
  surface-container: '#131814'
  surface-container-high: '#1C241E'
  surface-container-highest: '#2d3732'
  on-surface: '#dbe5de'
  on-surface-variant: '#d3c4b0'
  inverse-surface: '#dbe5de'
  inverse-on-surface: '#29322e'
  outline: '#9c8f7d'
  outline-variant: '#4f4536'
  surface-tint: '#f5bd56'
  primary: '#ffd183'
  on-primary: '#422c00'
  primary-container: '#eab34d'
  on-primary-container: '#654600'
  inverse-primary: '#7d5700'
  secondary: '#78dc77'
  on-secondary: '#00390a'
  secondary-container: '#00761f'
  on-secondary-container: '#95fb92'
  tertiary: '#aadeff'
  on-tertiary: '#00354a'
  tertiary-container: '#56c7ff'
  on-tertiary-container: '#00516f'
  error: '#ffb4ab'
  on-error: '#690005'
  error-container: '#93000a'
  on-error-container: '#ffdad6'
  primary-fixed: '#ffdeaa'
  primary-fixed-dim: '#f5bd56'
  on-primary-fixed: '#271900'
  on-primary-fixed-variant: '#5f4100'
  secondary-fixed: '#94f990'
  secondary-fixed-dim: '#78dc77'
  on-secondary-fixed: '#002204'
  on-secondary-fixed-variant: '#005313'
  tertiary-fixed: '#c4e7ff'
  tertiary-fixed-dim: '#7bd0ff'
  on-tertiary-fixed: '#001e2c'
  on-tertiary-fixed-variant: '#004c69'
  background: '#0c1511'
  on-background: '#dbe5de'
  surface-variant: '#2d3732'
  surface-canvas: '#0B0F0C'
  surface-border: rgba(255, 255, 255, 0.08)
  foliage-green-bright: '#66BB6A'
  foliage-green-deep: '#4D5432'
  telemetry-cyan: '#38BDF8'
  erosion-alert: '#F97316'
  spectral-deep-sea: '#183A41'
  text-primary: '#F4F7F4'
  text-secondary: '#A3B3A7'
  text-tertiary: '#65776A'
typography:
  headline-lg:
    fontFamily: Space Grotesk
    fontSize: 32px
    fontWeight: '700'
    lineHeight: 40px
    letterSpacing: -0.02em
  headline-lg-mobile:
    fontFamily: Space Grotesk
    fontSize: 26px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  headline-md:
    fontFamily: Space Grotesk
    fontSize: 22px
    fontWeight: '600'
    lineHeight: 28px
  headline-sm:
    fontFamily: Space Grotesk
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-lg:
    fontFamily: Inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  label-lg:
    fontFamily: Space Mono
    fontSize: 13px
    fontWeight: '500'
    lineHeight: 16px
    letterSpacing: 0.02em
  label-md:
    fontFamily: Space Mono
    fontSize: 11px
    fontWeight: '500'
    lineHeight: 14px
    letterSpacing: 0.04em
  label-sm:
    fontFamily: Space Mono
    fontSize: 10px
    fontWeight: '400'
    lineHeight: 12px
    letterSpacing: 0.06em
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  gutter: 1rem
  gutter-mobile: 0.75rem
  margin: 1.25rem
  margin-mobile: 1rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 1rem
  space-lg: 1.5rem
  space-xl: 2rem
---

## Brand & Style

This design system is engineered for mission-critical agronomic fieldwork, precision machinery management, and orbital remote sensing synthesis. Built natively for Android Jetpack Compose and Material 3, the aesthetic balances orbital technical instrumentation with tactile earth grounding.

### Personality & Tone
- **Precision Agronomy:** Measured, technical, and data-dense without visual noise.
- **Rugged Resilience:** Tailored for dynamic outdoor lighting—from harsh midday field sunlight to night-cab machinery tracking—via rich high-contrast dark field surfaces.
- **Orbital Clarity:** Translates multispectral NDVI layers, telemetry streams, and moisture radar into glanceable agronomic insights.

### Design Movement
The interface operates on **Technical Neo-Brutalism softened by Atmospheric Depth**: deep obsidian-earthen slate foundations paired with razor-thin structural borders, precise Jetpack Compose surface containers, and glowing spectral accents derived directly from multi-band remote sensing imagery.

## Colors

The color palette translates satellite remote sensing wavelengths directly into actionable agricultural telemetry against deep, battery-conserving OLED dark substrates.

### Palette Architecture
- **Primary (`#EAB34D`):** Amber-Ochre harvest tone. Used for active states, harvest yield trajectories, primary FAB actions, and critical navigation targets.
- **Secondary (`#4CAF50` / `#66BB6A`):** Crop Foliage Green. Denotes healthy vegetative indexes (NDVI), canopy vigor, verified task completions, and active field operational bounds.
- **Tertiary (`#38BDF8`):** Radar Hydrology / Telemetry Cyan. Dedicated to soil volumetric water content, pivot irrigation statuses, satellite telemetry sync, and precipitation forecasts.
- **Alert / Degradation (`#F97316`):** Terracotta / Soil Erosion alert. Highlights moisture deficits, equipment drift, pest blight alerts, and mechanical geofence breaches.
- **Neutrals (`#0B0F0C` to `#1C241E`):** Obsidian-earthen baseline. Prevents field glare, delivers pure black efficiency on modern OLED displays, and establishes strict visual layers.

### Contrast & Usability
All essential interactive typography against `surface-canvas` or `surface-container` adheres strictly to WCAG AA/AAA standards (exceeding 4.5:1 for body copy and 3.0:1 for graphical accents).

## Typography

The typographic hierarchy distinguishes operational narratives from precise geospatial metrics.

- **Headlines (Space Grotesk):** Engineered display proportions that convey modern instrumentation without sacrificing compact readability on Android viewport widths.
- **Body & Instructional Copy (Inter):** Highly legible, neutral sans-serif optimized for variable outdoor screen glare, form inputs, and agronomic task schedules.
- **Data, Coordinates & Telemetry (Space Mono):** Used for GIS coordinates (lat/long), spectral index values (e.g., `NDVI: 0.78`), telemetry timestamps, machinery telemetry, and sensor status tags to guarantee tabular character alignment.

## Layout & Spacing

Layouts follow an 8dp structural grid, downscaled to 4dp micro-increments for compact telemetry readouts and sensor dashboards.

### Grid & Form Factors
- **Mobile (Compact, &lt;600dp):** Single column fluid canvas with `16dp` outer canvas margins and `12dp` item gutters. Persistent bottom navigation bar anchored to window insets.
- **Field Tablet (Medium/Expanded, 600dp - 1240dp):** Two-pane layout with persistent machinery / plot list on the left (360dp fixed) and GIS multispectral map canvas filling the remaining fluid container. Margins step up to `24dp` with `16dp` gutters.
- **Machinery Mount / Rugged In-Cab (&gt;1240dp):** Modular dashboard cards snapping across a 12-column grid system allowing dual telemetry monitoring and task switching simultaneously.

## Elevation & Depth

Rather than relying on heavy, muddy drop shadows that wash out under sunlight, visual hierarchy in this dark agronomic system is expressed through **Tonal Surface Tiers** combined with **Inner Atmospheric Ring Outlines**.

1. **Canvas Level (0dp):** Deep Obsidian (`#0B0F0C`) acts as the base map underlay and screen foundation.
2. **Container Level 1 (Card & Module Baselines):** Earthen Charcoal (`#131814`) with a stroke border of `1dp` solid `rgba(255, 255, 255, 0.08)`.
3. **Container Level 2 (Active Toolbars, Selected Card, Dialogs):** Raised Earth (`#1C241E`) with a stroke border of `1dp` solid `rgba(234, 179, 77, 0.25)` or `rgba(255, 255, 255, 0.12)`.
4. **Spectral Glow Accents:** Interactive active states (e.g., active pivot or selected field polygon) use a subtle colored outer bleed: `0px 0px 12px rgba(234, 179, 77, 0.20)`.

## Shapes

The design system adopts a balanced **Rounded (`roundedness: 2`)** geometry to blend modern consumer software ergonomics with durable technical hardware enclosures.

- **Base Cards & Field Panes:** `8dp` (`rounded-md`) to ensure sharp structural containment of complex data matrices.
- **Interactive Badges & Agronomic Stat Chips:** Full pill radius (`9999dp` / `rounded-full`) to immediately communicate touch affordances across touch gloves and in-motion handling.
- **Action Buttons & Inputs:** `8dp` to maintain alignment with card margins and container edges.
- **Modal Sheets & Overlays:** Top corner radius of `16dp` (`rounded-lg`).

## Components

### Buttons
- **Primary Filled Button:** Container in Amber-Ochre (`#EAB34D`), content in Deep Canvas (`#0B0F0C`) with bold weight (`Space Grotesk`, 14sp). Minimum touch target height of 48dp.
- **Secondary Outlined Button:** Transparent fill with `1dp` border (`rgba(255, 255, 255, 0.16)`), content in `#F4F7F4`. Pressed state illuminates to `rgba(234, 179, 77, 0.12)`.
- **Tonal Sensor Trigger:** Container `#1C241E`, leading icon tinted in Foliage Green (`#66BB6A`) or Telemetry Cyan (`#38BDF8`), text in `#F4F7F4`.

### Field & Status Chips (Jetpack Compose Material 3)
- **NDVI / Crop Status Chip:** Pill container with 32dp height. Background `#131814` with a dynamic 1dp border matching health status: Foliage Green for nominal vegetative index, Ochre for harvest ready, Terracotta for moisture deficit.
- **Filter Chips:** Pill shape with muted inactive border (`rgba(255, 255, 255, 0.08)`). When selected, container fills with `rgba(234, 179, 77, 0.15)` with amber borders and check indicator.

### Telemetry Cards
- Surface: `#131814` with internal `1dp` border in `rgba(255, 255, 255, 0.08)`.
- Header houses the coordinate or parcel identifier in `label-sm` (`Space Mono`) with `#A3B3A7` text color.
- Body displays large metric typography (`headline-md`) coupled with the respective spectral accent (e.g., `#38BDF8` for 18.4% soil moisture).

### Input Fields
- Filled container style using `#1C241E`. Bottom active indicator line in `#EAB34D`.
- Floating label rendered in `body-sm` (`Inter`).
- Input text rendered in `#F4F7F4`, placeholder text in `#65776A`.

### Bottom Navigation Bar
- Anchored to bottom with background `#0B0F0C` elevated via a top divider of `1dp` solid `rgba(255, 255, 255, 0.06)`.
- Active item indicator: Horizontal pill capsule in `rgba(234, 179, 77, 0.18)` containing the active icon colored in `#EAB34D`.
- Inactive items rendered in `#65776A` with typography in `label-sm`.

### Monospaced Coordinate Badges
- Compact rectangular badges with `4dp` corner radius.
- Background: `#0E1713` with `1dp` border in `rgba(56, 189, 248, 0.3)`.
- Typography: `Space Mono` 11sp in `#38BDF8` displaying GPS format: `41°24'12.2"N 93°36'44.8"W`.