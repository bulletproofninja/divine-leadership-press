import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { CheckCircle2, AlertTriangle, Loader2, ArrowRight, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

export default function AffiliateConnectReturn({ refreshMode = false }) {
  const navigate = useNavigate();
  const [state, setState] = useState({ phase: 'loading', message: 'Checking your Stripe account…' });

  useEffect(() => {
    if (refreshMode) {
      // Stripe sent the affiliate back because the onboarding link expired.
      // Mint a fresh link automatically.
      axios.post(
        `${API}/affiliate/connect/onboard`,
        { origin_url: window.location.origin },
        getAuthHeaders(),
      ).then((r) => {
        if (r.data?.url) window.location.href = r.data.url;
        else throw new Error('No onboarding URL');
      }).catch((error) => {
        setState({
          phase: 'error',
          message: error.response?.data?.detail || 'Could not refresh onboarding link.',
        });
      });
      return;
    }

    axios.get(`${API}/affiliate/connect/status`, getAuthHeaders())
      .then((r) => {
        const d = r.data || {};
        if (d.ready_for_payouts) {
          setState({ phase: 'ready', data: d, message: 'Payout account is fully set up.' });
        } else if (d.connected) {
          setState({
            phase: 'partial',
            data: d,
            message: 'Stripe still needs a few more details before payouts are enabled.',
          });
        } else {
          setState({ phase: 'error', message: 'No connected account found.' });
        }
      })
      .catch((error) => setState({
        phase: 'error',
        message: error.response?.data?.detail || 'Could not load account status.',
      }));
  }, [refreshMode]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card data-testid="connect-return-card" className="p-10 max-w-md w-full text-center">
        {state.phase === 'loading' && (
          <>
            <Loader2 className="h-10 w-10 mx-auto text-primary animate-spin mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">Hold on…</h1>
            <p className="text-sm text-muted-foreground">{state.message}</p>
          </>
        )}

        {state.phase === 'ready' && (
          <>
            <CheckCircle2 className="h-12 w-12 mx-auto text-emerald-600 mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">You're all set.</h1>
            <p className="text-sm text-muted-foreground mb-6">
              Future affiliate commissions will land directly in your bank automatically.
            </p>
            <Button
              data-testid="connect-return-help-btn"
              onClick={() => navigate('/help#earnings')}
              className="rounded-sm"
              size="lg"
            >
              Back to earnings <ArrowRight className="h-4 w-4 ml-2" />
            </Button>
          </>
        )}

        {state.phase === 'partial' && (
          <>
            <AlertTriangle className="h-10 w-10 mx-auto text-amber-600 mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">Almost there.</h1>
            <p className="text-sm text-muted-foreground mb-6">{state.message}</p>
            <Button
              data-testid="connect-return-resume-btn"
              onClick={() => navigate('/help#earnings')}
              className="rounded-sm"
            >
              Resume from earnings page
            </Button>
          </>
        )}

        {state.phase === 'error' && (
          <>
            <AlertTriangle className="h-10 w-10 mx-auto text-destructive mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">
              {refreshMode ? <><RefreshCw className="h-5 w-5 inline mr-2" />Refreshing…</> : 'Something held us up.'}
            </h1>
            <p className="text-sm text-muted-foreground mb-6">{state.message}</p>
            <Button onClick={() => navigate('/help#earnings')}>Back to earnings</Button>
          </>
        )}
      </Card>
    </div>
  );
}
