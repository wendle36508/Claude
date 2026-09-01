import type { Metadata } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata: Metadata = {
  title: "Thrift Bins",
  description: "Find fresh bin drops at outlet thrift stores near you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900">
        <header className="border-b bg-white">
          <div className="mx-auto max-w-5xl px-4 py-3">
            <a href="/" className="text-lg font-semibold">
              🗑️ Thrift Bins
            </a>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
