import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';
import { CheckCircle2, KeyRound, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const token = useMemo(() => new URLSearchParams(window.location.search).get('token') || '', []);
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [complete, setComplete] = useState(false);

  useEffect(() => {
    if (!token) return;
    window.history.replaceState({}, document.title, '/reset-password');
  }, [token]);

  const submit = async (event) => {
    event.preventDefault();
    if (!token) return toast.error('This reset link is invalid. Request a new one.');
    if (password !== confirmPassword) return toast.error('Passwords do not match.');
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/reset-password`, {
        token,
        new_password: password,
      }, { withCredentials: true });
      setComplete(true);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Password reset failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-background px-4 py-16 flex items-center justify-center">
      <Card data-testid="reset-password-card" className="w-full max-w-md p-7 border-t-4 border-t-primary">
        <div className="mb-6">
          <span className="h-12 w-12 border bg-primary/5 flex items-center justify-center mb-4">
            {complete ? <CheckCircle2 className="h-6 w-6 text-emerald-700" /> : <KeyRound className="h-6 w-6 text-primary" />}
          </span>
          <h1 data-testid="reset-password-heading" className="text-3xl font-heading font-semibold mb-2">
            {complete ? 'Password updated' : 'Choose a new password'}
          </h1>
          <p data-testid="reset-password-status" className="text-sm text-muted-foreground font-body">
            {complete
              ? 'Your previous sessions are closed. Sign in again with your new password.'
              : 'Use 12–128 characters with uppercase, lowercase, a number, and a symbol.'}
          </p>
        </div>

        {complete ? (
          <Button data-testid="reset-password-sign-in-button" className="w-full rounded-sm" onClick={() => navigate('/')}>
            Return to sign in
          </Button>
        ) : (
          <form data-testid="reset-password-form" onSubmit={submit} className="space-y-4">
            <div>
              <Label htmlFor="new-password">New password</Label>
              <Input
                id="new-password"
                data-testid="reset-password-new-input"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </div>
            <div>
              <Label htmlFor="confirm-password">Confirm new password</Label>
              <Input
                id="confirm-password"
                data-testid="reset-password-confirm-input"
                type="password"
                autoComplete="new-password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                required
              />
            </div>
            <Button data-testid="reset-password-submit-button" type="submit" className="w-full rounded-sm" disabled={loading || !token}>
              {loading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Updating password…</> : 'Update password'}
            </Button>
            {!token && (
              <p data-testid="reset-password-invalid-token" className="text-sm text-destructive">
                This link is missing its secure token. Request a new reset email.
              </p>
            )}
          </form>
        )}
      </Card>
    </main>
  );
}
