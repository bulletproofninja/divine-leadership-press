import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import {
  ArrowLeft, Upload, FileText, ImageIcon, BookOpen, Sparkles, ScanSearch,
  Mic, Headphones, FileDown, History, MessageSquare, Layers, Globe, FileType,
  Lightbulb, Shield, HelpCircle, Share2, Copy, Users, Trophy, Award, CreditCard, ExternalLink, Loader2,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_book-press/artifacts/gwdawx4q_Divine%20Leadership%20Press%20Emblem%281%29.png';

const getAuthHeaders = () => {
  const token = localStorage.getItem('token');
  return token ? { headers: { Authorization: `Bearer ${token}` } } : { headers: {} };
};

const SECTIONS = [
  {
    id: 'getting-started',
    title: 'Getting Started',
    icon: BookOpen,
    blurb: 'Account, dashboard, and your first manuscript.',
    body: [
      'Register an account from the landing page. Your manuscripts are private to you — only you can see, edit, export, or delete them.',
      'The Dashboard is your library. Each book card shows a cover thumbnail (when uploaded), the current trim size, last-edited date, version & comment counts, and a six-step **Publication Pipeline** badge row.',
      'Start a new book with **+ New Document**, or import an existing one with **Upload**.',
    ],
  },
  {
    id: 'pipeline',
    title: 'Publication Pipeline',
    icon: Layers,
    blurb: 'Six visual milestones from manuscript to marketplace.',
    body: [
      'Every book is tracked across six steps: **Manuscript → Metadata → Cover → PDF → ePub → Audiobook**. Each badge turns green when its requirement is met.',
      'The same six-step strip appears at the top of the Editor sidebar so you always know what is left to do before you can submit to Amazon KDP, Lulu, or any other store.',
      '“Metadata” needs both an Author and a Description filled in (Book Setup panel). “Cover” needs an uploaded image. “PDF / ePub / Audiobook” turn on the moment you generate or upload each format.',
    ],
  },
  {
    id: 'upload',
    title: 'Upload & Import',
    icon: Upload,
    blurb: 'Bring an existing manuscript into DLP.',
    body: [
      'Supported imports: **.docx** (preserves headings, bold, italic, underline, lists, alignment) and **.txt** (paragraph-aware).',
      '**Apple Pages (.pages)** files are not directly supported. Open the file in Pages, choose **File → Export To → Word (.docx)**, then upload the resulting .docx.',
      'After import, the manuscript opens in the editor with all formatting intact. You can keep editing in the rich-text editor or run the AI tools immediately.',
    ],
  },
  {
    id: 'editor',
    title: 'The Editor',
    icon: FileText,
    blurb: 'Professional writing surface with versioning & comments.',
    body: [
      'The editor uses a classic serif typeface and a wide writing column. Headings, bold/italic/underline, lists, quotes, and alignment all behave the way they will in your printed book.',
      '**Every Save creates a new version**. The History tab lets you scrub through past versions and restore any of them. Your manuscript is never lost.',
      '**Comments** can be attached to any selected text — useful when working with co-authors or editors.',
    ],
  },
  {
    id: 'book-setup',
    title: 'Book Setup (Cover + Metadata)',
    icon: ImageIcon,
    blurb: 'Cover art and KDP-ready metadata.',
    body: [
      '**Cover image**: upload a JPG, PNG, or WebP up to 10 MB. KDP recommends 1600×2560 px. Use **Replace Cover** to swap it; **Remove** to clear it; **Download Cover as PDF** to generate a KDP-trim-sized PDF for paperback submission.',
      '**Metadata fields**: Author, Subtitle, Description, ISBN, Language, Category (e.g. *Self-Help > Leadership*), Keywords (comma-separated), Publisher. Click **Save Book Details** to persist.',
      'The description doubles as the Amazon listing copy and feeds the AI tools (blurb generator, synopsis) for stylistic consistency.',
    ],
  },
  {
    id: 'editors-desk',
    title: "Editor's Desk — Full Copy-Edit",
    icon: ScanSearch,
    blurb: 'Grammar, punctuation, run-ons, passive voice & more.',
    body: [
      'Pick a style guide (**Chicago Manual of Style** — book/literary default — or **AP**, **MLA**, **DLP House**). Click **Run Full Edit**.',
      'Claude Sonnet 4.5 scans the manuscript and returns specific issues across 11 categories: grammar, punctuation, spelling, run-on sentences, comma splices, passive voice, wordy phrases, repetition, consistency, clarity, and tone.',
      'Each issue has a severity badge — **must fix**, **suggested**, or **stylistic** — and shows the exact original text alongside the suggested replacement plus a one-line rationale.',
      '**Accept** applies the fix inline (preserving bold/italic). **Reject** dismisses it. **Accept All / Reject All** handle the entire list at once. Filter the list by severity to focus on the highest-impact issues first.',
      'The same panel shows a **readability dashboard**: Flesch-Kincaid grade level, average sentence length, passive voice %, adverb density, and a warning if your longest sentence runs over 35 words.',
    ],
  },
  {
    id: 'ai-polish',
    title: 'AI Editorial Polish',
    icon: Sparkles,
    blurb: 'Five Claude tools for prose, blurbs, and outlines.',
    body: [
      '**Tighten Prose** — rewrites the manuscript for concision while preserving your voice (about 15–25% shorter).',
      '**Improve Clarity** — rewrites for readability, target Flesch-Kincaid grade ~8. Keeps all factual claims and paragraph structure.',
      '**Back-Cover Blurb** — generates a 130–160 word literary marketing blurb based on your book content.',
      '**Suggest Chapter Titles** — proposes a short, evocative title for each H1 chapter in the manuscript.',
      '**Generate Synopsis** — produces a one-page (350–500 word) synopsis ready for query letters and KDP listings.',
      'All five present a **preview** with **Replace Manuscript / Append to Manuscript / Copy / Discard** controls — nothing changes until you choose to apply it.',
    ],
  },
  {
    id: 'dictation',
    title: 'Voice Dictation',
    icon: Mic,
    blurb: 'Speak your book. Whisper transcribes with auto-punctuation.',
    body: [
      'Click **Dictate** in the editor toolbar. Grant microphone permission when prompted. Click **Stop** to send the recording to OpenAI Whisper.',
      'Whisper returns text with proper punctuation, capitalisation, and paragraph breaks. The transcript is inserted **at your cursor position**, with a leading space if you are mid-sentence.',
      'Toggle **Continuous** to record indefinitely in 30-second segments — Whisper transcribes each segment as it ends while the next segment is already recording, so there are no gaps.',
      'The **Dictation History** sidebar panel shows every chunk with a timestamp and an **Undo** button. Undo removes that exact chunk from the manuscript (search-and-remove), useful when you mis-spoke.',
    ],
  },
  {
    id: 'voice-memos',
    title: 'Voice Memos',
    icon: Mic,
    blurb: 'Audio notes attached to specific paragraphs.',
    body: [
      'Voice Memos are raw audio annotations — not transcribed by default. Use them to capture an idea, a citation, or a re-write suggestion while writing.',
      'Click **Record Voice Memo**, speak, then **Stop & Save**. The memo is anchored to the paragraph your cursor was on (shown as ¶N on the card).',
      'Each memo card has: a play button, **Transcribe & Insert** (calls Whisper and inserts the text at the cursor, then caches the transcript), and a delete button.',
      'Cached transcripts are reused on subsequent inserts — you only pay once per memo.',
    ],
  },
  {
    id: 'audio-studio',
    title: 'Audio Studio — Audiobook Generation',
    icon: Headphones,
    blurb: 'Three ways to give your book a voice.',
    body: [
      '**OpenAI TTS HD** (included): pick from 9 narrator voices and a speed slider (0.5×–2.0×). Click **Read Aloud (Preview)** to audition the first 1,500 characters, or **Generate Audiobook (MP3)** to render the full book.',
      '**ElevenLabs** (your own API key): the premium tier. Save your ElevenLabs key in the panel — DLP then lists your full ElevenLabs voice library (stock + any custom voices you have cloned on the ElevenLabs dashboard). Paste a custom Voice ID to use a cloned voice. **Preview** auditions; **Generate Audiobook (ElevenLabs)** renders.',
      '**Uploaded** mode: already have an audiobook? Upload an MP3/WAV/M4A/OGG/FLAC file (up to 200 MB) and DLP will play it back in-browser. The Audiobook pipeline badge turns green.',
      'Audiobooks are limited to ~17,000 words per render (a single short novel or a chapter of a longer work). Split larger books into chapters and render each separately.',
    ],
  },
  {
    id: 'export',
    title: 'Export — PDF, ePub, Cover PDF',
    icon: FileDown,
    blurb: 'Production-ready files for KDP, Lulu, and digital stores.',
    body: [
      '**PDF**: pick any of the 12 standard KDP trim sizes (5×8 through 8.5×11). DLP renders a publishing-grade PDF with a title page, mirrored binding margins, page numbers, and a classic Times serif typeface.',
      '**ePub**: chapter-aware (auto-splits on H1 headings) with serif CSS that displays cleanly on Kindle, Kobo, Apple Books, and any other reader.',
      '**Cover PDF**: once a cover image is uploaded, click **Download Cover as PDF** in Book Setup. DLP scales your image to fully cover the current trim size (cover-crop) and produces a single-page PDF ready for paperback submission.',
      '**Generic Image → PDF**: any JPG/PNG/WebP can be converted to a PDF at any trim — useful for separate front-cover, back-cover, or spine submissions.',
    ],
  },
  {
    id: 'privacy',
    title: 'Privacy & Your Data',
    icon: Shield,
    blurb: 'Where your manuscript lives, and who can see it.',
    body: [
      'Manuscripts, comments, versions, voice memos, cover images, and uploaded audiobooks are stored on your DLP account and are visible only to you.',
      'AI calls (Claude, OpenAI Whisper, OpenAI TTS) and ElevenLabs calls send the text/audio of the request to the relevant provider — they do not see your manuscript wholesale unless you explicitly trigger a tool on it.',
      'You can delete any manuscript from the Dashboard at any time. Deletion removes the document, versions, comments, memos, cover, and audio files.',
    ],
  },
  {
    id: 'shortcuts',
    title: 'Tips & Best Practices',
    icon: Lightbulb,
    blurb: 'Get the most out of DLP.',
    body: [
      '**Run Editor\'s Desk before exporting.** A single full edit pass catches dozens of issues that compound across a book-length manuscript.',
      '**Set metadata early.** Author, description, category, and keywords all feed the AI tools (blurb, synopsis) so they sound consistent with your book.',
      '**Use Continuous Dictation for first drafts**, then run AI Editorial Polish → Editor\'s Desk to clean up. The voice-first authoring loop is real.',
      '**Save often.** Every save is a recoverable version. You cannot lose work to a bad edit.',
      '**Audiobook before launch.** Even if you don\'t publish an audiobook, the Read Aloud preview catches awkward phrasing the eye can miss.',
    ],
  },
];


export default function HelpPage() {
  const navigate = useNavigate();
  const [referral, setReferral] = useState(null);
  const [copying, setCopying] = useState(false);
  const [leaderboard, setLeaderboard] = useState([]);
  const [myBadge, setMyBadge] = useState(null);
  const [programSettings, setProgramSettings] = useState(null);
  const [earnings, setEarnings] = useState(null);
  const [connect, setConnect] = useState(null);
  const [connectLoading, setConnectLoading] = useState(false);
  const isAuthed = !!localStorage.getItem('token');

  useEffect(() => {
    axios.get(`${API}/referrals/leaderboard?limit=10`)
      .then((r) => setLeaderboard(r.data.leaderboard || []))
      .catch(() => setLeaderboard([]));
    axios.get(`${API}/affiliate/settings`)
      .then((r) => setProgramSettings(r.data))
      .catch(() => setProgramSettings(null));
    if (!isAuthed) return;
    axios.get(`${API}/auth/me/referrals`, getAuthHeaders())
      .then((r) => setReferral(r.data))
      .catch(() => setReferral(null));
    axios.get(`${API}/auth/me/badge`, getAuthHeaders())
      .then((r) => setMyBadge(r.data))
      .catch(() => setMyBadge(null));
    axios.get(`${API}/billing/commissions`, getAuthHeaders())
      .then((r) => setEarnings(r.data))
      .catch(() => setEarnings(null));
    axios.get(`${API}/affiliate/connect/status`, getAuthHeaders())
      .then((r) => setConnect(r.data))
      .catch(() => setConnect(null));
  }, [isAuthed]);

  const onboardPayouts = async () => {
    setConnectLoading(true);
    try {
      const r = await axios.post(
        `${API}/affiliate/connect/onboard`,
        { origin_url: window.location.origin },
        getAuthHeaders(),
      );
      if (r.data?.url) {
        window.location.href = r.data.url;
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not start onboarding');
      setConnectLoading(false);
    }
  };

  const openConnectDashboard = async () => {
    setConnectLoading(true);
    try {
      const r = await axios.post(
        `${API}/affiliate/connect/dashboard-link`,
        {},
        getAuthHeaders(),
      );
      if (r.data?.url) {
        window.open(r.data.url, '_blank');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not open Stripe dashboard');
    } finally {
      setConnectLoading(false);
    }
  };

  const referralUrl = referral
    ? `${window.location.origin}/?ref=${referral.referral_code}`
    : '';

  const copyReferralLink = async () => {
    if (!referralUrl) return;
    setCopying(true);
    try {
      await navigator.clipboard.writeText(referralUrl);
      toast.success('Referral link copied');
    } catch (_) {
      toast.error('Could not copy — copy manually');
    } finally {
      setCopying(false);
    }
  };

  const shareNative = async () => {
    if (!referralUrl) return;
    if (navigator.share) {
      try {
        await navigator.share({
          title: 'Divine Leadership Press',
          text: 'I\'m using Divine Leadership Press to write and publish my book. Join me:',
          url: referralUrl,
        });
      } catch (_) {/* user cancelled */}
    } else {
      copyReferralLink();
    }
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b sticky top-0 z-30 bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <Button
            data-testid="help-back-btn"
            variant="ghost"
            size="sm"
            onClick={() => navigate(-1)}
            className="rounded-sm"
          >
            <ArrowLeft className="h-4 w-4 mr-2" /> Back
          </Button>
          <div className="flex items-center gap-3">
            <img src={LOGO_URL} alt="Divine Leadership Press" className="h-8 w-8 object-contain" />
            <span className="font-heading text-sm uppercase tracking-[0.18em] text-primary">
              Help & Documentation
            </span>
          </div>
          <a
            data-testid="download-user-guide-btn"
            href="/dlp-user-guide.pdf"
            download
            className="inline-flex items-center gap-1.5 h-9 px-3 rounded-sm border text-xs font-body hover:bg-primary hover:text-primary-foreground transition-colors"
            title="Download the full PDF user guide"
          >
            <ExternalLink className="h-3.5 w-3.5" />
            <span className="hidden sm:inline">PDF Guide</span>
          </a>
        </div>
      </header>

      <div className="container mx-auto px-4 py-12 grid grid-cols-1 lg:grid-cols-[260px_1fr] gap-12">
        {/* Section navigation */}
        <aside className="hidden lg:block">
          <div className="sticky top-28 space-y-1" data-testid="help-toc">
            <h2 className="text-xs uppercase tracking-[0.18em] font-mono text-muted-foreground mb-3">
              Contents
            </h2>
            {SECTIONS.map((section) => (
              <a
                key={section.id}
                href={`#${section.id}`}
                data-testid={`help-toc-${section.id}`}
                className="block py-1.5 px-2 text-sm font-body text-foreground hover:text-primary hover:bg-accent/40 rounded-sm transition-colors"
              >
                {section.title}
              </a>
            ))}
            {isAuthed && (
              <a
                href="#share"
                data-testid="help-toc-share"
                className="block py-1.5 px-2 text-sm font-body text-primary hover:bg-accent/40 rounded-sm transition-colors mt-2 pt-2 border-t"
              >
                Share & Refer
              </a>
            )}
            {leaderboard.length > 0 && (
              <a
                href="#leaderboard"
                data-testid="help-toc-leaderboard"
                className="block py-1.5 px-2 text-sm font-body text-amber-700 hover:bg-accent/40 rounded-sm transition-colors"
              >
                Top Inviters
              </a>
            )}
          </div>
        </aside>

        {/* Main content */}
        <main className="space-y-12 max-w-3xl">
          {/* Intro */}
          <motion.section
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            data-testid="help-intro"
          >
            <div className="flex items-center gap-3 mb-3">
              <HelpCircle className="h-6 w-6 text-primary" />
              <span className="text-xs uppercase tracking-[0.18em] font-mono text-muted-foreground">
                Welcome to Divine Leadership Press
              </span>
            </div>
            <h1 className="text-4xl sm:text-5xl font-heading font-semibold leading-tight mb-4">
              Everything you need to write, edit, narrate, and publish a book.
            </h1>
            <p className="text-base text-muted-foreground font-body leading-relaxed">
              DLP is a manuscript-to-marketplace pipeline built for serious authors.
              Below is a tour of every major capability — from importing a Word document
              to generating a finished MP3 audiobook ready for ACX / Audible. Skim the
              contents on the left or scroll straight through.
            </p>
          </motion.section>

          {/* Sections */}
          {SECTIONS.map((section, idx) => {
            const Icon = section.icon;
            return (
              <motion.section
                key={section.id}
                id={section.id}
                data-testid={`help-section-${section.id}`}
                initial={{ opacity: 0, y: 10 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-100px' }}
                transition={{ duration: 0.4, delay: 0.05 }}
                className="scroll-mt-28"
              >
                <div className="flex items-center gap-3 mb-2">
                  <div className="p-2 rounded-sm bg-primary/10 text-primary">
                    <Icon className="h-5 w-5" />
                  </div>
                  <span className="text-[10px] uppercase tracking-[0.22em] font-mono text-muted-foreground">
                    {String(idx + 1).padStart(2, '0')} · Section
                  </span>
                </div>
                <h2 className="text-2xl sm:text-3xl font-heading font-semibold mb-1">
                  {section.title}
                </h2>
                <p className="text-sm text-muted-foreground italic font-body mb-5">
                  {section.blurb}
                </p>
                <Card className="p-6 bg-card/60 backdrop-blur-sm border-l-4 border-l-primary/70 rounded-sm">
                  <div className="space-y-3 text-base font-body leading-relaxed">
                    {section.body.map((para, i) => (
                      <p
                        key={i}
                        data-testid={`help-body-${section.id}-${i}`}
                        dangerouslySetInnerHTML={{
                          __html: para.replace(
                            /\*\*(.+?)\*\*/g,
                            '<strong class="font-semibold text-foreground">$1</strong>'
                          ),
                        }}
                      />
                    ))}
                  </div>
                </Card>
              </motion.section>
            );
          })}

          {/* Share & Refer */}
          {isAuthed && referral && (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.4 }}
              data-testid="referral-card"
              className="scroll-mt-28"
              id="share"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-sm bg-primary/10 text-primary">
                  <Share2 className="h-5 w-5" />
                </div>
                <span className="text-[10px] uppercase tracking-[0.22em] font-mono text-muted-foreground">
                  Bonus · Share & Refer
                </span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-heading font-semibold mb-1">
                Invite an Author to Divine Leadership Press
              </h2>
              <p className="text-sm text-muted-foreground italic font-body mb-5">
                Every writer you know has a book in them. Send them your personal invite link.
              </p>
              <Card className="p-6 bg-card/60 backdrop-blur-sm border-l-4 border-l-primary/70 rounded-sm">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                  <div className="p-3 rounded-sm border bg-accent/30 text-center">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                      Your Referral Code
                    </div>
                    <div
                      data-testid="referral-code-display"
                      className="text-2xl font-heading font-semibold tracking-wider text-primary mt-1"
                    >
                      {referral.referral_code}
                    </div>
                  </div>
                  <div className="p-3 rounded-sm border bg-accent/30 text-center">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                      Authors You've Invited
                    </div>
                    <div data-testid="referral-total-count" className="text-2xl font-heading font-semibold mt-1 flex items-center justify-center gap-2">
                      <Users className="h-5 w-5 text-primary" />
                      {referral.total_referred}
                    </div>
                  </div>
                </div>

                <div className="mb-3">
                  <label className="text-xs uppercase tracking-wider font-mono text-muted-foreground">
                    Share this link
                  </label>
                  <div className="mt-1 flex gap-2">
                    <Input
                      data-testid="referral-link-input"
                      value={referralUrl}
                      readOnly
                      onFocus={(e) => e.target.select()}
                      className="rounded-sm font-mono text-xs flex-1"
                    />
                    <Button
                      data-testid="referral-copy-btn"
                      variant="outline"
                      size="sm"
                      className="rounded-sm"
                      disabled={copying}
                      onClick={copyReferralLink}
                    >
                      <Copy className="h-3.5 w-3.5 mr-1" /> Copy
                    </Button>
                    <Button
                      data-testid="referral-share-btn"
                      size="sm"
                      className="rounded-sm"
                      onClick={shareNative}
                    >
                      <Share2 className="h-3.5 w-3.5 mr-1" /> Share
                    </Button>
                  </div>
                  <p className="text-[11px] text-muted-foreground mt-2">
                    Anyone who registers via this link will be attributed to your account.
                  </p>
                </div>

                {referral.recent && referral.recent.length > 0 && (
                  <div data-testid="referral-recent-list" className="mt-4 pt-4 border-t">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground mb-2">
                      Recent invitees
                    </div>
                    <ul className="space-y-1.5">
                      {referral.recent.slice(0, 5).map((r, i) => (
                        <li key={i} className="flex items-center justify-between text-xs font-body">
                          <span>{r.name}</span>
                          <span className="text-muted-foreground font-mono text-[10px]">
                            {r.joined_at ? new Date(r.joined_at).toLocaleDateString() : ''}
                          </span>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* User's earned badge */}
                {myBadge?.badge && (
                  <div
                    data-testid="referral-badge"
                    className="mt-4 pt-4 border-t flex items-center gap-3"
                  >
                    <div className="p-2 rounded-sm bg-amber-50 border border-amber-200 text-amber-700">
                      <Award className="h-5 w-5" />
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                        Your badge
                      </div>
                      <div className="text-sm font-heading font-semibold">
                        {myBadge.badge.label}
                      </div>
                      <div className="text-[11px] text-muted-foreground">
                        Earned for inviting {myBadge.count} author{myBadge.count === 1 ? '' : 's'}.
                      </div>
                    </div>
                  </div>
                )}

                {/* Program rules */}
                {programSettings && (
                  <div data-testid="program-rules" className="mt-4 pt-4 border-t text-[11px] text-muted-foreground">
                    <div className="uppercase tracking-wider font-mono mb-1">Program rules</div>
                    <ul className="list-disc pl-4 space-y-0.5">
                      <li>Reward type: <span className="font-medium text-foreground">{programSettings.reward_type}</span></li>
                      <li>Qualifying event: <span className="font-medium text-foreground">{programSettings.qualifying_event.replace(/_/g, ' ')}</span></li>
                      {programSettings.commission_percent > 0 && (
                        <li>Commission: <span className="font-medium text-foreground">{programSettings.commission_percent}%</span></li>
                      )}
                      {programSettings.reward_value > 0 && (
                        <li>Per qualifying invite: <span className="font-medium text-foreground">{programSettings.currency} {programSettings.reward_value}</span></li>
                      )}
                      {programSettings.notes && (
                        <li>{programSettings.notes}</li>
                      )}
                    </ul>
                  </div>
                )}
              </Card>
            </motion.section>
          )}

          {/* Affiliate earnings (private) */}
          {isAuthed && referral?.referral_code && (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.4 }}
              data-testid="earnings-card"
              className="scroll-mt-28"
              id="earnings"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-sm bg-emerald-50 border border-emerald-200 text-emerald-700">
                  <Award className="h-5 w-5" />
                </div>
                <span className="text-[10px] uppercase tracking-[0.22em] font-mono text-muted-foreground">
                  Your earnings
                </span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-heading font-semibold mb-1">
                Affiliate commissions ledger
              </h2>
              <p className="text-sm text-muted-foreground italic font-body mb-5">
                Every paid subscription from an author you invited.
              </p>
              <Card className="p-6 bg-card/60 backdrop-blur-sm border-l-4 border-l-emerald-500 rounded-sm">
                {/* Payout account status */}
                {isAuthed && (
                  <div
                    data-testid="connect-payout-card"
                    className="mb-5 pb-5 border-b"
                  >
                    {connect?.ready_for_payouts ? (
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="p-2 rounded-sm bg-emerald-50 border border-emerald-200 text-emerald-700 flex-shrink-0">
                            <CreditCard className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm font-semibold mb-0.5">
                              Payout account connected
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Commissions will auto-transfer to your bank via Stripe Express.
                            </p>
                          </div>
                        </div>
                        <Button
                          data-testid="connect-dashboard-btn"
                          variant="outline"
                          size="sm"
                          className="rounded-sm"
                          onClick={openConnectDashboard}
                          disabled={connectLoading}
                        >
                          {connectLoading ? (
                            <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                          ) : (
                            <ExternalLink className="h-3.5 w-3.5 mr-2" />
                          )}
                          Stripe dashboard
                        </Button>
                      </div>
                    ) : connect?.connected ? (
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="p-2 rounded-sm bg-amber-50 border border-amber-200 text-amber-700 flex-shrink-0">
                            <CreditCard className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm font-semibold mb-0.5">
                              Finish setting up your payout account
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Stripe still needs a few details before your commissions can be paid.
                            </p>
                          </div>
                        </div>
                        <Button
                          data-testid="connect-resume-btn"
                          size="sm"
                          className="rounded-sm"
                          onClick={onboardPayouts}
                          disabled={connectLoading}
                        >
                          {connectLoading ? (
                            <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                          ) : (
                            <CreditCard className="h-3.5 w-3.5 mr-2" />
                          )}
                          Resume onboarding
                        </Button>
                      </div>
                    ) : (
                      <div className="flex items-center justify-between gap-3 flex-wrap">
                        <div className="flex items-start gap-3 min-w-0">
                          <div className="p-2 rounded-sm bg-primary/10 text-primary flex-shrink-0">
                            <CreditCard className="h-4 w-4" />
                          </div>
                          <div className="min-w-0">
                            <div className="text-sm font-semibold mb-0.5">
                              Connect your payout account to get paid automatically
                            </div>
                            <p className="text-xs text-muted-foreground">
                              Stripe Express — 2-minute setup. Commissions land directly in your bank
                              with no manual review.
                            </p>
                          </div>
                        </div>
                        <Button
                          data-testid="connect-onboard-btn"
                          size="sm"
                          className="rounded-sm"
                          onClick={onboardPayouts}
                          disabled={connectLoading}
                        >
                          {connectLoading ? (
                            <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                          ) : (
                            <CreditCard className="h-3.5 w-3.5 mr-2" />
                          )}
                          Connect with Stripe
                        </Button>
                      </div>
                    )}
                  </div>
                )}

                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                  <div className="p-3 rounded-sm border bg-accent/30 text-center">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                      Pending payout
                    </div>
                    <div
                      data-testid="earnings-pending"
                      className="text-2xl font-heading font-semibold text-amber-700 mt-1"
                    >
                      ${(earnings?.totals?.pending || 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="p-3 rounded-sm border bg-accent/30 text-center">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                      Lifetime paid
                    </div>
                    <div
                      data-testid="earnings-paid"
                      className="text-2xl font-heading font-semibold text-emerald-700 mt-1"
                    >
                      ${(earnings?.totals?.paid || 0).toFixed(2)}
                    </div>
                  </div>
                  <div className="p-3 rounded-sm border bg-accent/30 text-center">
                    <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                      Total rows
                    </div>
                    <div
                      data-testid="earnings-count"
                      className="text-2xl font-heading font-semibold mt-1"
                    >
                      {earnings?.totals?.count || 0}
                    </div>
                  </div>
                </div>

                {earnings?.commissions?.length > 0 && (
                <div data-testid="earnings-list" className="border-t pt-3">
                  <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground mb-2">
                    Recent commissions
                  </div>
                  <ul className="space-y-1.5 text-xs font-body">
                    {earnings.commissions.slice(0, 6).map((c) => (
                      <li
                        key={c.id}
                        data-testid={`earnings-row-${c.id}`}
                        className="flex items-center justify-between py-1 border-b last:border-0"
                      >
                        <span className="flex items-center gap-2 min-w-0">
                          <span className="text-muted-foreground font-mono text-[10px]">
                            {c.created_at ? new Date(c.created_at).toLocaleDateString() : ''}
                          </span>
                          <span className="uppercase tracking-wider text-[10px] font-mono px-1.5 py-0.5 bg-muted rounded-sm">
                            {c.kind} · {c.percent}%
                          </span>
                        </span>
                        <span className="flex items-center gap-2 flex-shrink-0">
                          <span className="font-mono font-semibold">
                            ${Number(c.amount).toFixed(2)}
                          </span>
                          <span className={`text-[10px] uppercase ${
                            c.status === 'paid' ? 'text-emerald-700' : 'text-amber-700'
                          }`}>
                            {c.status}
                          </span>
                        </span>
                      </li>
                    ))}
                  </ul>
                </div>
                )}
              </Card>
            </motion.section>
          )}

          {/* Leaderboard — visible to everyone */}
          {leaderboard.length > 0 && (
            <motion.section
              initial={{ opacity: 0, y: 10 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, margin: '-100px' }}
              transition={{ duration: 0.4 }}
              data-testid="leaderboard-card"
              className="scroll-mt-28"
              id="leaderboard"
            >
              <div className="flex items-center gap-3 mb-2">
                <div className="p-2 rounded-sm bg-amber-50 text-amber-700 border border-amber-200">
                  <Trophy className="h-5 w-5" />
                </div>
                <span className="text-[10px] uppercase tracking-[0.22em] font-mono text-muted-foreground">
                  Top Inviters
                </span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-heading font-semibold mb-1">
                Authors building the DLP community
              </h2>
              <p className="text-sm text-muted-foreground italic font-body mb-5">
                The most prolific inviters this season.
              </p>
              <Card className="p-6 bg-card/60 backdrop-blur-sm border-l-4 border-l-amber-400 rounded-sm">
                <ol data-testid="leaderboard-list" className="space-y-2">
                  {leaderboard.map((entry, idx) => (
                    <li
                      key={idx}
                      data-testid={`leaderboard-row-${idx}`}
                      className="flex items-center justify-between gap-3 py-1.5 border-b last:border-0"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <span className={`flex items-center justify-center h-7 w-7 rounded-sm font-mono text-xs font-semibold ${
                          idx === 0 ? 'bg-amber-100 text-amber-800 border border-amber-300' :
                          idx === 1 ? 'bg-zinc-100 text-zinc-800 border border-zinc-300' :
                          idx === 2 ? 'bg-orange-50 text-orange-800 border border-orange-200' :
                          'bg-muted text-muted-foreground border border-border'
                        }`}>
                          {idx + 1}
                        </span>
                        <span className="font-body text-sm truncate">{entry.name}</span>
                      </div>
                      <span className="text-sm font-mono font-semibold text-primary flex-shrink-0">
                        {entry.count} <span className="font-normal text-muted-foreground">invited</span>
                      </span>
                    </li>
                  ))}
                </ol>
              </Card>
            </motion.section>
          )}

          {/* Footer CTA */}
          <motion.section
            initial={{ opacity: 0 }}
            whileInView={{ opacity: 1 }}
            viewport={{ once: true }}
            transition={{ duration: 0.4 }}
            data-testid="help-footer"
            className="border-t pt-10 mt-4"
          >
            <h3 className="text-xl font-heading font-semibold mb-3">Still have questions?</h3>
            <p className="text-sm text-muted-foreground font-body mb-5">
              Every panel in the editor has an inline description right under its title.
              If something is still unclear, your manuscript is safe — every save is
              versioned, and you can always undo from the History tab.
            </p>
            <Button
              data-testid="help-back-to-dashboard-btn"
              onClick={() => navigate('/dashboard')}
              className="rounded-sm"
            >
              Back to Dashboard
            </Button>
          </motion.section>
        </main>
      </div>
    </div>
  );
}
