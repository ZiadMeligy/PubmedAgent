"use client";

import { useAuth } from '@/hooks/useAuth';
import { useTheme } from 'next-themes';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { ArrowLeft, LogOut, Moon, Sun, User, Mail, Calendar, Shield, Bell, Database, AlertCircle, Sliders } from 'lucide-react';
import Link from 'next/link';
import { useState, useEffect } from 'react';
import { useAuthStore } from '@/lib/store';

export default function SettingsPage() {
  const { user, loading, signOut, isConfigured } = useAuth();
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [notifications, setNotifications] = useState(true);
  const [dataSharing, setDataSharing] = useState(false);
  
  const token = useAuthStore((s) => s.token);
  const [alpha, setAlpha] = useState(0.8);
  const [beta, setBeta] = useState(0.1);
  const [gamma, setGamma] = useState(0.1);
  const [journalQualityEnabled, setJournalQualityEnabled] = useState(false);
  const [minimumSjr, setMinimumSjr] = useState(10.0);
  const [settingsSaved, setSettingsSaved] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (token) {
      fetch('http://localhost:8000/settings', {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(r => r.json())
      .then(d => {
        if (d.alpha !== undefined) {
          setAlpha(d.alpha);
          setBeta(d.beta);
          setGamma(d.gamma);
          if (d.journal_quality_enabled !== undefined) {
            setJournalQualityEnabled(d.journal_quality_enabled);
            setMinimumSjr(d.minimum_sjr);
          }
        }
      });
    }
  }, [token]);

  const saveRetrievalSettings = async () => {
    if (!token) return;
    try {
      const res = await fetch('http://localhost:8000/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({ 
          alpha, beta, gamma,
          journal_quality_enabled: journalQualityEnabled,
          minimum_sjr: minimumSjr
        })
      });
      if (res.ok) {
        setSettingsSaved(true);
        setTimeout(() => setSettingsSaved(false), 3000);
      }
    } catch (e) {
      console.error(e);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-pulse text-muted-foreground">Loading...</div>
      </div>
    );
  }

  const handleSignOut = async () => {
    await signOut();
    window.location.href = '/';
  };

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    });
  };

  // Show auth not configured message
  if (!isConfigured) {
    return (
      <div className="min-h-screen bg-background">
        <header className="border-b">
          <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
            <Link href="/">
              <Button variant="ghost" size="icon">
                <ArrowLeft className="h-5 w-5" />
              </Button>
            </Link>
            <h1 className="text-xl font-semibold">Settings</h1>
          </div>
        </header>

        <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex items-center gap-3">
                <div className="h-14 w-14 rounded-full bg-muted flex items-center justify-center">
                  <User className="h-7 w-7 text-muted-foreground" />
                </div>
                <div>
                  <CardTitle>Guest User</CardTitle>
                  <CardDescription>Authentication not configured</CardDescription>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              <div className="flex items-start gap-3 p-4 rounded-lg bg-muted/50">
                <AlertCircle className="h-5 w-5 text-muted-foreground flex-shrink-0 mt-0.5" />
                <p className="text-sm text-muted-foreground">
                  Authentication is not configured for this application. Your conversation history is stored locally in your browser.
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Appearance Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">Appearance</CardTitle>
              <CardDescription>Customize how the app looks</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  {(!mounted || resolvedTheme === 'dark') ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
                  <div>
                    <Label htmlFor="theme-toggle">Dark Mode</Label>
                    <p className="text-sm text-muted-foreground">
                      Toggle between light and dark themes
                    </p>
                  </div>
                </div>
                {mounted && (
                  <Switch
                    id="theme-toggle"
                    checked={resolvedTheme === 'dark'}
                    onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                  />
                )}
              </div>
            </CardContent>
          </Card>

          {/* Data & Privacy Settings */}
          <Card>
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <Database className="h-5 w-5" />
                Data & Privacy
              </CardTitle>
              <CardDescription>Manage your data and privacy settings</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-3">
                <Label>Conversation History</Label>
                <p className="text-sm text-muted-foreground">
                  Your conversations are stored locally in your browser. Clear your browser data to remove them.
                </p>
                <Button variant="outline" className="w-full sm:w-auto">
                  Clear All Conversations
                </Button>
              </div>
            </CardContent>
          </Card>
        </main>
      </div>
    );
  }

  // Auth configured - show full profile
  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b">
        <div className="max-w-4xl mx-auto px-4 py-4 flex items-center gap-4">
          <Link href="/">
            <Button variant="ghost" size="icon">
              <ArrowLeft className="h-5 w-5" />
            </Button>
          </Link>
          <h1 className="text-xl font-semibold">Settings</h1>
        </div>
      </header>

      <main className="max-w-4xl mx-auto px-4 py-8 space-y-6">
        {/* User Profile Section */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 rounded-full bg-primary flex items-center justify-center">
                <User className="h-7 w-7 text-primary-foreground" />
              </div>
              <div>
                <CardTitle>
                  {user?.username || user?.email?.split('@')[0] || 'User'}
                </CardTitle>
                <CardDescription className="flex items-center gap-1 mt-1">
                  <Mail className="h-3 w-3" />
                  {user?.email || 'No email provided'}
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-4 text-sm">
              <div className="flex items-center gap-3 text-muted-foreground">
                <Calendar className="h-4 w-4" />
                <span>Member since {formatDate(new Date().toISOString())}</span>
              </div>
              <div className="flex items-center gap-3 text-muted-foreground">
                <Shield className="h-4 w-4" />
                <span>Active Session</span>
              </div>
            </div>
            <Separator className="my-4" />
            <Button variant="destructive" onClick={handleSignOut} className="w-full sm:w-auto">
              <LogOut className="h-4 w-4 mr-2" />
              Sign Out
            </Button>
          </CardContent>
        </Card>

        {/* Retrieval Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Sliders className="h-5 w-5" />
              Retrieval Preferences
            </CardTitle>
            <CardDescription>Adjust the weights for hierarchical retrieval. The total sum is exactly 1.0.</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            
            {/* Total Remaining Meter */}
            <div className="space-y-2">
              <div className="flex justify-between text-sm">
                <span className="font-medium">Total Allocation</span>
                <span className={((alpha + beta + gamma) < 0.99) ? 'text-primary font-bold' : 'text-muted-foreground'}>
                  {((alpha + beta + gamma) * 100).toFixed(0)}% Used
                </span>
              </div>
              <div className="h-2 w-full bg-muted rounded-full overflow-hidden flex">
                <div className="h-full bg-blue-500 transition-all duration-300" style={{ width: `${alpha * 100}%` }} title="Semantic" />
                <div className="h-full bg-green-500 transition-all duration-300" style={{ width: `${beta * 100}%` }} title="Recency" />
                <div className="h-full bg-purple-500 transition-all duration-300" style={{ width: `${gamma * 100}%` }} title="Citations" />
              </div>
              {((alpha + beta + gamma) < 0.99) && (
                <p className="text-xs text-primary text-right animate-pulse">
                  {(1.0 - (alpha + beta + gamma)).toFixed(2)} remaining to unlock
                </p>
              )}
            </div>

            <div className="space-y-4">
              <div>
                <Label className="flex justify-between">
                  <span>Semantic Similarity (Alpha)</span>
                  <span className="text-blue-500 font-mono">{alpha.toFixed(2)}</span>
                </Label>
                <input 
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.05" 
                  value={alpha} 
                  onChange={e => {
                    const val = parseFloat(e.target.value);
                    const maxAllowed = 1.0 - beta - gamma;
                    setAlpha(Math.min(val, maxAllowed));
                  }} 
                  className="w-full mt-2 accent-blue-500" 
                />
              </div>
              <div>
                <Label className="flex justify-between">
                  <span>Recency (Beta)</span>
                  <span className="text-green-500 font-mono">{beta.toFixed(2)}</span>
                </Label>
                <input 
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.05" 
                  value={beta} 
                  onChange={e => {
                    const val = parseFloat(e.target.value);
                    const maxAllowed = 1.0 - alpha - gamma;
                    setBeta(Math.min(val, maxAllowed));
                  }} 
                  className="w-full mt-2 accent-green-500" 
                />
              </div>
              <div>
                <Label className="flex justify-between">
                  <span>Citation Impact (Gamma)</span>
                  <span className="text-purple-500 font-mono">{gamma.toFixed(2)}</span>
                </Label>
                <input 
                  type="range" 
                  min="0" 
                  max="1" 
                  step="0.05" 
                  value={gamma} 
                  onChange={e => {
                    const val = parseFloat(e.target.value);
                    const maxAllowed = 1.0 - alpha - beta;
                    setGamma(Math.min(val, maxAllowed));
                  }} 
                  className="w-full mt-2 accent-purple-500" 
                />
              </div>
            </div>

            <div className="flex justify-end pt-2">
              <Button onClick={saveRetrievalSettings} disabled={(alpha + beta + gamma) < 0.99}>
                {settingsSaved ? 'Saved!' : 'Save Weights'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Journal Quality Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Shield className="h-5 w-5" />
              Journal Quality
            </CardTitle>
            <CardDescription>Filter papers based on SCImago Journal Rank (SJR)</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="journal-quality-toggle">Journal Quality Mode</Label>
                <p className="text-sm text-muted-foreground">
                  When enabled, excludes papers from journals below a minimum SJR score.
                </p>
              </div>
              <Switch
                id="journal-quality-toggle"
                checked={journalQualityEnabled}
                onCheckedChange={setJournalQualityEnabled}
              />
            </div>
            
            {journalQualityEnabled && (
              <>
                <Separator />
                <div className="space-y-3">
                  <Label>Minimum SJR</Label>
                  <select 
                    className="w-full sm:w-auto p-2 rounded-md border border-input bg-background ml-2"
                    value={
                      [15, 10, 7, 5, 3, 2, 1].includes(minimumSjr) ? minimumSjr : "custom"
                    }
                    onChange={(e) => {
                      const val = e.target.value;
                      if (val !== "custom") {
                        setMinimumSjr(parseFloat(val));
                      } else {
                        if ([15, 10, 7, 5, 3, 2, 1].includes(minimumSjr)) {
                           setMinimumSjr(0);
                        }
                      }
                    }}
                  >
                    <option value="15">SJR ≥ 15</option>
                    <option value="10">SJR ≥ 10</option>
                    <option value="7">SJR ≥ 7</option>
                    <option value="5">SJR ≥ 5</option>
                    <option value="3">SJR ≥ 3</option>
                    <option value="2">SJR ≥ 2</option>
                    <option value="1">SJR ≥ 1</option>
                    <option value="custom">Custom...</option>
                  </select>
                  
                  {(![15, 10, 7, 5, 3, 2, 1].includes(minimumSjr)) && (
                    <div className="mt-2 flex items-center gap-2">
                      <Label>Custom Minimum SJR:</Label>
                      <input 
                        type="number" 
                        step="0.1" 
                        className="p-1 border rounded"
                        value={minimumSjr} 
                        onChange={(e) => setMinimumSjr(parseFloat(e.target.value) || 0)}
                      />
                    </div>
                  )}

                  <div className="mt-2 p-3 bg-muted/50 rounded-md">
                    <p className="text-xs text-muted-foreground">
                      Typical SJR ranges<br/>
                      Q1 journals: approximately 2.0 – 18+<br/>
                      Q2 journals: approximately 1.0 – 2.0
                    </p>
                  </div>
                </div>
              </>
            )}
            
            <div className="flex justify-end pt-2">
              <Button onClick={saveRetrievalSettings}>
                {settingsSaved ? 'Saved!' : 'Save Filter Settings'}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Appearance Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Appearance</CardTitle>
            <CardDescription>Customize how the app looks</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {(!mounted || resolvedTheme === 'dark') ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
                <div>
                  <Label htmlFor="theme-toggle-auth">Dark Mode</Label>
                  <p className="text-sm text-muted-foreground">
                    Toggle between light and dark themes
                  </p>
                </div>
              </div>
              {mounted && (
                <Switch
                  id="theme-toggle-auth"
                  checked={resolvedTheme === 'dark'}
                  onCheckedChange={(checked) => setTheme(checked ? 'dark' : 'light')}
                />
              )}
            </div>
          </CardContent>
        </Card>

        {/* Notifications Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Bell className="h-5 w-5" />
              Notifications
            </CardTitle>
            <CardDescription>Manage your notification preferences</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="notifications">Email Notifications</Label>
                <p className="text-sm text-muted-foreground">
                  Receive email updates about your searches
                </p>
              </div>
              <Switch
                id="notifications"
                checked={notifications}
                onCheckedChange={setNotifications}
              />
            </div>
            <Separator />
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="research-updates">Research Updates</Label>
                <p className="text-sm text-muted-foreground">
                  Get notified when new papers match your interests
                </p>
              </div>
              <Switch id="research-updates" defaultChecked />
            </div>
          </CardContent>
        </Card>

        {/* Data & Privacy Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Database className="h-5 w-5" />
              Data & Privacy
            </CardTitle>
            <CardDescription>Manage your data and privacy settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <Label htmlFor="data-sharing">Data Sharing</Label>
                <p className="text-sm text-muted-foreground">
                  Help improve our service by sharing anonymous usage data
                </p>
              </div>
              <Switch
                id="data-sharing"
                checked={dataSharing}
                onCheckedChange={setDataSharing}
              />
            </div>
            <Separator />
            <div className="space-y-3">
              <Label>Conversation History</Label>
              <p className="text-sm text-muted-foreground">
                Your conversations are stored locally in your browser. Clear your browser data to remove them.
              </p>
              <Button variant="outline" className="w-full sm:w-auto">
                Export My Data
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Account Settings Placeholder */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Account</CardTitle>
            <CardDescription>Manage your account settings</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <Button variant="outline" className="w-full sm:w-auto">
              Change Password
            </Button>
            <div className="pt-4">
              <Button variant="outline" className="w-full sm:w-auto text-destructive border-destructive hover:bg-destructive hover:text-destructive-foreground">
                Delete Account
              </Button>
            </div>
          </CardContent>
        </Card>
      </main>
    </div>
  );
}
