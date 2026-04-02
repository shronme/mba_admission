import type { Config } from "tailwindcss";
import {
  stitchAccent,
  stitchAmbientShadow,
  stitchBrand,
  stitchSemantic,
  stitchSurface,
} from "./src/design/stitch-theme";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "system-ui", "sans-serif"],
        serif: ["var(--font-noto-serif)", "Noto Serif", "Georgia", "serif"],
      },
      boxShadow: {
        ambient: stitchAmbientShadow(),
      },
      colors: {
        brand: { ...stitchBrand },
        surface: { ...stitchSurface },
        accent: { ...stitchAccent },
        on: {
          surface: stitchSemantic.on_surface,
        },
        cream: {
          50: "#fdf8f0",
          100: "#f5ecd8",
          200: "#e8d8b8",
          300: "#d9c296",
        },
        gold: {
          50: "#fdf3d8",
          100: "#f9e8b0",
          200: "#f0d070",
          400: "#d4a843",
          500: "#c49a2c",
          600: "#a07e23",
          700: "#7d621b",
        },
      },
    },
  },
  // Base utilities must be safelisted: @apply in globals.css is not scanned as class strings.
  // Do not attach `variants` here only — that skips the unprefixed utilities @apply needs.
  safelist: [
    {
      pattern:
        /^(bg|text|border|ring|fill|stroke)-(brand-\d+|accent(-muted)?|surface(-[a-z]+)?|on-surface)$/,
    },
    {
      pattern:
        /^(bg|text|border|ring|fill|stroke)-(brand-\d+|accent(-muted)?|surface(-[a-z]+)?|on-surface)$/,
      variants: ["hover", "focus", "active", "disabled", "file"],
    },
  ],
  plugins: [],
};

export default config;
