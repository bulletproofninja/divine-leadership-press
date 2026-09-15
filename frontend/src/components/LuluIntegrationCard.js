import { useEffect, useRef, useState } from 'react';
import axios from 'axios';
import { AlertTriangle, CheckCircle2, KeyRound, Loader2, PlugZap, Save, Trash2 } from 'lucide-react';
import { toast } from 'sonner';
import { Button } from './ui/button';
import { Card } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const auth = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
  withCredentials: true,
});

export const LuluIntegrationCard = () => {
  const [status, setStatus] = useState({ configured: false, environment: 'production', connection_status: 'not_tested' });
  const [environment, setEnvironment] = useState('production');
  const [clientKey, setClientKey] = useState('');
  const [clientSecret, setClientSecret] = useState('');
  const [busy, setBusy] = useState('');
  const [confirmingClear, setConfirmingClear] = useState(false);
  const environmentTouched = useRef(false);

  const loadStatus = async () => {
    try {
      const response = await axios.get(`${API}/admin/integrations/lulu`, auth());
      setStatus(response.data);
      if (!environmentTouched.current) {
        setEnvironment(response.data.environment || 'production');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not load Lulu settings');
    }
  };

  useEffect(() => { loadStatus(); }, []);

  const save = async (event) => {
    event.preventDefault();
    setBusy('save');
    try {
      const response = await axios.put(`${API}/admin/integrations/lulu`, {
        environment,
        client_key: clientKey,
        client_secret: clientSecret,
      }, auth());
      setStatus(response.data);
      setClientKey('');
      setClientSecret('');
      toast.success('Lulu credentials encrypted and saved');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save Lulu credentials');
    } finally {
      setBusy('');
    }
  };

  const testConnection = async () => {
    setBusy('test');
    try {
      const response = await axios.post(`${API}/admin/integrations/lulu/test`, {}, auth());
      setStatus((current) => ({ ...current, connection_status: 'connected' }));
      toast.success(response.data.message);
    } catch (error) {
      setStatus((current) => ({ ...current, connection_status: 'error' }));
      toast.error(error.response?.data?.detail || 'Lulu connection failed');
    } finally {
      setBusy('');
    }
  };

  const clear = async () => {
    setBusy('clear');
    try {
      const response = await axios.delete(`${API}/admin/integrations/lulu`, auth());
      setStatus(response.data);
      environmentTouched.current = false;
      setEnvironment('production');
      setConfirmingClear(false);
      toast.success('Lulu credentials removed');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not remove Lulu credentials');
    } finally {
      setBusy('');
    }
  };

  return (
    <Card data-testid="lulu-integration-card" className="p-5 mb-10 border-l-4 border-l-emerald-700">
      <div className="flex items-start justify-between gap-4 mb-5">
        <div className="flex items-start gap-3 min-w-0">
          <span className="p-2 bg-emerald-50 text-emerald-800 flex-shrink-0"><PlugZap className="h-5 w-5" /></span>
          <div className="min-w-0">
            <h2 className="text-lg font-heading font-semibold">Lulu Direct</h2>
            <p data-testid="lulu-integration-help" className="text-xs text-muted-foreground mt-1">
              Owner-only publishing credentials. Secrets are encrypted before storage and never shown again.
            </p>
          </div>
        </div>
        <span
          data-testid="lulu-connection-status"
          className={`text-[10px] uppercase tracking-wider px-2 py-1 border flex-shrink-0 ${
            status.connection_status === 'connected'
              ? 'border-emerald-600 text-emerald-800 bg-emerald-50'
              : status.connection_status === 'error'
                ? 'border-red-500 text-red-700 bg-red-50'
                : 'border-border text-muted-foreground'
          }`}
        >
          {status.connection_status === 'connected' ? 'Connected' : status.configured ? 'Saved' : 'Not configured'}
        </span>
      </div>

      <div data-testid="lulu-environment-warning" className="flex items-start gap-2 border border-amber-300 bg-amber-50 p-3 mb-5 text-xs text-amber-950">
        <AlertTriangle className="h-4 w-4 mt-0.5 flex-shrink-0" />
        {environment === 'production'
          ? 'Production is selected. Creating a live print job can incur Lulu charges; use Test Connection before publishing.'
          : 'Sandbox is selected. Test jobs stay separate from Lulu production.'}
      </div>

      <form data-testid="lulu-credentials-form" onSubmit={save} className="space-y-4">
        <div>
          <Label>Environment</Label>
          <div className="grid grid-cols-2 gap-2 mt-1">
            {['production', 'sandbox'].map((value) => (
              <Button
                key={value}
                data-testid={`lulu-environment-${value}`}
                data-state={environment === value ? 'active' : 'inactive'}
                aria-pressed={environment === value}
                type="button"
                size="sm"
                variant={environment === value ? 'default' : 'outline'}
                className="rounded-sm capitalize"
                onClick={() => {
                  environmentTouched.current = true;
                  setEnvironment(value);
                }}
              >
                {environment === value && <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />}
                {value}
              </Button>
            ))}
          </div>
        </div>
        <div>
          <Label htmlFor="lulu-client-key">Client key</Label>
          <Input
            id="lulu-client-key"
            data-testid="lulu-client-key-input"
            type="password"
            autoComplete="off"
            placeholder={status.client_key_hint || 'Paste Lulu client key'}
            value={clientKey}
            onChange={(event) => setClientKey(event.target.value)}
            required
          />
        </div>
        <div>
          <Label htmlFor="lulu-client-secret">Client secret</Label>
          <Input
            id="lulu-client-secret"
            data-testid="lulu-client-secret-input"
            type="password"
            autoComplete="new-password"
            placeholder={status.configured ? 'Enter a new secret to replace it' : 'Paste Lulu client secret'}
            value={clientSecret}
            onChange={(event) => setClientSecret(event.target.value)}
            required
          />
        </div>
        <div className="flex flex-wrap gap-2">
          <Button data-testid="lulu-save-credentials-button" type="submit" className="rounded-sm" disabled={!!busy}>
            {busy === 'save' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Save className="h-4 w-4 mr-2" />}
            Save encrypted credentials
          </Button>
          <Button
            data-testid="lulu-test-connection-button"
            type="button"
            variant="outline"
            className="rounded-sm"
            disabled={!status.configured || !!busy}
            onClick={testConnection}
          >
            {busy === 'test' ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <KeyRound className="h-4 w-4 mr-2" />}
            Test connection
          </Button>
        </div>
      </form>

      {status.configured && (
        <div className="border-t mt-5 pt-4 flex items-center justify-between gap-3 flex-wrap">
          <p data-testid="lulu-saved-key-hint" className="text-xs text-muted-foreground">
            Saved {status.environment} key: <span className="font-mono">{status.client_key_hint}</span>
          </p>
          {confirmingClear ? (
            <div className="flex gap-2">
              <Button data-testid="lulu-clear-confirm-button" type="button" size="sm" variant="destructive" onClick={clear} disabled={!!busy}>
                {busy === 'clear' && <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />} Remove
              </Button>
              <Button data-testid="lulu-clear-cancel-button" type="button" size="sm" variant="ghost" onClick={() => setConfirmingClear(false)}>Cancel</Button>
            </div>
          ) : (
            <Button data-testid="lulu-clear-credentials-button" type="button" size="sm" variant="ghost" onClick={() => setConfirmingClear(true)}>
              <Trash2 className="h-3.5 w-3.5 mr-1.5" /> Clear credentials
            </Button>
          )}
        </div>
      )}
    </Card>
  );
};