// SATS tokens (vendored, unchanged) plus the shadcn/ui colour names, which read the CSS
// variables set by src/styles/sats/shadcn-theme.css.
const sats = require("./src/styles/sats/tailwind.sats.cjs");

const shadcn = (name) => `hsl(var(--${name}) / <alpha-value>)`;

/** @type {import('tailwindcss').Config} */
module.exports = {
  ...sats,
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    ...sats.theme,
    extend: {
      ...sats.theme.extend,
      colors: {
        ...sats.theme.extend.colors,
        background: shadcn("background"),
        foreground: shadcn("foreground"),
        card: { DEFAULT: shadcn("card"), foreground: shadcn("card-foreground") },
        popover: { DEFAULT: shadcn("popover"), foreground: shadcn("popover-foreground") },
        primary: { DEFAULT: shadcn("primary"), foreground: shadcn("primary-foreground") },
        secondary: { DEFAULT: shadcn("secondary"), foreground: shadcn("secondary-foreground") },
        muted: { DEFAULT: shadcn("muted"), foreground: shadcn("muted-foreground") },
        accent: { DEFAULT: shadcn("accent"), foreground: shadcn("accent-foreground") },
        destructive: { DEFAULT: shadcn("destructive"), foreground: shadcn("destructive-foreground") },
        border: shadcn("border"),
        input: shadcn("input"),
        ring: shadcn("ring"),
      },
      // The vendored config still lists Segoe UI first; the package's CSS has since moved
      // to self-hosted Inter, so follow the CSS variables.
      fontFamily: {
        sans: ["var(--font-family-base)"],
        mono: ["var(--font-family-mono)"],
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};
