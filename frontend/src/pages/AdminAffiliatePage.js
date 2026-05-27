import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Textarea } from '../components/ui/textarea';
import { Switch } from '../components/ui/switch';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  ArrowLeft, Save, Shield, AlertCircle, DollarSign, Loader2, Lock,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

const REWARD_TYPES = [
  { key: 'cash_and_perks', label: 'Cash + Perks (both)' },
  { key: 'cash', label: 'Cash only — Stripe Connect' },
  { key: 'credits', label: 'In-app credits' },
  { key: 'perks', label: 'Perks only (free exports, etc.)' },
  { key: 'none', label: 'Tracking only — no reward' },
];

const QUALIFYING_EVENTS = [
  { key: 'active_subscription_60d', label: 'Active subscriber for 60 days' },
  { key: 'first_paid_subscription', label: 'First paid subscription' },
  { key: 'first_book_published', label: 'First book published' },
  { key: 'signup', label: 'Signup (no payment required)' },
];

const PAYOUT_METHODS = [
  { key: 'stripe_connect', label: 'Stripe Connect' },
  { key: 'manual', label: 'Manual (off-platform)' },
  { key: 'none', label: 'No payouts' },
];


export default function AdminAffiliatePage({ user }) {
  const navigate = useNavigate();
  const [settings, setSettings] = useState(null);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user?.is_super_admin) return;
    axios.get(`${API}/affiliate/settings`, getAuthHeaders())
      .then((r) => setSettings(r.data))
      .catch(() => toast.error('Could not load settings'))
      .finally(() => setLoading(false));
  }, [user]);

  if (!user?.is_super_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card data-testid="admin-forbidden" className="p-8 max-w-md text-center">
          <Lock className="h-10 w-10 mx-auto text-destructive mb-4" />
          <h1 className="text-xl font-heading font-semibold mb-2">Owner access only</h1>
          <p className="text-sm text-muted-foreground mb-5">
            This page is reserved for the platform owner.
          </p>
          <Button data-testid="admin-forbidden-back" onClick={() => navigate('/dashboard')}>
            Back to Dashboard
          </Button>
        </Card>
      </div>
    );
  }

  const update = (key, value) => setSettings((s) => ({ ...s, [key]: value }));

  const save = async () => {
    setSaving(true);
    try {
      const r = await axios.put(
        `${API}/admin/affiliate/settings`,
        settings,
        getAuthHeaders()
      );
      setSettings(r.data);
      toast.success('Affiliate settings saved');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save settings');
    } finally {
      setSaving(false);
    }
  };

  if (loading || !settings) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  const needsSubscriptionBilling =
    settings.qualifying_event === 'active_subscription_60d'
    || settings.qualifying_event === 'first_paid_subscription'
    || settings.mrr_commission_percent > 0;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 z-30 bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            data-testid="admin-back-btn"
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard')}
            className="rounded-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <div className="flex items-center gap-2">
            <Shield className="h-4 w-4 text-primary" />
            <span className="font-heading text-sm uppercase tracking-[0.18em] text-primary">
              Owner — Affiliate Program
            </span>
          </div>
          <div className="w-20" />
        </div>
      </header>

      <div className="container mx-auto px-4 py-10 max-w-3xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl sm:text-4xl font-heading font-semibold mb-2">
            Affiliate program parameters
          </h1>
          <p className="text-sm text-muted-foreground font-body mb-8 max-w-2xl">
            These settings control how authors are rewarded for inviting other authors to
            Divine Leadership Press. All numbers are visible to authors on their Share &amp;
            Refer card.
          </p>

          {needsSubscriptionBilling && !settings.stripe_connect_enabled && (
            <div
              data-testid="billing-warning"
              className="mb-6 p-4 rounded-sm border-l-4 border-l-amber-400 bg-amber-50 text-amber-900 flex gap-3"
            >
              <AlertCircle className="h-5 w-5 flex-shrink-0 mt-0.5" />
              <div className="text-sm">
                <div className="font-semibold mb-1">Subscription billing required</div>
                <p>
                  Your reward rules depend on paid subscriptions (MRR or "active for N days"),
                  but DLP does not yet have a billing system. These settings are saved and will
                  activate the moment we wire in Stripe subscriptions + Stripe Connect for
                  payouts. Tracking and the leaderboard already work.
                </p>
              </div>
            </div>
          )}

          <Card className="p-6 space-y-6">
            {/* Enabled toggle */}
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-sm font-semibold">Program enabled</Label>
                <p className="text-xs text-muted-foreground">
                  When off, referral tracking continues but no rewards accrue.
                </p>
              </div>
              <Switch
                data-testid="admin-enabled-switch"
                checked={!!settings.enabled}
                onCheckedChange={(v) => update('enabled', v)}
              />
            </div>

            {/* Reward type */}
            <div>
              <Label className="text-sm font-semibold">Reward type</Label>
              <Select value={settings.reward_type} onValueChange={(v) => update('reward_type', v)}>
                <SelectTrigger data-testid="admin-reward-type" className="rounded-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {REWARD_TYPES.map((r) => (
                    <SelectItem key={r.key} value={r.key}>{r.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Commissions */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold">Signup commission %</Label>
                <Input
                  data-testid="admin-signup-pct"
                  type="number" min="0" max="100" step="0.5"
                  value={settings.signup_commission_percent ?? 0}
                  onChange={(e) => update('signup_commission_percent', parseFloat(e.target.value) || 0)}
                  className="rounded-sm font-mono"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  One-time at qualifying event.
                </p>
              </div>
              <div>
                <Label className="text-sm font-semibold">MRR commission %</Label>
                <Input
                  data-testid="admin-mrr-pct"
                  type="number" min="0" max="100" step="0.5"
                  value={settings.mrr_commission_percent ?? 0}
                  onChange={(e) => update('mrr_commission_percent', parseFloat(e.target.value) || 0)}
                  className="rounded-sm font-mono"
                />
                <p className="text-[11px] text-muted-foreground mt-1">
                  Recurring monthly while invitee remains an active subscriber.
                </p>
              </div>
            </div>

            {/* Qualifying event */}
            <div>
              <Label className="text-sm font-semibold">Qualifying event</Label>
              <Select value={settings.qualifying_event} onValueChange={(v) => update('qualifying_event', v)}>
                <SelectTrigger data-testid="admin-qualifying-event" className="rounded-sm">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUALIFYING_EVENTS.map((q) => (
                    <SelectItem key={q.key} value={q.key}>{q.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold">Active days required</Label>
                <Input
                  data-testid="admin-active-days"
                  type="number" min="0" step="1"
                  value={settings.active_days_required ?? 0}
                  onChange={(e) => update('active_days_required', parseInt(e.target.value, 10) || 0)}
                  className="rounded-sm font-mono"
                />
              </div>
              <div>
                <Label className="text-sm font-semibold">Minimum payout ({settings.currency || 'USD'})</Label>
                <Input
                  data-testid="admin-min-payout"
                  type="number" min="0" step="1"
                  value={settings.minimum_payout ?? 0}
                  onChange={(e) => update('minimum_payout', parseFloat(e.target.value) || 0)}
                  className="rounded-sm font-mono"
                />
              </div>
            </div>

            {/* Payout method */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <Label className="text-sm font-semibold">Payout method</Label>
                <Select value={settings.payout_method} onValueChange={(v) => update('payout_method', v)}>
                  <SelectTrigger data-testid="admin-payout-method" className="rounded-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAYOUT_METHODS.map((p) => (
                      <SelectItem key={p.key} value={p.key}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <Label className="text-sm font-semibold">Currency</Label>
                <Input
                  data-testid="admin-currency"
                  value={settings.currency || 'USD'}
                  onChange={(e) => update('currency', e.target.value.toUpperCase().slice(0, 4))}
                  className="rounded-sm font-mono uppercase"
                />
              </div>
            </div>

            {/* Stripe Connect status */}
            <div className="flex items-center justify-between p-3 rounded-sm border bg-accent/30">
              <div className="flex items-center gap-2">
                <DollarSign className="h-4 w-4 text-primary" />
                <div>
                  <Label className="text-sm font-semibold">Stripe Connect onboarded</Label>
                  <p className="text-[11px] text-muted-foreground">
                    Flip ON only after Stripe Connect setup is complete (separate build).
                  </p>
                </div>
              </div>
              <Switch
                data-testid="admin-stripe-toggle"
                checked={!!settings.stripe_connect_enabled}
                onCheckedChange={(v) => update('stripe_connect_enabled', v)}
              />
            </div>

            {/* Perks */}
            <div>
              <Label className="text-sm font-semibold">Perks description (shown to authors)</Label>
              <Textarea
                data-testid="admin-perks"
                value={settings.perks_description || ''}
                onChange={(e) => update('perks_description', e.target.value)}
                className="rounded-sm min-h-[60px]"
              />
            </div>

            {/* Notes */}
            <div>
              <Label className="text-sm font-semibold">Internal notes (not shown to authors)</Label>
              <Textarea
                data-testid="admin-notes"
                value={settings.notes || ''}
                onChange={(e) => update('notes', e.target.value)}
                className="rounded-sm min-h-[60px]"
              />
            </div>

            <Button
              data-testid="admin-save-btn"
              className="w-full rounded-sm"
              disabled={saving}
              onClick={save}
            >
              {saving ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</>) :
                (<><Save className="h-4 w-4 mr-2" /> Save settings</>)}
            </Button>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
