import type { Metadata } from 'next'
import { DM_Sans, DM_Mono, Fraunces } from 'next/font/google'
import './globals.css'

const dmSans = DM_Sans({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
})

const fraunces = Fraunces({
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
  axes: ['SOFT', 'WONK'],
})

const dmMono = DM_Mono({
  subsets: ['latin'],
  variable: '--font-mono',
  weight: ['400', '500'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Groww Review Pulse',
  description: 'Weekly Play Store review insights for Groww — themes, quotes, action ideas.',
  icons: { icon: '/favicon.ico' },
}

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${dmSans.variable} ${fraunces.variable} ${dmMono.variable}`}>
      <body className="font-sans antialiased bg-[#0b0f1a] text-white min-h-screen">
        {children}
      </body>
    </html>
  )
}
