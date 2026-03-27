import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/features/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          50: "#f0faf4",
          100: "#d4eddf",
          200: "#a9dcbf",
          300: "#6ec49a",
          400: "#3dab7a",
          500: "#1e8c5e",
          600: "#17724c",
          700: "#115a3c",
          800: "#0b422b",
          900: "#062b1b",
        },
        // kept for any legacy references
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
  safelist: [
    {
      // Ensure forest color utilities are generated even when only referenced
      // via @apply in globals.css (not scanned as content files by Tailwind JIT).
      pattern: /^(bg|text|border|ring|fill|stroke)-forest-\d+$/,
      variants: ["hover", "focus", "active", "disabled"],
    },
  ],
  plugins: [],
};

export default config;
