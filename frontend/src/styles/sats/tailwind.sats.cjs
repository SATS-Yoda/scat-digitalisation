/**
 * SATS Enterprise Design System — Tailwind CSS v3 Theme
 *
 * Usage:
 *   1. Copy or import this file as your tailwind.config.js (or merge into an existing one).
 *   2. Make sure colors_and_type.css is loaded globally in your app so the
 *      CSS custom properties are available.
 *   3. Dark mode is driven by [data-theme="dark"] on the <html> element —
 *      add `dark:` variants to override surface / text / border utilities.
 *
 * Primitive tokens (brand, neutral, status, viz) are hardcoded hex values.
 * Semantic tokens (surface, text, border) reference CSS custom properties so
 * they update automatically when [data-theme="dark"] is applied.
 *
 * @type {import('tailwindcss').Config}
 */
module.exports = {
  content: ["./**/*.{html,js,jsx,ts,tsx}"],

  // Dark mode: toggle by setting data-theme="dark" on <html>
  darkMode: ["selector", '[data-theme="dark"]'],

  theme: {
    extend: {

      // ─── Colors ──────────────────────────────────────────────────────
      colors: {

        // -- Brand (hardcoded primitives) --------------------------------
        brand: {
          primary:          "#EE2536",  // Reserved: primary CTA, active nav, wordmark
          "primary-dark":   "#CF0928",  // Hover / pressed state of brand-primary
          secondary:        "#1F5575",  // Operational blue: KPIs, links, chart anchor
          "secondary-light":"#2D85AA",  // Hover state on secondary-blue surfaces
        },

        // -- Neutrals (hardcoded primitives) -----------------------------
        neutral: {
          0:   "#FFFFFF",
          100: "#F5F5F5",
          200: "#E6E6E6",
          300: "#D5D7D7",
          500: "#777777",
          700: "#4F2A4E",
          800: "#2A2A2A",
          900: "#1A1A1A",
        },

        // -- Status (hardcoded) ------------------------------------------
        status: {
          info:    "#30A9CE",
          success: "#418E3D",
          warning: "#FFA62B",
          error:   "#EF4444",
        },

        // -- Data viz — light (hardcoded) --------------------------------
        viz: {
          orange: "#FFA62B",
          sky:    "#30A9CE",
          yellow: "#FFDD15",
          green:  "#418E3D",
          blue:   "#1F5575",
          mint:   "#4FC6B7",
          // Dark variants (prefix with dark- for explicit use)
          "dark-orange": "#FFBC5C",
          "dark-sky":    "#5EC7E5",
          "dark-yellow": "#FFE65C",
          "dark-green":  "#5FBF5A",
          "dark-blue":   "#4A9FD1",
          "dark-mint":   "#74D9CD",
        },

        // -- Semantic: Surface (CSS-var-backed — theme-aware) ------------
        // Apply with: bg-surface-primary, bg-surface-secondary, etc.
        surface: {
          primary:   "var(--surface-primary)",
          secondary: "var(--surface-secondary)",
          tertiary:  "var(--surface-tertiary)",
          hover:     "var(--surface-hover)",
          disabled:  "var(--surface-disabled)",
        },

        // -- Semantic: Text (CSS-var-backed) -----------------------------
        // Apply with: text-content-primary, text-content-muted, etc.
        content: {
          primary:   "var(--text-primary)",
          secondary: "var(--text-secondary)",
          muted:     "var(--text-muted)",
          disabled:  "var(--text-disabled)",
          inverse:   "var(--text-inverse)",
        },

        // -- Semantic: Border (CSS-var-backed) ---------------------------
        // Apply with: border-edge-default, border-edge-focus, etc.
        edge: {
          default: "var(--border-default)",
          subtle:  "var(--border-subtle)",
          focus:   "var(--border-focus)",
          error:   "var(--border-error)",
        },
      },

      // ─── Typography ──────────────────────────────────────────────────
      fontFamily: {
        sans: ['"Segoe UI"', "Roboto", "Arial", "Helvetica", "sans-serif"],
        mono: [
          "ui-monospace",
          '"Cascadia Mono"',
          '"Segoe UI Mono"',
          "Menlo",
          "Consolas",
          "monospace",
        ],
      },

      fontSize: {
        // SATS type scale — maps to --font-size-* tokens
        xs:   ["12px", { lineHeight: "1.4"  }],  // caption
        sm:   ["14px", { lineHeight: "1.45" }],  // body-sm, table
        md:   ["16px", { lineHeight: "1.5"  }],  // body (default)
        lg:   ["18px", { lineHeight: "1.5"  }],  // body-lg
        xl:   ["20px", { lineHeight: "1.35" }],  // subtitle
        "2xl":["24px", { lineHeight: "1.3"  }],  // title
        "3xl":["32px", { lineHeight: "1.2"  }],  // headline
        "4xl":["40px", { lineHeight: "1.15" }],  // display-lg
        "5xl":["48px", { lineHeight: "1.1"  }],  // display-xl
      },

      fontWeight: {
        regular:  "400",
        medium:   "500",
        semibold: "600",
        bold:     "700",
      },

      // ─── Spacing ─────────────────────────────────────────────────────
      // SATS named spacing scale — use alongside Tailwind's default numeric scale
      spacing: {
        hair:    "1px",
        xxs:     "4px",
        xs:      "8px",
        sm:      "12px",
        md:      "16px",
        lg:      "24px",
        xl:      "32px",
        xxl:     "48px",
        "2xxl":  "64px",
        section: "96px",
      },

      // ─── Border radius ───────────────────────────────────────────────
      borderRadius: {
        xs:   "4px",
        sm:   "6px",
        md:   "8px",
        lg:   "12px",
        xl:   "16px",
        xxl:  "24px",
        full: "9999px",
      },

      // ─── Box shadow (elevation) ───────────────────────────────────────
      boxShadow: {
        "elevation-0": "none",
        "elevation-1": "0 2px 6px rgba(0,0,0,0.06)",
        "elevation-2": "0 4px 12px rgba(0,0,0,0.10)",
        "elevation-3": "0 8px 24px rgba(0,0,0,0.14)",
        "elevation-overlay": "0 12px 32px rgba(0,0,0,0.20)",
        // Dark theme elevations (more opaque)
        "elevation-1-dark": "0 2px 6px rgba(0,0,0,0.40)",
        "elevation-2-dark": "0 4px 12px rgba(0,0,0,0.50)",
        "elevation-3-dark": "0 8px 24px rgba(0,0,0,0.60)",
        "elevation-overlay-dark": "0 12px 32px rgba(0,0,0,0.70)",
      },

      // ─── Layout ──────────────────────────────────────────────────────
      maxWidth: {
        desktop: "1440px",
        content: "1280px",
      },

      width: {
        sidebar: "260px",
      },

      height: {
        topbar: "64px",
      },
    },
  },

  plugins: [],
};
