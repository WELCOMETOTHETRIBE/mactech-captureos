import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["ui-sans-serif", "system-ui", "-apple-system", "Segoe UI", "sans-serif"]
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
