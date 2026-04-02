import themeTokens from "../../design-reference/stitch-ai-consultation-8777623071946293026/theme-tokens.json";

const nc = themeTokens.namedColors;
const th = themeTokens.theme;

/** Semantic Stitch / Material tokens (single source: theme-tokens.json). */
export const stitchSemantic = nc;

/** Tailwind `brand` scale: each step is a namedColors value (light → dark). */
export const stitchBrand = {
  50: nc.inverse_on_surface,
  100: nc.primary_fixed,
  200: nc.primary_fixed_dim,
  300: nc.on_primary_container,
  400: nc.surface_tint,
  500: nc.secondary,
  600: nc.on_primary_fixed_variant,
  700: nc.on_secondary_fixed_variant,
  800: nc.primary_container,
  900: nc.primary,
} as const;

export const stitchSurface = {
  DEFAULT: nc.surface,
  low: nc.surface_container_low,
  container: nc.surface_container,
  high: nc.surface_container_high,
  highest: nc.surface_container_highest,
  bright: nc.surface_bright,
  dim: nc.surface_dim,
  card: nc.surface_container_lowest,
} as const;

export const stitchAccent = {
  DEFAULT: nc.tertiary_fixed_dim,
  muted: th.overrideTertiaryColor,
} as const;

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const h = hex.replace("#", "");
  const n = parseInt(h.length === 3 ? h.split("").map((c) => c + c).join("") : h, 16);
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

/** Ambient shadow from design-system-spec (tinted `on_surface`). */
export function stitchAmbientShadow(): string {
  const { r, g, b } = hexToRgb(nc.on_surface);
  return `0px 12px 32px rgba(${r}, ${g}, ${b}, 0.06)`;
}
