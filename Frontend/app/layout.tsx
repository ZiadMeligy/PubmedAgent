import './globals.css';
import type { Metadata } from 'next';
import { Inter } from 'next/font/google';
import { ThemeProvider } from '@/components/ThemeProvider';
import { AuthProvider } from '@/hooks/useAuth';

const inter = Inter({ subsets: ['latin'] });

export const metadata: Metadata = {
  title: 'BioMed Assistant | Biomedical Literature Search',
  description: 'AI-powered assistant for searching PubMed papers and answering questions about biomedical literature.',
  openGraph: {
    title: 'BioMed Assistant',
    description: 'AI-powered assistant for searching PubMed papers and answering questions about biomedical literature.',
    type: 'website',
  },
  twitter: {
    card: 'summary_large_image',
    title: 'BioMed Assistant',
    description: 'AI-powered assistant for searching PubMed papers and answering questions about biomedical literature.',
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={inter.className}>
        <ThemeProvider
          attribute="class"
          defaultTheme="system"
          enableSystem
          disableTransitionOnChange
        >
          <AuthProvider>
            {children}
          </AuthProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
