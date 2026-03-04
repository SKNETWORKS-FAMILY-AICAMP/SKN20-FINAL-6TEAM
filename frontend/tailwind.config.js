/** @type {import('tailwindcss').Config} */
const withMT = require("@material-tailwind/react/utils/withMT");
const defaultTheme = require("tailwindcss/defaultTheme");

const shiftedFontSize = {
  xs: ['0.6875rem', { lineHeight: '1rem' }],
  sm: defaultTheme.fontSize.xs,
  base: defaultTheme.fontSize.sm,
  lg: defaultTheme.fontSize.base,
  xl: defaultTheme.fontSize.lg,
  '2xl': defaultTheme.fontSize.xl,
  '3xl': defaultTheme.fontSize['2xl'],
  '4xl': defaultTheme.fontSize['3xl'],
  '5xl': defaultTheme.fontSize['4xl'],
  '6xl': defaultTheme.fontSize['5xl'],
  '7xl': defaultTheme.fontSize['6xl'],
  '8xl': defaultTheme.fontSize['7xl'],
  '9xl': defaultTheme.fontSize['8xl'],
};

export default withMT({
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Nanum Gothic"', ...defaultTheme.fontFamily.sans],
      },
      fontSize: shiftedFontSize,
    },
  },
  plugins: [],
});
