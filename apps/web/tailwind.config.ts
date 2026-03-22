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
  plugins: [],
};

export default config;
