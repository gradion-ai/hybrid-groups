import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "./contexts/AuthContext";
import Sidebar from "./components/Sidebar";
import AuthGuard from "./components/AuthGuard";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Hybrid Groups",
  description: "Hybrid Groups Web App",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark" data-theme="dark">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
      <AuthProvider>
          <AuthGuard>
            <div className="flex h-screen bg-gray-100 dark:bg-gray-900">
              <Sidebar />
              <main className="flex-1 p-6 sm:p-8 overflow-y-auto">
                {children}
              </main>
            </div>
          </AuthGuard>
      </AuthProvider>
      </body>
    </html>
  );
}
