import type { Metadata } from "next";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "FieldShift — Agricultural Intelligence & Crop Rotation Platform",
  description:
    "Trilingual farmer-friendly crop-rotation decision-support interface anchored to Wilaya of Guelma, Algeria.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" dir="ltr">
      <body className="font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
