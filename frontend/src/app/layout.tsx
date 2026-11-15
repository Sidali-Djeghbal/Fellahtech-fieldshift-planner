import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./fonts.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "FELLAH TECH — Agricultural Intelligence & Crop Rotation Platform",
  description:
    "Trilingual farmer-friendly crop-rotation decision-support interface anchored to Wilaya of Guelma, Algeria.",
};

const THEME_INIT_SCRIPT = `(function(){try{var raw=localStorage.getItem("fieldshift-planner-v32");var pref="system";if(raw){var parsed=JSON.parse(raw);var candidate=parsed&&parsed.state&&parsed.state.theme;if(candidate==="light"||candidate==="dark"||candidate==="system"){pref=candidate;}}var isDark=pref==="dark"||(pref==="system"&&typeof window.matchMedia==="function"&&window.matchMedia("(prefers-color-scheme: dark)").matches);var resolved=isDark?"dark":"light";var root=document.documentElement;root.dataset.theme=resolved;root.classList.toggle("dark",isDark);root.style.colorScheme=resolved;}catch(e){}})();`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" dir="ltr" data-theme="light" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_INIT_SCRIPT }} />
      </head>
      <body className="font-sans antialiased selection:bg-[#22C55E]/25 selection:text-[#0B3D2E] dark:selection:bg-[#22C55E]/30 dark:selection:text-[#F5F7F5]">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
