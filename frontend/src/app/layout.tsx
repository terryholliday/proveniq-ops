
import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "PROVENIQ OPS",
  description: "Operational Execution Engine",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`antialiased bg-gray-900 text-slate-100`}
      >
        {children}
      </body>
    </html>
  );
}
