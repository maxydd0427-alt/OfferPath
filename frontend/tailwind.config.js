/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      boxShadow: {
        soft: "0 24px 80px rgba(24, 39, 75, 0.10)",
        card: "0 16px 50px rgba(26, 45, 69, 0.08)",
      },
      colors: {
        ink: "#17212b",
        mist: "#f5f7fb",
        pine: "#136f63",
        coral: "#e25f4d",
      },
    },
  },
  plugins: [],
};
