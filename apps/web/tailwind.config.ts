import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        // Editorial serif for page titles + section openers. System fonts
        // only — no Google Fonts hit, no FOUT — and they all read as
        // "serious but warm" on macOS/iOS/Windows. Used selectively, not
        // for body copy.
        serif: [
          "Iowan Old Style",
          "Palatino Linotype",
          "Palatino",
          "Hoefler Text",
          "Georgia",
          "serif"
        ]
      },
      colors: {
        // Brand teal — federal/GSA-adjacent, distinct from generic tech blue.
        // Used for primary actions, active nav, score >=80, focus rings.
        brand: {
          50: "#effaf9",
          100: "#d6f1ee",
          200: "#aee2dd",
          300: "#7bcdc7",
          400: "#48b3ac",
          500: "#2a9892",
          600: "#207b78",
          700: "#1c6362",
          800: "#1a504f",
          900: "#0d3d3d",
          950: "#062626"
        },
        // Warm-paper neutrals — replaces the cold neutral-50/white default.
        // The 50/100 tints are subtle: enough off-white that the eye reads
        // "warm document" instead of "blank screen". Cards stay white on
        // top so they lift slightly. Uses include page background, sidebar
        // borders, and section dividers.
        paper: {
          50: "#faf9f5",
          100: "#f3f1ea",
          200: "#e9e5d9",
          300: "#d4ccba",
          400: "#a89d85",
          500: "#7a6e54",
          900: "#1c1815"
        }
      },
      ringColor: {
        DEFAULT: "#207b78"
      }
    }
  },
  plugins: []
};

export default config;
