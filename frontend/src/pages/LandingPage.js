import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, BookOpen, FileText, Download, Globe, Sparkles, Eye, BarChart, FileDown, Mail } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import axios from 'axios';
import { toast } from 'sonner';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_book-press/artifacts/gwdawx4q_Divine%20Leadership%20Press%20Emblem%281%29.png';

export default function LandingPage({ onLogin }) {
  const [showAuth, setShowAuth] = useState(false);
  const [isLogin, setIsLogin] = useState(true);
  const [loading, setLoading] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [resetRequested, setResetRequested] = useState(false);
  const [formData, setFormData] = useState({
    email: '',
    password: '',
    name: '',
    referral_code: '',
  });
  const [referralFromUrl, setReferralFromUrl] = useState('');

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const ref = params.get('ref');
    if (ref) {
      const cleaned = ref.trim().toUpperCase().slice(0, 16);
      setReferralFromUrl(cleaned);
      setFormData((p) => ({ ...p, referral_code: cleaned }));
      // Auto-open the register tab when arriving via a referral link
      setIsLogin(false);
      setShowAuth(true);
    }
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const endpoint = isLogin ? '/auth/login' : '/auth/register';
      const payload = isLogin
        ? { email: formData.email, password: formData.password }
        : {
            email: formData.email,
            password: formData.password,
            name: formData.name,
            ...(formData.referral_code ? { referral_code: formData.referral_code } : {}),
          };

      const response = await axios.post(`${API}${endpoint}`, payload, { withCredentials: true });

      toast.success(isLogin ? 'Welcome back!' : 'Account created successfully!');
      onLogin(response.data.token, response.data.user);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const handleForgotPassword = async (e) => {
    e.preventDefault();
    setLoading(true);
    try {
      const response = await axios.post(`${API}/auth/forgot-password`, {
        email: formData.email,
      });
      setResetRequested(true);
      toast.success(response.data.message);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not request a reset link');
    } finally {
      setLoading(false);
    }
  };

  const features = [
    {
      icon: <FileText className="w-8 h-8" />,
      title: 'Professional Editing',
      description: 'Full-featured rich text editor with track changes, comments, and version history'
    },
    {
      icon: <Download className="w-8 h-8" />,
      title: 'Multi-Format Export',
      description: 'Convert to 6×9, ePub, magazine format, and print-ready PDFs'
    },
    {
      icon: <Globe className="w-8 h-8" />,
      title: 'Publishing Integration',
      description: 'Direct publishing to Amazon KDP, LULU, and other platforms'
    },
    {
      icon: <Eye className="w-8 h-8" />,
      title: 'Live Preview',
      description: 'See your formatted book in real-time before export'
    },
    {
      icon: <Sparkles className="w-8 h-8" />,
      title: 'ISBN Management',
      description: 'Comprehensive metadata and ISBN tracking for your publications'
    },
    {
      icon: <BarChart className="w-8 h-8" />,
      title: 'Version Control',
      description: 'Track every change with complete version history'
    }
  ];

  return (
    <div className="min-h-screen" style={{ background: 'linear-gradient(135deg, hsl(210, 100%, 12%) 0%, hsl(210, 80%, 18%) 100%)' }}>
      {/* Hero Section */}
      <div className="relative overflow-hidden">
        <div className="absolute inset-0 z-0 opacity-10">
          <div
            className="w-full h-full"
            style={{
              backgroundImage: 'url(https://images.unsplash.com/photo-1672396306113-4641c9a9c97e?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njl8MHwxfHNlYXJjaHwxfHxhbnRpcXVlJTIwbGlicmFyeSUyMGJvb2tzJTIwYWVzdGhldGljfGVufDB8fHx8MTc2NTg0NTI2M3ww&ixlib=rb-4.1.0&q=85)',
              backgroundSize: 'cover',
              backgroundPosition: 'center'
            }}
          />
        </div>
        <div className="relative z-10 container mx-auto px-4 py-24 lg:py-32">
          <div className="max-w-4xl mx-auto text-center">
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="flex flex-col items-center"
            >
              <img src={LOGO_URL} alt="Divine Leadership Press" className="w-32 h-32 mb-6" />
              <h1 className="text-5xl sm:text-6xl lg:text-7xl font-heading font-bold mb-6 tracking-tightest" style={{ color: 'hsl(40, 30%, 92%)' }}>
                Divine Leadership Press
              </h1>
              <p className="text-lg sm:text-xl mb-8 font-body max-w-2xl mx-auto" style={{ color: 'hsl(40, 20%, 85%)' }}>
                Professional book publishing and formatting platform. Transform your manuscripts into beautifully formatted books ready for print and digital distribution.
              </p>
              <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
                <Button
                  data-testid="get-started-btn"
                  size="lg"
                  className="rounded-sm text-base px-8 py-6 hover:scale-105 transition-transform duration-300 bg-[hsl(40,30%,92%)] text-[hsl(210,100%,12%)] hover:bg-[hsl(40,35%,88%)]"
                  onClick={() => setShowAuth(true)}
                >
                  <BookOpen className="mr-2 h-5 w-5" />
                  Start Publishing
                </Button>
                <Button
                  data-testid="learn-more-btn"
                  variant="outline"
                  size="lg"
                  className="rounded-sm text-base px-8 py-6 border-[hsl(40,30%,92%)] text-[hsl(40,30%,92%)] hover:bg-[hsl(40,30%,92%)]/10 hover:scale-105 transition-transform duration-300"
                  onClick={() => document.getElementById('features').scrollIntoView({ behavior: 'smooth' })}
                >
                  Learn More
                </Button>
              </div>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div id="features" className="py-20 px-4 bg-background">
        <div className="container mx-auto max-w-7xl">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
            viewport={{ once: true }}
            className="text-center mb-16"
          >
            <p className="text-sm uppercase tracking-widest text-primary mb-4 font-body font-medium">Features</p>
            <h2 className="text-4xl lg:text-5xl font-heading font-bold mb-4 tracking-tight">
              Century-Old Expertise,<br />Modern Technology
            </h2>
            <p className="text-muted-foreground text-lg max-w-2xl mx-auto font-body">
              Every tool a professional publisher needs, from manuscript to market
            </p>
          </motion.div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            {features.map((feature, idx) => (
              <motion.div
                key={idx}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: idx * 0.1 }}
                viewport={{ once: true }}
              >
                <Card data-testid={`feature-card-${idx}`} className="p-8 h-full border hover:shadow-lg transition-shadow duration-300 bg-card/50 backdrop-blur-sm">
                  <div className="text-primary mb-4">{feature.icon}</div>
                  <h3 className="text-xl font-heading font-semibold mb-3">{feature.title}</h3>
                  <p className="text-muted-foreground font-body leading-relaxed">{feature.description}</p>
                </Card>
              </motion.div>
            ))}
          </div>
        </div>
      </div>

      {/* CTA Section */}
      <div className="py-20 px-4" style={{ background: 'hsl(210, 100%, 15%)' }}>
        <div className="container mx-auto max-w-4xl text-center">
          <motion.div
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            transition={{ duration: 0.6 }}
            viewport={{ once: true }}
          >
            <h2 className="text-3xl lg:text-5xl font-heading font-bold mb-6 tracking-tight" style={{ color: 'hsl(40, 30%, 92%)' }}>
              Ready to Publish Your Book?
            </h2>
            <p className="text-lg mb-8 font-body" style={{ color: 'hsl(40, 20%, 80%)' }}>
              Join authors and publishers who trust Divine Leadership Press
            </p>
            <Button
              data-testid="cta-get-started-btn"
              size="lg"
              className="rounded-sm text-base px-8 py-6 hover:scale-105 transition-transform duration-300 bg-[hsl(40,30%,92%)] text-[hsl(210,100%,12%)] hover:bg-[hsl(40,35%,88%)]"
              onClick={() => setShowAuth(true)}
            >
              Get Started Now
            </Button>
          </motion.div>
        </div>
      </div>

      {/* Footer */}
      <footer
        data-testid="landing-footer"
        className="border-t border-white/10 bg-black/20 backdrop-blur-sm"
      >
        <div className="container mx-auto px-4 py-10 max-w-6xl">
          <div className="grid grid-cols-1 sm:grid-cols-[auto_1fr_auto] gap-6 items-center">
            <div className="flex items-center gap-3">
              <img
                src={LOGO_URL}
                alt="Divine Leadership Press"
                className="h-10 w-10 object-contain"
              />
              <div>
                <div className="font-heading text-sm text-white uppercase tracking-[0.18em]">
                  Divine Leadership Press
                </div>
                <div className="text-[10px] font-mono uppercase tracking-widest text-white/60">
                  Est. 1925 · A Century of Letterpress Craft
                </div>
              </div>
            </div>
            <div className="text-center sm:text-left text-xs text-white/70 font-body max-w-md sm:ml-6">
              Before you subscribe — download the full 8-page publisher&rsquo;s user
              guide covering use cases, market positioning, feature list, FAQ,
              and troubleshooting.
            </div>
            <a
              data-testid="landing-pdf-guide-btn"
              href="/dlp-user-guide.pdf"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 h-10 px-4 rounded-sm border border-cream/30 text-cream bg-white/5 hover:bg-white hover:text-primary text-sm font-body transition-colors"
              style={{ color: '#f5efe0' }}
            >
              <FileDown className="h-4 w-4" />
              Download PDF Guide
            </a>
          </div>
          <div className="mt-8 pt-6 border-t border-white/10 flex flex-col sm:flex-row items-center justify-between gap-3 text-[11px] font-mono uppercase tracking-widest text-white/50">
            <span>© {new Date().getFullYear()} Divine Leadership Press. All rights reserved.</span>
            <span>Manuscript to marketplace, in one workroom.</span>
          </div>
        </div>
      </footer>

      {/* Auth Modal */}
      {showAuth && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm z-50 flex items-center justify-center p-4" onClick={() => setShowAuth(false)}>
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.2 }}
            onClick={(e) => e.stopPropagation()}
          >
            <Card data-testid="auth-modal" className="w-full max-w-md p-8 bg-card/95 backdrop-blur-md">
              {forgotMode ? (
                <div data-testid="forgot-password-panel">
                  <div className="mb-6 flex flex-col items-center">
                    <span className="h-14 w-14 mb-4 border bg-primary/5 flex items-center justify-center">
                      <Mail className="h-6 w-6 text-primary" />
                    </span>
                    <h2 className="text-2xl font-heading font-bold mb-2">Reset your password</h2>
                    <p data-testid="forgot-password-help" className="text-sm text-muted-foreground font-body text-center">
                      Enter your account email. We&rsquo;ll send a secure, single-use reset link.
                    </p>
                  </div>
                  {resetRequested ? (
                    <div data-testid="forgot-password-confirmation" className="space-y-4">
                      <div className="border-l-4 border-l-emerald-600 bg-emerald-50 p-4 text-sm text-emerald-900">
                        If an account exists for that email, a reset link is on its way. Check your inbox and spam folder.
                      </div>
                      <Button
                        data-testid="forgot-password-back-button"
                        type="button"
                        variant="outline"
                        className="w-full rounded-sm"
                        onClick={() => { setForgotMode(false); setResetRequested(false); }}
                      >
                        <ArrowLeft className="h-4 w-4 mr-2" /> Back to sign in
                      </Button>
                    </div>
                  ) : (
                    <form data-testid="forgot-password-form" onSubmit={handleForgotPassword} className="space-y-4">
                      <div>
                        <Label htmlFor="forgot-email">Email</Label>
                        <Input
                          id="forgot-email"
                          data-testid="forgot-password-email-input"
                          type="email"
                          placeholder="you@example.com"
                          value={formData.email}
                          onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                          required
                        />
                      </div>
                      <Button data-testid="forgot-password-submit-button" type="submit" className="w-full rounded-sm" disabled={loading}>
                        {loading ? 'Sending secure link…' : 'Send reset link'}
                      </Button>
                      <Button
                        data-testid="forgot-password-cancel-button"
                        type="button"
                        variant="ghost"
                        className="w-full rounded-sm"
                        onClick={() => setForgotMode(false)}
                      >
                        <ArrowLeft className="h-4 w-4 mr-2" /> Back to sign in
                      </Button>
                    </form>
                  )}
                </div>
              ) : (
                <>
                  <div className="mb-6 flex flex-col items-center">
                    <img src={LOGO_URL} alt="Divine Leadership Press" className="w-20 h-20 mb-4" />
                    <h2 className="text-2xl font-heading font-bold mb-2">
                      {isLogin ? 'Welcome Back' : 'Create Account'}
                    </h2>
                    <p className="text-muted-foreground font-body text-center">
                      {isLogin ? 'Sign in to your account' : 'Start your publishing journey'}
                    </p>
                  </div>
                  <Tabs value={isLogin ? 'login' : 'register'} onValueChange={(v) => setIsLogin(v === 'login')}>
                    <TabsList className="grid w-full grid-cols-2 mb-6">
                      <TabsTrigger data-testid="login-tab" value="login">Login</TabsTrigger>
                      <TabsTrigger data-testid="register-tab" value="register">Register</TabsTrigger>
                    </TabsList>
                  <TabsContent value="login" className="space-y-4">
                    <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <Label htmlFor="login-email">Email</Label>
                      <Input
                        id="login-email"
                        data-testid="login-email-input"
                        type="email"
                        placeholder="you@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="login-password">Password</Label>
                      <Input
                        id="login-password"
                        data-testid="login-password-input"
                        type="password"
                        placeholder="••••••••"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        required
                      />
                    </div>
                    <Button data-testid="login-submit-btn" type="submit" className="w-full rounded-sm" disabled={loading}>
                      {loading ? 'Signing in...' : 'Sign In'}
                    </Button>
                    </form>
                    <Button
                      data-testid="forgot-password-link"
                      type="button"
                      variant="link"
                      className="w-full h-auto p-0 text-sm"
                      onClick={() => { setForgotMode(true); setResetRequested(false); }}
                    >
                      Forgot your password?
                    </Button>
                  </TabsContent>

                  <TabsContent value="register" className="space-y-4">
                    <form onSubmit={handleSubmit} className="space-y-4">
                    <div>
                      <Label htmlFor="register-name">Name</Label>
                      <Input
                        id="register-name"
                        data-testid="register-name-input"
                        type="text"
                        placeholder="Your name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        required={!isLogin}
                      />
                    </div>
                    <div>
                      <Label htmlFor="register-email">Email</Label>
                      <Input
                        id="register-email"
                        data-testid="register-email-input"
                        type="email"
                        placeholder="you@example.com"
                        value={formData.email}
                        onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="register-password">Password</Label>
                      <Input
                        id="register-password"
                        data-testid="register-password-input"
                        type="password"
                        placeholder="••••••••"
                        value={formData.password}
                        onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                        required
                      />
                    </div>
                    <div>
                      <Label htmlFor="register-referral">
                        Referral code <span className="text-muted-foreground font-normal">(optional)</span>
                      </Label>
                      <Input
                        id="register-referral"
                        data-testid="register-referral-input"
                        type="text"
                        placeholder="e.g. ABC12345"
                        value={formData.referral_code}
                        onChange={(e) => setFormData({ ...formData, referral_code: e.target.value.toUpperCase().slice(0, 16) })}
                        className="font-mono"
                      />
                      {referralFromUrl && (
                        <p className="text-[11px] text-emerald-700 mt-1">
                          Invited by code <span className="font-mono font-semibold">{referralFromUrl}</span>
                        </p>
                      )}
                    </div>
                    <Button data-testid="register-submit-btn" type="submit" className="w-full rounded-sm" disabled={loading}>
                      {loading ? 'Creating account...' : 'Create Account'}
                    </Button>
                    </form>
                  </TabsContent>
                  </Tabs>
                </>
              )}
            </Card>
          </motion.div>
        </div>
      )}
    </div>
  );
}
