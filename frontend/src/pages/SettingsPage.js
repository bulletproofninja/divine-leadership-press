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
  ArrowLeft, Key, Sparkles, Loader2, CheckCircle2, Trash2, ExternalLink, BotMessageSquare,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
});

const PROVIDER_META = {
  anthropic: {
    label: 'Anthropic (Claude)',
    keyPrefix: 'sk-ant-',
    model: 'claude-sonnet-4-5',
    getKeyUrl: 'https://console.anthropic.com/settings/keys',
    tagline: 'Best for long-form prose, voice matching, and nuanced editorial polish.',
  },
  openai: {
    label: 'OpenAI (ChatGPT)',
    keyPrefix: 'sk-',
    model: 'gpt-5.4',
    getKeyUrl: 'https://platform.openai.com/api-keys',
    tagline: 'Fast, versatile, great at brainstorming and structured outlines.',
  },
};

function KeyCard({ providerKey, hasKey, onSave, onClear, onTest, savingKey, clearingKey, testingKey }) {
  const meta = PROVIDER_META[providerKey];
  const [inputKey, setInputKey] = useState('');
  const [editing, setEditing] = useState(false);

  const submit = async () => {
    const k = inputKey.trim();
    if (!k) return toast.error('Paste your API key first');
    await onSave(providerKey, k);
    setInputKey('');
    setEditing(false);
  };

  return (
    <Card
      data-testid={`llm-key-card-${providerKey}`}
      className={`p-5 ${hasKey ? 'border-l-4 border-l-emerald-500' : ''}`}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-start gap-3">
          <span className={`p-2 rounded-sm ${hasKey ? 'bg-emerald-50 text-emerald-700' : 'bg-primary/10 text-primary'}`}>
            {hasKey ? <CheckCircle2 className="h-5 w-5" /> : <BotMessageSquare className="h-5 w-5" />}
          </span>
          <div>
            <div className="text-base font-heading font-semibold leading-tight">
              {meta.label}
            </div>
            <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground mt-0.5">
              {meta.model} · BYO key
            </div>
            <p className="text-xs text-muted-foreground font-body mt-1 max-w-md">
              {meta.tagline}
            </p>
          </div>
        </div>
        <a
          href={meta.getKeyUrl}
          target="_blank"
          rel="noopener noreferrer"
          data-testid={`llm-key-get-${providerKey}`}
          className="inline-flex items-center gap-1 text-xs text-primary hover:underline flex-shrink-0"
        >
          Get key <ExternalLink className="h-3 w-3" />
        </a>
      </div>

      {hasKey && !editing ? (
        <div className="flex items-center gap-2 text-xs text-emerald-800 bg-emerald-50 border rounded-sm p-2">
          <CheckCircle2 className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">Connected. Agent calls route through your provider account.</span>
          <Button
            data-testid={`llm-key-test-${providerKey}`}
            variant="outline"
            size="sm"
            className="h-7 text-xs rounded-sm"
            onClick={() => onTest(providerKey)}
            disabled={testingKey === providerKey}
          >
            {testingKey === providerKey ? <Loader2 className="h-3 w-3 animate-spin" /> : 'Test'}
          </Button>
          <Button
            data-testid={`llm-key-replace-${providerKey}`}
            variant="ghost"
            size="sm"
            className="h-7 text-xs rounded-sm"
            onClick={() => setEditing(true)}
          >
            Replace
          </Button>
          <Button
            data-testid={`llm-key-clear-${providerKey}`}
            variant="ghost"
            size="sm"
            className="h-7 text-xs rounded-sm text-destructive"
            onClick={() => onClear(providerKey)}
            disabled={clearingKey === providerKey}
          >
            {clearingKey === providerKey ? <Loader2 className="h-3 w-3 animate-spin" /> : <Trash2 className="h-3 w-3" />}
          </Button>
        </div>
      ) : (
        <div className="flex gap-2">
          <Input
            data-testid={`llm-key-input-${providerKey}`}
            type="password"
            placeholder={`${meta.keyPrefix}...`}
            value={inputKey}
            onChange={(e) => setInputKey(e.target.value)}
            onKeyDown={(e) => { if (e.key === 'Enter') submit(); }}
            className="text-xs font-mono rounded-sm"
          />
          <Button
            data-testid={`llm-key-save-${providerKey}`}
            size="sm"
            onClick={submit}
            disabled={savingKey === providerKey || !inputKey.trim()}
            className="rounded-sm"
          >
            {savingKey === providerKey ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Key className="h-3.5 w-3.5 mr-1" />}
            Connect
          </Button>
          {editing && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => { setEditing(false); setInputKey(''); }}
              className="rounded-sm"
            >
              Cancel
            </Button>
          )}
        </div>
      )}
    </Card>
  );
}

