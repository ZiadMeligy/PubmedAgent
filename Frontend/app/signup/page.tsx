'use client';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/lib/store';
import Link from 'next/link';

export default function SignupPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const setToken = useAuthStore((s) => s.setToken);
  const router = useRouter();

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      const res = await fetch('http://localhost:8000/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, username, password })
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Signup failed');
      }
      const data = await res.json();
      setToken(data.token);
      router.push('/');
    } catch (err: any) {
      setError(err.message);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 text-white">
      <form onSubmit={handleSignup} className="bg-gray-800 p-8 rounded-lg w-96 shadow-xl border border-gray-700">
        <h2 className="text-3xl mb-6 font-bold text-center tracking-tight">Create Account</h2>
        {error && <div className="text-red-400 mb-4 bg-red-900/30 p-2 rounded">{error}</div>}
        <input 
          type="email" placeholder="Email" value={email} onChange={e => setEmail(e.target.value)} 
          className="w-full mb-4 p-3 rounded bg-gray-900 border border-gray-700 focus:border-blue-500 focus:outline-none transition-colors" required 
        />
        <input 
          type="text" placeholder="Username" value={username} onChange={e => setUsername(e.target.value)} 
          className="w-full mb-4 p-3 rounded bg-gray-900 border border-gray-700 focus:border-blue-500 focus:outline-none transition-colors" required 
        />
        <input 
          type="password" placeholder="Password" value={password} onChange={e => setPassword(e.target.value)} 
          className="w-full mb-6 p-3 rounded bg-gray-900 border border-gray-700 focus:border-blue-500 focus:outline-none transition-colors" required 
        />
        <button type="submit" className="w-full bg-blue-600 text-white font-semibold p-3 rounded hover:bg-blue-500 transition-colors">Sign Up</button>
        <p className="mt-6 text-center text-gray-400">
          Already have an account? <Link href="/login" className="text-blue-400 hover:text-blue-300">Log in</Link>
        </p>
      </form>
    </div>
  );
}
