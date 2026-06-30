"use client";

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { useAuthStore, UserProfile } from '@/lib/store';

interface AuthContextType {
  user: UserProfile | null;
  loading: boolean;
  signOut: () => Promise<void>;
  isConfigured: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const token = useAuthStore((s) => s.token);
  const user = useAuthStore((s) => s.user);
  const setUser = useAuthStore((s) => s.setUser);
  const logout = useAuthStore((s) => s.logout);
  const [loading, setLoading] = useState(true);
  const [isHydrated, setIsHydrated] = useState(false);

  const isConfigured = true;

  useEffect(() => {
    setIsHydrated(true);
  }, []);

  useEffect(() => {
    const fetchUser = async () => {
      if (!isHydrated) return; // Wait for hydration
      
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const res = await fetch(process.env.NEXT_PUBLIC_API_URL ? `${process.env.NEXT_PUBLIC_API_URL}/auth/me` : 'http://localhost:8000/auth/me', {
          headers: { Authorization: `Bearer ${token}` }
        });
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else {
          logout();
        }
      } catch (err) {
        console.error('Failed to fetch user', err);
      } finally {
        setLoading(false);
      }
    };
    fetchUser();
  }, [isHydrated, token, setUser, logout]);

  const signOut = async () => {
    logout();
  };

  return (
    <AuthContext.Provider value={{ user, loading, signOut, isConfigured }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