export default function SettingsPage({ user, setUser }) {
  const navigate = useNavigate();
  const [me, setMe] = useState(user || null);
  const [savingKey, setSavingKey] = useState(null);
  const [clearingKey, setClearingKey] = useState(null);
  const [savingPref, setSavingPref] = useState(false);
  const [testingKey, setTestingKey] = useState(null);

  useEffect(() => {
    axios.get(`${API}/auth/me`, getAuthHeaders())
      .then((r) => {
        setMe(r.data);
        if (setUser) setUser(r.data);
      })
      .catch(() => {});
  }, [setUser]);

  const saveKey = async (provider, apiKey) => {
    setSavingKey(provider);
    try {
      const r = await axios.put(
        `${API}/auth/me/${provider}-key`,
        { api_key: apiKey },
        getAuthHeaders(),
      );
      setMe(r.data);
      if (setUser) setUser(r.data);
      toast.success(`${PROVIDER_META[provider].label} key saved`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save key');
    } finally {
      setSavingKey(null);
    }
  };

  const clearKey = async (provider) => {
    if (!window.confirm(`Remove your ${PROVIDER_META[provider].label} key? Agent calls will fall back to the DLP-managed key with a daily quota.`)) return;
    setClearingKey(provider);
    try {
      const r = await axios.delete(`${API}/auth/me/${provider}-key`, getAuthHeaders());
      setMe(r.data);
      if (setUser) setUser(r.data);
      toast.success('Key removed');
    } catch (error) {
      toast.error('Could not clear key');
    } finally {
      setClearingKey(null);
    }
  };

  const testKey = async (provider) => {
    setTestingKey(provider);
    try {
      const r = await axios.post(
        `${API}/auth/me/${provider}-key/test`,
        {},
        getAuthHeaders(),
      );
      if (r.data?.connected) toast.success(`${PROVIDER_META[provider].label} connection verified without generating text`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Connection test failed');
    } finally {
      setTestingKey(null);
    }
  };

  const setPreferred = async (provider) => {
    setSavingPref(true);
    try {
      const r = await axios.put(
        `${API}/auth/me/preferred-provider`,
        { provider },
        getAuthHeaders(),
      );
      setMe(r.data);
      if (setUser) setUser(r.data);
      toast.success(`Preferred provider: ${PROVIDER_META[provider].label}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not update preference');
    } finally {
      setSavingPref(false);
    }
  };

  const preferred = me?.preferred_llm_provider || 'anthropic';
  const anyKey = me?.has_openai_key || me?.has_anthropic_key;

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b sticky top-0 z-30 bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            data-testid="settings-back-btn"
            variant="ghost"
            size="sm"
            onClick={() => navigate('/dashboard')}
            className="rounded-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <span className="font-heading text-sm uppercase tracking-[0.18em] text-primary">
            Settings: AI Providers
          </span>
          <div className="w-20" />
        </div>
      </header>

      <div className="container mx-auto px-4 py-10 max-w-3xl">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
          <h1 className="text-3xl sm:text-4xl font-heading font-semibold mb-2">
            AI provider keys
          </h1>
          <p className="text-sm text-muted-foreground font-body mb-8 max-w-2xl">
            Connect your OpenAI or Anthropic API key and the writing agent routes
            every call through your account. There is no DLP daily quota and no
            Author Pro subscription needed. Leave both blank to use the
            DLP-managed key with the free 5 messages/day tier.
          </p>

          {/* Preferred provider */}
          <Card
            data-testid="preferred-provider-card"
            className="p-5 mb-6 bg-accent/30 border-l-4 border-l-primary"
          >
            <div className="flex items-start gap-3 mb-3">
              <span className="p-2 rounded-sm bg-primary/10 text-primary flex-shrink-0">
                <Sparkles className="h-5 w-5" />
              </span>
              <div>
                <div className="text-sm font-heading font-semibold">Preferred provider</div>
                <p className="text-xs text-muted-foreground">
                  Which model does the agent use when both keys are available?
                </p>
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {Object.entries(PROVIDER_META).map(([k, v]) => (
                <Button
                  key={k}
                  data-testid={`preferred-provider-${k}`}
                  variant={preferred === k ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setPreferred(k)}
                  disabled={savingPref || preferred === k}
                  className="rounded-sm"
                >
                  {savingPref && preferred !== k
                    ? <Loader2 className="h-3.5 w-3.5 mr-1.5 animate-spin" />
                    : preferred === k
                      ? <CheckCircle2 className="h-3.5 w-3.5 mr-1.5" />
                      : <BotMessageSquare className="h-3.5 w-3.5 mr-1.5" />}
                  {v.label}
                </Button>
              ))}
            </div>
          </Card>

          {/* Provider key cards */}
          <div className="space-y-4">
            <KeyCard
              providerKey="anthropic"
              hasKey={!!me?.has_anthropic_key}
              onSave={saveKey}
              onClear={clearKey}
              onTest={testKey}
              savingKey={savingKey}
              clearingKey={clearingKey}
              testingKey={testingKey}
            />
            <KeyCard
              providerKey="openai"
              hasKey={!!me?.has_openai_key}
              onSave={saveKey}
              onClear={clearKey}
              onTest={testKey}
              savingKey={savingKey}
              clearingKey={clearingKey}
              testingKey={testingKey}
            />
          </div>

          {/* Status banner */}
          <Card
            data-testid="settings-status-card"
            className={`p-4 mt-6 border-l-4 ${
              anyKey ? 'border-l-emerald-500 bg-emerald-50/60' : 'border-l-amber-500 bg-amber-50/60'
            }`}
          >
            <div className={`text-xs ${anyKey ? 'text-emerald-900' : 'text-amber-900'} font-body`}>
              {anyKey ? (
                <>
                  <strong>You&rsquo;re on BYO keys.</strong> Agent calls are unlimited and routed
                  through your <strong>{preferred === 'openai' && me?.has_openai_key ? 'OpenAI' : preferred === 'anthropic' && me?.has_anthropic_key ? 'Anthropic' : (me?.has_openai_key ? 'OpenAI' : 'Anthropic')}</strong> account.
                  Costs bill to your provider dashboard, not DLP.
                </>
              ) : (
                <>
                  <strong>Free tier.</strong> Agent calls use the DLP-managed key
                  with 5 messages/day. Plug in a key above for unlimited, or
                  subscribe to Author Pro.
                </>
              )}
            </div>
          </Card>

          <p className="text-[11px] text-muted-foreground font-mono uppercase tracking-widest text-center mt-8">
            Keys are stored encrypted server-side and never shared.
          </p>
        </motion.div>
      </div>
    </div>
  );
}
