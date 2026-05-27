import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import { Checkbox } from '../components/ui/checkbox';
import {
  ArrowLeft, Shield, Loader2, Lock, DollarSign, CheckCircle2, Banknote,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

const PAYOUT_METHODS = [
  { key: 'manual', label: 'Manual / off-platform' },
  { key: 'stripe_connect', label: 'Stripe Connect' },
  { key: 'paypal', label: 'PayPal' },
  { key: 'wire', label: 'Wire transfer' },
];

function fmt(amount, currency = 'USD') {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency', currency: currency.toUpperCase(),
    }).format(amount);
  } catch { return `$${amount}`; }
}

function fmtDate(iso) {
  if (!iso) return '—';
  try { return new Date(iso).toLocaleDateString(); } catch { return iso; }
}

export default function AdminCommissionsPage({ user }) {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [commissions, setCommissions] = useState([]);
  const [pendingByUser, setPendingByUser] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [filter, setFilter] = useState('pending');
  const [payoutMethod, setPayoutMethod] = useState('manual');
  const [payoutReference, setPayoutReference] = useState('');
  const [marking, setMarking] = useState(false);

  const load = async () => {
    setLoading(true);
    try {
      const r = await axios.get(
        `${API}/admin/commissions${filter && filter !== 'all' ? `?status=${filter}` : ''}`,
        getAuthHeaders(),
      );
      setCommissions(r.data.commissions || []);
      setPendingByUser(r.data.pending_by_user || []);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not load commissions');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (user?.is_super_admin) load();
  }, [filter, user]);

  if (!user?.is_super_admin) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background p-4">
        <Card data-testid="commissions-forbidden" className="p-8 max-w-md text-center">
          <Lock className="h-10 w-10 mx-auto text-destructive mb-4" />
          <h1 className="text-xl font-heading font-semibold mb-2">Owner access only</h1>
          <Button onClick={() => navigate('/dashboard')}>Back to Dashboard</Button>
        </Card>
      </div>
    );
  }

  const toggle = (id) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id); else next.add(id);
    setSelected(next);
  };

  const selectAllPending = () => {
    const pending = commissions.filter((c) => c.status === 'pending').map((c) => c.id);
    setSelected(new Set(pending));
  };

  const clearSelection = () => setSelected(new Set());

  const markPaid = async () => {
    if (selected.size === 0) {
      toast.error('Pick at least one commission row');
      return;
    }
    setMarking(true);
    try {
      const r = await axios.post(
        `${API}/admin/commissions/mark-paid`,
        {
          commission_ids: Array.from(selected),
          payout_method: payoutMethod,
          payout_reference: payoutReference || null,
        },
        getAuthHeaders(),
      );
      toast.success(`${r.data.marked_paid} commission(s) marked paid`);
      setSelected(new Set());
      setPayoutReference('');
      load();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not mark commissions paid');
    } finally {
      setMarking(false);
    }
  };

  const selectedTotal = commissions
    .filter((c) => selected.has(c.id))
    .reduce((sum, c) => sum + Number(c.amount || 0), 0);

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 z-30 bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            data-testid="commissions-back-btn"
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
              Owner — Commissions &amp; Payouts
            </span>
          </div>
          <Button
            data-testid="commissions-affiliate-link"
            variant="ghost"
            size="sm"
            onClick={() => navigate('/admin/affiliate')}
            className="rounded-sm"
          >
            Settings
          </Button>
        </div>
      </header>

      <div className="container mx-auto px-4 py-10 max-w-6xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl sm:text-4xl font-heading font-semibold mb-2">
            Affiliate commissions
          </h1>
          <p className="text-sm text-muted-foreground font-body mb-8 max-w-2xl">
            Every paid subscription from a referred author accrues a commission per the program
            rules. Pay out by Stripe Connect (when enabled), or mark rows as paid manually after
            a wire / PayPal transfer.
          </p>

          {/* Pending-by-user summary */}
          <Card className="p-6 mb-6">
            <div className="flex items-center gap-2 mb-4">
              <DollarSign className="h-4 w-4 text-primary" />
              <h2 className="font-heading text-lg font-semibold">Outstanding balances</h2>
            </div>
            {pendingByUser.length === 0 ? (
              <p data-testid="no-pending" className="text-sm text-muted-foreground">
                No pending commissions right now.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 pr-4">Affiliate</th>
                      <th className="py-2 pr-4">Email</th>
                      <th className="py-2 pr-4 text-right">Pending rows</th>
                      <th className="py-2 pr-4 text-right">Pending total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingByUser.map((u) => (
                      <tr key={u.user_id} className="border-t" data-testid={`pending-user-${u.user_id}`}>
                        <td className="py-2 pr-4 font-medium">{u.name || '—'}</td>
                        <td className="py-2 pr-4 text-muted-foreground">{u.email || '—'}</td>
                        <td className="py-2 pr-4 text-right">{u.count}</td>
                        <td className="py-2 pr-4 text-right font-mono">{fmt(u.pending_total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>

          {/* Filter + mark-paid panel */}
          <Card className="p-6 mb-6">
            <div className="flex flex-wrap items-end gap-4 mb-5">
              <div className="min-w-[180px]">
                <Label className="text-xs font-semibold">Filter</Label>
                <Select value={filter} onValueChange={setFilter}>
                  <SelectTrigger data-testid="commissions-filter" className="rounded-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="paid">Paid</SelectItem>
                    <SelectItem value="all">All</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="min-w-[200px]">
                <Label className="text-xs font-semibold">Payout method</Label>
                <Select value={payoutMethod} onValueChange={setPayoutMethod}>
                  <SelectTrigger data-testid="payout-method" className="rounded-sm">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {PAYOUT_METHODS.map((p) => (
                      <SelectItem key={p.key} value={p.key}>{p.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex-1 min-w-[200px]">
                <Label className="text-xs font-semibold">Payout reference (optional)</Label>
                <Input
                  data-testid="payout-reference"
                  value={payoutReference}
                  onChange={(e) => setPayoutReference(e.target.value)}
                  placeholder="Wire #, check #, Stripe tr_…"
                  className="rounded-sm"
                />
              </div>
              <Button
                data-testid="mark-paid-btn"
                onClick={markPaid}
                disabled={selected.size === 0 || marking}
                size="lg"
                className="rounded-sm"
              >
                {marking ? (
                  <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                ) : (
                  <Banknote className="h-4 w-4 mr-2" />
                )}
                Mark {selected.size || ''} as paid {selected.size > 0 ? `· ${fmt(selectedTotal)}` : ''}
              </Button>
            </div>

            <div className="flex gap-3 mb-4">
              <Button
                data-testid="select-all-pending-btn"
                variant="ghost"
                size="sm"
                onClick={selectAllPending}
                className="rounded-sm"
              >
                Select all pending
              </Button>
              {selected.size > 0 && (
                <Button
                  data-testid="clear-selection-btn"
                  variant="ghost"
                  size="sm"
                  onClick={clearSelection}
                  className="rounded-sm"
                >
                  Clear ({selected.size})
                </Button>
              )}
            </div>

            {loading ? (
              <div className="py-12 flex justify-center">
                <Loader2 className="h-6 w-6 animate-spin text-primary" />
              </div>
            ) : commissions.length === 0 ? (
              <p data-testid="no-commissions" className="py-8 text-center text-sm text-muted-foreground">
                No commissions match this filter.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs uppercase tracking-wider text-muted-foreground">
                      <th className="py-2 pr-2 w-10"></th>
                      <th className="py-2 pr-4">When</th>
                      <th className="py-2 pr-4">Affiliate</th>
                      <th className="py-2 pr-4">Referee paid</th>
                      <th className="py-2 pr-4">Plan</th>
                      <th className="py-2 pr-4">Kind</th>
                      <th className="py-2 pr-4 text-right">Commission</th>
                      <th className="py-2 pr-4">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {commissions.map((c) => (
                      <tr key={c.id} className="border-t" data-testid={`commission-row-${c.id}`}>
                        <td className="py-2 pr-2">
                          {c.status === 'pending' && (
                            <Checkbox
                              data-testid={`commission-check-${c.id}`}
                              checked={selected.has(c.id)}
                              onCheckedChange={() => toggle(c.id)}
                            />
                          )}
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground">{fmtDate(c.created_at)}</td>
                        <td className="py-2 pr-4">
                          <div className="font-medium">{c.referrer_name || '—'}</div>
                          <div className="text-xs text-muted-foreground">{c.referrer_email}</div>
                        </td>
                        <td className="py-2 pr-4 text-muted-foreground">{c.referee_email}</td>
                        <td className="py-2 pr-4">{c.plan_id}</td>
                        <td className="py-2 pr-4">
                          <span className="text-xs uppercase tracking-wider">
                            {c.kind} · {c.percent}%
                          </span>
                        </td>
                        <td className="py-2 pr-4 text-right font-mono">{fmt(c.amount, c.currency)}</td>
                        <td className="py-2 pr-4">
                          {c.status === 'paid' ? (
                            <span className="inline-flex items-center gap-1 text-xs text-emerald-700">
                              <CheckCircle2 className="h-3.5 w-3.5" /> Paid
                            </span>
                          ) : (
                            <span className="text-xs text-amber-700">Pending</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
