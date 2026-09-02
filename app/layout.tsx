import type { Metadata } from "next";
import "./globals.css";
import "leaflet/dist/leaflet.css";

export const metadata: Metadata = {
  title: "BinBuddy",
  description: "Find fresh bin drops at outlet thrift stores near you.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="bg-gray-50 text-gray-900">
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <a href="/" className="text-lg font-semibold">
              🗑️ BinBuddy
            </a>
            <nav className="flex gap-4 text-sm font-medium text-gray-600">
              <a href="/" className="hover:text-gray-900">
                Locations
              </a>
              <a href="/hauls" className="hover:text-gray-900">
                Hauls
              </a>
              <a href="/market" className="hover:text-gray-900">
                Market
              </a>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
