import React, { useState, useEffect } from 'react';
import Layout from '../components/Layout';
import { User, Lock, Bell, Settings2 } from 'lucide-react';

function Toggle({ checked, onChange }) {
  return (
    <button
      onClick={() => onChange(!checked)}
      className={`relative inline-flex items-center w-11 h-6 rounded-full transition-colors duration-200 focus:outline-none ${
        checked ? 'bg-indigo-500' : 'bg-slate-200'
      }`}
    >
      <span
        className={`inline-block w-4 h-4 bg-white rounded-full shadow transform transition-transform duration-200 ${
          checked ? 'translate-x-6' : 'translate-x-1'
        }`}
      />
    </button>
  );
}

export default function Settings() {
  // ── User Profile ──────────────────────────────────────────────────
  const [profile, setProfile] = useState({ firstName: 'Nitin', lastName: 'P', email: 'admin@ecc.engineering', role: 'admin' });
  const [profileSaving, setProfileSaving] = useState(false);

  // ── Security ──────────────────────────────────────────────────────
  const [passwords, setPasswords] = useState({ current: '', newPass: '', confirm: '' });
  const [passwordSaving, setPasswordSaving] = useState(false);

  // ── Notification Preferences ──────────────────────────────────────
  const [notifications, setNotifications] = useState({
    overdueAlerts: true,
    newAssignments: true,
    drawingProcessed: true,
    lowOcrConfidence: false,
    emailDigest: false,
  });

  // ── OCR & Processing ──────────────────────────────────────────────
  const [ocr, setOcr] = useState({
    confidenceThreshold: 70,
    defaultLanguage: 'English',
    autoAssignTo: 'Round Robin',
    autoGenerateCrs: true,
  });
  const [ocrSaving, setOcrSaving] = useState(false);

  useEffect(() => {
    async function fetchSettings() {
      try {
        const [profileRes, notifRes, ocrRes] = await Promise.all([
          fetch('/api/settings/profile'),
          fetch('/api/settings/notifications'),
          fetch('/api/settings/ocr'),
        ]);
        const [profileData, notifData, ocrData] = await Promise.all([
          profileRes.json(),
          notifRes.json(),
          ocrRes.json(),
        ]);
        setProfile(profileData);
        setNotifications(notifData);
        setOcr(ocrData);
      } catch (err) {
        console.error('Failed to fetch settings:', err);
      }
    }
    fetchSettings();
  }, []);

  async function handleSaveProfile() {
    setProfileSaving(true);
    try {
      await fetch('/api/settings/profile', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(profile),
      });
    } catch (err) {
      console.error('Save profile failed:', err);
    } finally {
      setProfileSaving(false);
    }
  }

  async function handleUpdatePassword() {
    if (passwords.newPass !== passwords.confirm) {
      alert('New passwords do not match.');
      return;
    }
    setPasswordSaving(true);
    try {
      await fetch('/api/settings/password', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ currentPassword: passwords.current, newPassword: passwords.newPass }),
      });
      setPasswords({ current: '', newPass: '', confirm: '' });
    } catch (err) {
      console.error('Password update failed:', err);
    } finally {
      setPasswordSaving(false);
    }
  }

  async function handleToggleNotification(key, value) {
    const updated = { ...notifications, [key]: value };
    setNotifications(updated);
    try {
      await fetch('/api/settings/notifications', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(updated),
      });
    } catch (err) {
      console.error('Notification update failed:', err);
      // Revert on failure
      setNotifications(notifications);
    }
  }

  async function handleSaveOcr() {
    setOcrSaving(true);
    try {
      await fetch('/api/settings/ocr', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(ocr),
      });
    } catch (err) {
      console.error('OCR settings save failed:', err);
    } finally {
      setOcrSaving(false);
    }
  }

  // Initials for avatar
  const initials = `${profile.firstName?.[0] ?? ''}${profile.lastName?.[0] ?? ''}`.toUpperCase() || 'NA';

  return (
    <Layout>
      <div className="max-w-7xl mx-auto space-y-6">

        {/* Page Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-800">Settings</h1>
          <p className="text-sm text-slate-500">Configure system preferences, user profile and OCR options</p>
        </div>

        <div className="grid grid-cols-3 gap-6 items-start">

          {/* ── Left Column ─────────────────────────────────────────── */}
          <div className="col-span-2 space-y-6">

            {/* User Profile Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              <div className="flex items-center gap-2 pb-1">
                <User size={16} className="text-slate-400" />
                <h2 className="font-semibold text-slate-800">User Profile</h2>
              </div>

              {/* Avatar Row */}
              <div className="flex items-center gap-4">
                <div className="w-14 h-14 rounded-full bg-indigo-500 flex items-center justify-center text-white font-bold text-lg select-none">
                  {initials}
                </div>
                <div>
                  <p className="font-semibold text-slate-800">{profile.firstName} {profile.lastName}</p>
                  <p className="text-xs text-slate-500">{profile.email}</p>
                  <span className="inline-flex items-center gap-1 mt-1 text-[11px] font-semibold text-indigo-600 bg-indigo-50 border border-indigo-100 px-2 py-0.5 rounded-full">
                    <span className="w-1.5 h-1.5 rounded-full bg-indigo-500"></span>
                    {profile.role}
                  </span>
                </div>
              </div>

              {/* Name Fields */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">First Name</label>
                  <input
                    type="text"
                    value={profile.firstName}
                    onChange={e => setProfile(p => ({ ...p, firstName: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Last Name</label>
                  <input
                    type="text"
                    value={profile.lastName}
                    onChange={e => setProfile(p => ({ ...p, lastName: e.target.value }))}
                    className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>
              </div>

              {/* Email */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Email</label>
                <input
                  type="email"
                  value={profile.email}
                  onChange={e => setProfile(p => ({ ...p, email: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              {/* Role */}
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Role</label>
                <select
                  value={profile.role}
                  onChange={e => setProfile(p => ({ ...p, role: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none appearance-none"
                >
                  <option>ECC Admin</option>
                  <option>Engineer</option>
                  <option>Viewer</option>
                </select>
              </div>

              <button
                onClick={handleSaveProfile}
                disabled={profileSaving}
                className="bg-indigo-500 hover:bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors disabled:opacity-60"
              >
                💾 {profileSaving ? 'Saving...' : 'Save Profile'}
              </button>
            </div>

            {/* Security Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              <div className="flex items-center gap-2 pb-1">
                <Lock size={16} className="text-slate-400" />
                <h2 className="font-semibold text-slate-800">Security</h2>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Current Password</label>
                <input
                  type="password"
                  value={passwords.current}
                  onChange={e => setPasswords(p => ({ ...p, current: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">New Password</label>
                <input
                  type="password"
                  value={passwords.newPass}
                  onChange={e => setPasswords(p => ({ ...p, newPass: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                  placeholder="••••••••"
                />
              </div>
              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Confirm New Password</label>
                <input
                  type="password"
                  value={passwords.confirm}
                  onChange={e => setPasswords(p => ({ ...p, confirm: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                  placeholder="••••••••"
                />
              </div>

              <button
                onClick={handleUpdatePassword}
                disabled={passwordSaving}
                className="bg-indigo-500 hover:bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors disabled:opacity-60"
              >
                🔑 {passwordSaving ? 'Updating...' : 'Update Password'}
              </button>
            </div>
          </div>

          {/* ── Right Column ─────────────────────────────────────────── */}
          <div className="space-y-6">

            {/* Notification Preferences Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              <div className="flex items-center gap-2 pb-1">
                <Bell size={16} className="text-amber-400" />
                <h2 className="font-semibold text-slate-800">Notification Preferences</h2>
              </div>

              {[
                { key: 'overdueAlerts', label: 'Overdue Alerts', desc: 'Notify when CRS items pass target date' },
                { key: 'newAssignments', label: 'New Assignments', desc: 'Notify when comments are assigned to you' },
                { key: 'drawingProcessed', label: 'Drawing Processed', desc: 'Notify when OCR completes on a drawing' },
                { key: 'lowOcrConfidence', label: 'Low OCR Confidence', desc: 'Alert when comments score below 70%' },
                { key: 'emailDigest', label: 'Email Digest', desc: 'Daily summary email at 8am' },
              ].map(item => (
                <div key={item.key} className="flex items-center justify-between gap-4">
                  <div>
                    <p className="text-sm font-medium text-slate-700">{item.label}</p>
                    <p className="text-xs text-slate-400">{item.desc}</p>
                  </div>
                  <Toggle
                    checked={notifications[item.key]}
                    onChange={val => handleToggleNotification(item.key, val)}
                  />
                </div>
              ))}
            </div>

            {/* OCR & Processing Card */}
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 space-y-5">
              <div className="flex items-center gap-2 pb-1">
                <Settings2 size={16} className="text-slate-400" />
                <h2 className="font-semibold text-slate-800">OCR & Processing</h2>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Confidence Threshold (%)</label>
                <input
                  type="number"
                  min={0}
                  max={100}
                  value={ocr.confidenceThreshold}
                  onChange={e => setOcr(o => ({ ...o, confidenceThreshold: Number(e.target.value) }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none"
                />
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Default Language</label>
                <select
                  value={ocr.defaultLanguage}
                  onChange={e => setOcr(o => ({ ...o, defaultLanguage: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none appearance-none"
                >
                  <option>English</option>
                  <option>Hindi</option>
                  <option>German</option>
                  <option>French</option>
                </select>
              </div>

              <div>
                <label className="block text-[10px] font-bold text-slate-400 uppercase tracking-wider mb-1.5">Auto-Assign To</label>
                <select
                  value={ocr.autoAssignTo}
                  onChange={e => setOcr(o => ({ ...o, autoAssignTo: e.target.value }))}
                  className="w-full px-3 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm text-slate-700 focus:ring-2 focus:ring-indigo-500 outline-none appearance-none"
                >
                  <option>Round Robin</option>
                  <option>Least Busy</option>
                  <option>Manual</option>
                </select>
              </div>

              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="text-sm font-medium text-slate-700">Auto-generate CRS</p>
                  <p className="text-xs text-slate-400">Automatically create CRS after OCR</p>
                </div>
                <Toggle
                  checked={ocr.autoGenerateCrs}
                  onChange={val => setOcr(o => ({ ...o, autoGenerateCrs: val }))}
                />
              </div>

              <button
                onClick={handleSaveOcr}
                disabled={ocrSaving}
                className="bg-indigo-500 hover:bg-indigo-600 text-white px-5 py-2 rounded-lg text-sm font-semibold flex items-center gap-2 shadow-sm transition-colors disabled:opacity-60"
              >
                💾 {ocrSaving ? 'Saving...' : 'Save OCR Settings'}
              </button>
            </div>

          </div>
        </div>
      </div>
    </Layout>
  );
}