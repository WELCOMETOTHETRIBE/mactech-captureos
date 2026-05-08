import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Cross-suite "gold copy" token contract — every color reads from a
      // CSS variable defined in app/globals.css. This is what makes the same
      // shadcn-shape primitive theme cleanly between MacTech apps. Legacy
      // `paper.*` and `brand.*` scales are preserved below as aliases so we
      // don't have to migrate every existing class in this PR.
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)"
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
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
        // Token-driven utilities. Use these on new code:
        //   bg-background, text-foreground, bg-card, text-card-foreground,
        //   bg-primary text-primary-foreground, bg-secondary, bg-muted,
        //   text-muted-foreground, bg-accent, text-accent-foreground,
        //   bg-destructive, bg-success, bg-warning, border-border,
        //   border-input, ring-ring.
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))"
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))"
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))"
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))"
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))"
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))"
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))"
        },
        success: "hsl(var(--success))",
        warning: "hsl(var(--warning))",
        // Pillar tokens for the four MacTech pillars. Kept flat (no
        // foreground pair) because the Pillar chip uses a soft tint
        // (color/15 background, color/90 text) instead of a solid fill.
        pillar: {
          security: "hsl(var(--pillar-security))",
          infrastructure: "hsl(var(--pillar-infrastructure))",
          quality: "hsl(var(--pillar-quality))",
          governance: "hsl(var(--pillar-governance))"
        },
        // ─── Legacy aliases — DO NOT EXTEND ─────────────────────────────
        // These keep the ~100 existing `bg-paper-*` / `text-brand-*` /
        // `border-paper-*` classes compiling without a stop-the-world
        // migration. New code should reach for the token utilities above
        // (`bg-secondary`, `text-primary`, `border-border`, etc.).
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
        // Default focus-ring color tracks the --ring token, which currently
        // resolves to brand-teal #207b78. Components that opt into
        // ring-ring also use it explicitly.
        DEFAULT: "hsl(var(--ring))"
      }
    }
  },
  plugins: []
};

export default config;
