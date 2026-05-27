import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { CheckCircle2, Loader2, XCircle, ArrowRight } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

export default function BillingSuccess() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const sessionId = params.get('session_id');
  const [state, setState] = useState({ phase: 'loading', message: 'Confirming your payment…' });
  const attemptsRef = useRef(0);

  useEffect(() => {
    if (!sessionId) {
      setState({ phase: 'error', message: 'Missing checkout session id.' });
      return;
    }

    const MAX_ATTEMPTS = 10;
    const INTERVAL_MS = 2000;
    let cancelled = false;

    const poll = async () => {
      if (cancelled) return;
      attemptsRef.current += 1;
      try {
        const r = await axios.get(
          `${API}/billing/checkout/status/${sessionId}`,
          getAuthHeaders(),
        );
        if (cancelled) return;
        const data = r.data || {};
        if (data.payment_status === 'paid') {
          setState({
            phase: 'success',
            message: 'Payment confirmed — your subscription is active.',
            data,
          });
          return;
        }
        if (data.status === 'expired') {
          setState({ phase: 'error', message: 'This checkout session expired. Please try again.' });
          return;
        }
        if (attemptsRef.current >= MAX_ATTEMPTS) {
          setState({
            phase: 'error',
            message: 'Payment is still processing. Check your email for confirmation, or refresh this page in a moment.',
          });
          return;
        }
        setTimeout(poll, INTERVAL_MS);
      } catch (error) {
        if (cancelled) return;
        if (attemptsRef.current >= MAX_ATTEMPTS) {
          setState({
            phase: 'error',
            message: error.response?.data?.detail || 'Could not confirm payment status.',
          });
          return;
        }
        setTimeout(poll, INTERVAL_MS);
      }
    };

    poll();
    return () => { cancelled = true; };
  }, [sessionId]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card data-testid="billing-success-card" className="p-10 max-w-md w-full text-center">
        {state.phase === 'loading' && (
          <>
            <Loader2 className="h-10 w-10 mx-auto text-primary animate-spin mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">Just a moment…</h1>
            <p className="text-sm text-muted-foreground">{state.message}</p>
          </>
        )}

        {state.phase === 'success' && (
          <>
            <CheckCircle2 className="h-12 w-12 mx-auto text-emerald-600 mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">Welcome aboard.</h1>
            <p className="text-sm text-muted-foreground mb-6">{state.message}</p>
            <div className="flex flex-col gap-2">
              <Button
                data-testid="billing-success-dashboard-btn"
                onClick={() => navigate('/dashboard')}
                className="rounded-sm"
                size="lg"
              >
                Open Dashboard <ArrowRight className="h-4 w-4 ml-2" />
              </Button>
              <Button
                data-testid="billing-success-billing-btn"
                onClick={() => navigate('/billing')}
                variant="ghost"
                size="sm"
              >
                View subscription
              </Button>
            </div>
          </>
        )}

        {state.phase === 'error' && (
          <>
            <XCircle className="h-10 w-10 mx-auto text-destructive mb-4" />
            <h1 className="text-2xl font-heading font-semibold mb-2">Something held us up.</h1>
            <p className="text-sm text-muted-foreground mb-6">{state.message}</p>
            <Button
              data-testid="billing-error-retry-btn"
              onClick={() => navigate('/billing')}
              className="rounded-sm"
            >
              Back to plans
            </Button>
          </>
        )}
      </Card>
    </div>
  );
}
