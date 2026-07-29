import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import {
  ArrowLeft, Check, Crown, Sparkles, Loader2, CheckCircle2, ShieldCheck, ExternalLink, AlertTriangle, FileDown,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

const PLAN_ICONS = {
  author_pro: Sparkles,
  estate: Crown,
};

function formatPrice(amount, currency) {
  try {
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: (currency || 'usd').toUpperCase(),
      minimumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `$${amount}`;
  }
}

function formatExpiry(iso) {
  if (!iso) return null;
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric', month: 'long', day: 'numeric',
    });
  } catch {
    return iso;
  }
}

export default function BillingPage({ user }) {
  const navigate = useNavigate();
  const [plans, setPlans] = useState([]);
  const [status, setStatus] = useState(null);
  const [diagnostics, setDiagnostics] = useState(null);
  const [loadingPlanId, setLoadingPlanId] = useState(null);
  const [loadingInitial, setLoadingInitial] = useState(true);
  const [portalLoading, setPortalLoading] = useState(false);

  useEffect(() => {
    Promise.all([
      axios.get(`${API}/billing/plans`),
      axios.get(`${API}/billing/me`, getAuthHeaders()).catch(() => ({ data: null })),
      axios.get(`${API}/billing/diagnostics`).catch(() => ({ data: null })),
    ]).then(([plansResp, statusResp, diagResp]) => {
      setPlans(plansResp.data.plans || []);
      setStatus(statusResp.data || null);
      setDiagnostics(diagResp.data || null);
    }).catch(() => {
      toast.error('Could not load plans');
    }).finally(() => setLoadingInitial(false));
  }, []);

  const subscribe = async (planId) => {
    setLoadingPlanId(planId);
    try {
      const r = await axios.post(
        `${API}/billing/checkout`,
        { plan_id: planId, origin_url: window.location.origin },
        getAuthHeaders(),
      );
      if (r.data?.url) {
        window.location.href = r.data.url;
      } else {
        throw new Error('No checkout URL returned');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not start checkout');
      setLoadingPlanId(null);
    }
  };

  const openPortal = async () => {
    setPortalLoading(true);
    try {
      const r = await axios.post(`${API}/billing/portal`, {}, getAuthHeaders());
      if (r.data?.url) {
        window.location.href = r.data.url;
      } else {
        throw new Error('No portal URL returned');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not open billing portal');
      setPortalLoading(false);
    }
  };

  if (loadingInitial) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 z-30 bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            data-testid="billing-back-btn"
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard')}
            className="rounded-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            <span className="font-heading text-sm uppercase tracking-[0.18em] text-primary">
              Billing &amp; Plans
            </span>
          </div>
          <div className="w-20" />
        </div>
      </header>

      <div className="container mx-auto px-4 py-12 max-w-5xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl sm:text-5xl font-heading font-semibold mb-3">
            Choose your edition.
          </h1>
          <p className="text-base text-muted-foreground font-body mb-10 max-w-2xl">
            One press. Two editions. Every author tier unlocks the full publishing
            pipeline — from manuscript to KDP-ready PDF, ePub, and audiobook.
            Monthly &mdash; cancel anytime.
          </p>

          {status?.active && (
            <Card
              data-testid="billing-active-card"
              className="p-5 mb-8 border-l-4 border-l-emerald-500 bg-emerald-50/60 flex flex-col sm:flex-row items-start gap-4"
            >
              <div className="flex items-start gap-3 flex-1">
                <CheckCircle2 className="h-5 w-5 text-emerald-700 mt-0.5 flex-shrink-0" />
                <div className="text-sm text-emerald-900">
                  <div className="font-semibold mb-0.5">
                    You&rsquo;re subscribed — {status.plan_name || status.plan_id}
                  </div>
                  <p>
                    Active through <strong>{formatExpiry(status.pro_until)}</strong>.
                    {status.payments_count > 1 && ` (${status.payments_count} payments on file.)`}
                  </p>
                </div>
              </div>
              {diagnostics?.subscription_billing_configured && (
                <Button
                  data-testid="open-portal-btn"
                  variant="outline"
                  size="sm"
                  onClick={openPortal}
                  disabled={portalLoading}
                  className="rounded-sm"
                >
                  {portalLoading ? (
                    <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                  ) : (
                    <ExternalLink className="h-4 w-4 mr-2" />
                  )}
                  Manage subscription
                </Button>
              )}
            </Card>
          )}

          {diagnostics?.live_mode && (
            <Card
              data-testid="live-mode-banner"
              className="p-4 mb-8 border-l-4 border-l-rose-500 bg-rose-50/70 flex items-start gap-3"
            >
              <AlertTriangle className="h-5 w-5 text-rose-700 mt-0.5 flex-shrink-0" />
              <div className="text-sm text-rose-900">
                <div className="font-semibold mb-0.5">Live mode — real cards will be charged.</div>
                <p>
                  This is your production Stripe account. Authors who subscribe will be billed
                  the listed amount immediately and auto-renewed every 30 days until they cancel
                  from the customer portal.
                  {!diagnostics?.webhook_secret_configured && (
                    <> <strong>Action needed:</strong> add the webhook signing secret
                    (<code className="font-mono text-xs">STRIPE_WEBHOOK_SECRET</code>) so renewal events get processed.
                    </>
                  )}
                </p>
              </div>
            </Card>
          )}

          <div className="grid md:grid-cols-2 gap-6">
            {plans.map((plan) => {
              const Icon = PLAN_ICONS[plan.id] || Sparkles;
              const isCurrent = status?.active && status.plan_id === plan.id;
              return (
                <motion.div
                  key={plan.id}
                  whileHover={{ y: -4 }}
                  transition={{ duration: 0.2 }}
                >
                  <Card
                    data-testid={`plan-card-${plan.id}`}
                    className={`p-7 h-full flex flex-col ${
                      isCurrent ? 'border-2 border-primary' : ''
                    }`}
                  >
                    <div className="flex items-center gap-3 mb-3">
                      <span className="p-2 rounded-sm bg-primary/10 text-primary">
                        <Icon className="h-5 w-5" />
                      </span>
                      <h2 className="text-2xl font-heading font-semibold">{plan.name}</h2>
                    </div>
                    <p className="text-sm text-muted-foreground mb-5 min-h-[2.5rem]">
                      {plan.tagline}
                    </p>

                    <div className="mb-6">
                      <div className="flex items-baseline gap-1">
                        <span className="text-5xl font-heading font-semibold">
                          {formatPrice(plan.amount, plan.currency)}
                        </span>
                        <span className="text-sm text-muted-foreground">/month</span>
                      </div>
                    </div>

                    <ul className="space-y-2.5 mb-7 flex-1">
                      {plan.features.map((f, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm">
                          <Check className="h-4 w-4 text-primary mt-0.5 flex-shrink-0" />
                          <span>{f}</span>
                        </li>
                      ))}
                    </ul>

                    <Button
                      data-testid={`subscribe-btn-${plan.id}`}
                      onClick={() => subscribe(plan.id)}
                      disabled={!!loadingPlanId || isCurrent}
                      className="w-full rounded-sm"
                      size="lg"
                    >
                      {loadingPlanId === plan.id ? (
                        <>
                          <Loader2 className="h-4 w-4 mr-2 animate-spin" />
                          Redirecting…
                        </>
                      ) : isCurrent ? (
                        <>Active subscription</>
                      ) : status?.active ? (
                        <>Switch to {plan.name}</>
                      ) : (
                        <>Subscribe — {formatPrice(plan.amount, plan.currency)}/mo</>
                      )}
                    </Button>
                  </Card>
                </motion.div>
              );
            })}
          </div>

          <p className="text-xs text-muted-foreground mt-8 max-w-2xl">
            {diagnostics?.live_mode
              ? 'Payments are processed live by Stripe and auto-renew every 30 days. Cancel any time from "Manage subscription".'
              : 'Payments are processed by Stripe in test mode. Each payment grants 30 days of access; renewals are charged on the same plan when you re-subscribe.'}{' '}
            Affiliate commissions accrue automatically per the program rules you can review in the Help page.
          </p>

          {/* PDF guide callout — prospects can see the full feature list before subscribing */}
          <Card
            data-testid="billing-pdf-guide-card"
            className="mt-6 p-5 border-l-4 border-l-primary bg-accent/30 flex flex-col sm:flex-row sm:items-center gap-4"
          >
            <div className="p-3 rounded-sm bg-primary/10 text-primary flex-shrink-0">
              <FileDown className="h-5 w-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-heading font-semibold text-sm mb-0.5">
                Still weighing it up? Read the full publisher&rsquo;s guide.
              </div>
              <p className="text-xs text-muted-foreground font-body">
                A 6-section PDF walking through what each plan includes, market
                positioning, FAQs, and troubleshooting — before you spend a cent.
              </p>
            </div>
            <a
              data-testid="billing-pdf-guide-btn"
              href="/dlp-user-guide.pdf"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-sm border border-primary text-primary hover:bg-primary hover:text-primary-foreground text-sm font-body transition-colors flex-shrink-0"
            >
              <FileDown className="h-4 w-4" />
              Download PDF Guide
            </a>
          </Card>
        </motion.div>
      </div>
    </div>
  );
}
