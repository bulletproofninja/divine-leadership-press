import { useState, useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Save, Download, History, MessageSquare, Settings, Eye, Globe, Loader2, FileType, BookOpen, Sparkles, Check, X, ScanSearch, AlertCircle, Lightbulb, FileSearch, Headphones, Play, Pause, ImageIcon, Trash2, Mic, MicOff, FileDown, HelpCircle, Wand2, BotMessageSquare } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Switch } from '../components/ui/switch';
import { Card } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { Textarea } from '../components/ui/textarea';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate, useParams } from 'react-router-dom';
import ReactQuill from 'react-quill-new';
import WritingAgentPanel from '../components/WritingAgentPanel';
import InlineCommandBar from '../components/InlineCommandBar';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = '/brand/divine-leadership-press-emblem.png';

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

const SEVERITY_BADGES = {
  must_fix: { label: 'Must fix', cls: 'bg-red-100 text-red-800 border-red-200' },
  suggested: { label: 'Suggested', cls: 'bg-amber-100 text-amber-800 border-amber-200' },
  stylistic: { label: 'Stylistic', cls: 'bg-blue-100 text-blue-800 border-blue-200' },
};

const CATEGORY_LABELS = {
  grammar: 'Grammar',
  punctuation: 'Punctuation',
  spelling: 'Spelling',
  run_on: 'Run-on',
  comma_splice: 'Comma splice',
  passive: 'Passive voice',
  wordy: 'Wordy',
  repetition: 'Repetition',
  consistency: 'Consistency',
  clarity: 'Clarity',
  tone: 'Tone',
};

const COVER_PAPER_TYPES = [
  { value: 'black_white', label: 'Black ink, white paper' },
  { value: 'cream', label: 'Black ink, cream paper' },
  { value: 'groundwood', label: 'Black ink, groundwood paper' },
  { value: 'standard_color', label: 'Standard color, white paper' },
  { value: 'premium_color', label: 'Premium color, white paper' },
];

function VoiceMemoCard({ memo, audioUrl, transcribing, onLoadAudio, onTranscribe, onDelete }) {
  const ts = memo.created_at ? new Date(memo.created_at) : null;
  return (
    <div data-testid={`memo-${memo.id}`} className="border rounded-sm p-2 bg-card hover:bg-accent/30 transition-colors">
      <div className="flex items-center justify-between mb-1 gap-2">
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <span className="text-xs font-medium truncate">{memo.title || 'Untitled memo'}</span>
          {memo.paragraph_index !== null && memo.paragraph_index !== undefined && (
            <span className="text-[10px] font-mono text-muted-foreground flex-shrink-0">
              ¶{memo.paragraph_index + 1}
            </span>
          )}
        </div>
        <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground flex-shrink-0">
          {ts ? ts.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}
        </span>
      </div>

      {audioUrl ? (
        <audio
          data-testid={`memo-player-${memo.id}`}
          controls
          src={audioUrl}
          className="w-full h-7 mb-2"
        >
          <track kind="captions" />
        </audio>
      ) : (
        <Button
          data-testid={`memo-load-${memo.id}`}
          size="sm"
          variant="outline"
          className="w-full rounded-sm h-7 text-xs mb-2"
          onClick={onLoadAudio}
        >
          <Play className="h-3 w-3 mr-1" /> Load &amp; Play
        </Button>
      )}

      {memo.transcript && (
        <div className="text-[11px] text-muted-foreground italic mb-2 line-clamp-3">
          “{memo.transcript}”
        </div>
      )}

      <div className="flex gap-1">
        <Button
          data-testid={`memo-transcribe-${memo.id}`}
          size="sm"
          variant="outline"
          className="flex-1 rounded-sm h-7 text-[11px]"
          disabled={transcribing}
          onClick={onTranscribe}
        >
          {transcribing ? (
            <><Loader2 className="h-3 w-3 mr-1 animate-spin" /> Transcribing…</>
          ) : memo.transcript ? (
            'Insert into manuscript'
          ) : (
            'Transcribe & Insert'
          )}
        </Button>
        <Button
          data-testid={`memo-delete-${memo.id}`}
          size="sm"
          variant="ghost"
          className="rounded-sm h-7 px-2"
          onClick={onDelete}
        >
          <Trash2 className="h-3 w-3 text-destructive" />
        </Button>
      </div>
    </div>
  );
}

function CopyEditIssueCard({ issue, onAccept, onReject }) {
  const sev = SEVERITY_BADGES[issue.severity] || SEVERITY_BADGES.suggested;
  return (
    <div data-testid={`issue-${issue.id}`} className="border rounded-sm p-3 bg-card hover:bg-accent/30 transition-colors">
      <div className="flex items-center justify-between mb-2 gap-2">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono uppercase tracking-wider ${sev.cls}`}>
            {sev.label}
          </span>
          <span className="text-[11px] font-medium text-muted-foreground">
            {CATEGORY_LABELS[issue.category] || issue.category}
          </span>
          <span className="text-[10px] text-muted-foreground">
            ¶{issue.paragraph_index + 1}
          </span>
        </div>
      </div>
      <div className="space-y-1 mb-2">
        <div className="text-xs">
          <span className="text-red-700 line-through bg-red-50 px-1 rounded">
            {issue.original}
          </span>
        </div>
        <div className="text-xs">
          <span className="text-emerald-800 bg-emerald-50 px-1 rounded font-medium">
            {issue.suggestion}
          </span>
        </div>
      </div>
      {issue.rationale && (
        <div className="flex items-start gap-1.5 text-[11px] text-muted-foreground italic mb-2">
          <Lightbulb className="h-3 w-3 flex-shrink-0 mt-0.5" />
          <span>{issue.rationale}</span>
        </div>
      )}
      <div className="flex gap-2">
        <Button
          data-testid={`accept-issue-${issue.id}`}
          size="sm"
          className="flex-1 rounded-sm h-7 text-xs"
          onClick={onAccept}
        >
          <Check className="h-3 w-3 mr-1" /> Accept
        </Button>
        <Button
          data-testid={`reject-issue-${issue.id}`}
          size="sm"
          variant="ghost"
          className="rounded-sm h-7 text-xs"
          onClick={onReject}
        >
          <X className="h-3 w-3" />
        </Button>
      </div>
    </div>
  );
}

export default function EditorPage({ user }) {
  const navigate = useNavigate();
  const { documentId } = useParams();
  const [docMeta, setDocMeta] = useState(null);
  const [content, setContent] = useState('');
  const [title, setTitle] = useState('');
  const [metadata, setMetadata] = useState({});
  const [versions, setVersions] = useState([]);
  const [comments, setComments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('editor');
  const [newComment, setNewComment] = useState('');
  const [showPreview, setShowPreview] = useState(false);
  const [wordCount, setWordCount] = useState(0);
  const [trackChanges, setTrackChanges] = useState(false);
  const [styleTemplate, setStyleTemplate] = useState('default');
  const [pdfTrim, setPdfTrim] = useState('6x9');
  const [trimSizes, setTrimSizes] = useState([]);
  const [aiRunning, setAiRunning] = useState(null);
  const [aiResult, setAiResult] = useState(null); // { tool, label, result, result_type }
  const [copyEditRunning, setCopyEditRunning] = useState(false);
  const [copyEditData, setCopyEditData] = useState(null); // { issues, readability, style_guide, paragraph_count }
  const [styleGuide, setStyleGuide] = useState('house');
  const [styleGuides, setStyleGuides] = useState([]);
  const [issueFilter, setIssueFilter] = useState('all');
  const [ttsVoices, setTtsVoices] = useState([]);
  const [ttsVoice, setTtsVoice] = useState('onyx');
  const [ttsSpeed, setTtsSpeed] = useState(1.0);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewAudioUrl, setPreviewAudioUrl] = useState(null);
  const [audiobookLoading, setAudiobookLoading] = useState(false);
  const [chapterAudiobookLoading, setChapterAudiobookLoading] = useState(false);
  const [chapterPreview, setChapterPreview] = useState(null);
  const [chapterPreviewLoading, setChapterPreviewLoading] = useState(false);
  // ElevenLabs state
  const [hasElevenKey, setHasElevenKey] = useState(false);
  const [elevenKeyInput, setElevenKeyInput] = useState('');
  const [savingElevenKey, setSavingElevenKey] = useState(false);
  const [elevenVoices, setElevenVoices] = useState([]);
  const [elevenVoiceId, setElevenVoiceId] = useState('');
  const [elevenLoadingVoices, setElevenLoadingVoices] = useState(false);
  const [elevenCustomVoiceId, setElevenCustomVoiceId] = useState('');
  const [elevenPreviewLoading, setElevenPreviewLoading] = useState(false);
  const [elevenAudiobookLoading, setElevenAudiobookLoading] = useState(false);
  const [elevenPreviewUrl, setElevenPreviewUrl] = useState(null);
  // Uploaded audiobook state
  const [uploadedAudiobookInfo, setUploadedAudiobookInfo] = useState(null);
  const [uploadingAudiobook, setUploadingAudiobook] = useState(false);
  const [uploadedPlayerUrl, setUploadedPlayerUrl] = useState(null);
  // Book Setup (metadata + cover)
  const [coverPreviewUrl, setCoverPreviewUrl] = useState(null);
  const [uploadingCover, setUploadingCover] = useState(false);
  const [savingMetadata, setSavingMetadata] = useState(false);
  const [downloadingCoverPdf, setDownloadingCoverPdf] = useState(false);
  const [backCoverFile, setBackCoverFile] = useState(null);
  const [coverPaperType, setCoverPaperType] = useState('black_white');
  const [generatingCoverSpread, setGeneratingCoverSpread] = useState(false);
  // Voice Memos
  const [memos, setMemos] = useState([]);
  const [memoRecording, setMemoRecording] = useState(false);
  const [memoSaving, setMemoSaving] = useState(false);
  const [memoAudioUrls, setMemoAudioUrls] = useState({}); // memoId -> blob URL
  const [memoTranscribing, setMemoTranscribing] = useState(null); // memoId currently transcribing
  const memoRecorderRef = useRef(null);
  const memoStreamRef = useRef(null);
  // Dictation
  const [isRecording, setIsRecording] = useState(false);
  const [transcribing, setTranscribing] = useState(false);
  const [continuousMode, setContinuousMode] = useState(false);
  const [dictationHistory, setDictationHistory] = useState([]);
  const mediaRecorderRef = useRef(null);
  const quillRef = useRef(null);
  const continuousRef = useRef(false);
  const mediaStreamRef = useRef(null);

  // Writing agent state
  const [agentOpen, setAgentOpen] = useState(false);
  const [cmdkOpen, setCmdkOpen] = useState(false);
  const [cmdkSelection, setCmdkSelection] = useState('');
  const [cmdkRange, setCmdkRange] = useState(null);

  // Cmd-K hotkey + open/close handlers
  useEffect(() => {
    const onKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault();
        const quill = quillRef.current?.getEditor?.();
        if (!quill) return;
        const range = quill.getSelection();
        const selectionText =
          range && range.length > 0 ? quill.getText(range.index, range.length) : '';
        setCmdkSelection(selectionText.trim());
        setCmdkRange(range);
        setCmdkOpen(true);
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);

  const applyCmdkResult = (newText) => {
    const quill = quillRef.current?.getEditor?.();
    if (!quill || !cmdkRange) return;
    if (cmdkRange.length > 0) {
      quill.deleteText(cmdkRange.index, cmdkRange.length, 'user');
    }
    quill.insertText(cmdkRange.index, newText, 'user');
    quill.setSelection(cmdkRange.index, newText.length, 'user');
    toast.success('Replaced selection');
  };

  useEffect(() => {
    fetchDocument();
    fetchVersions();
    fetchComments();
    fetchTrimSizes();
    loadElevenLabsStatus();
    fetchUploadedInfo();
    fetchMemos();
  }, [documentId]);

  const fetchTrimSizes = async () => {
    try {
      const response = await axios.get(`${API}/export/formats`);
      setTrimSizes(response.data.print_trim_sizes || []);
    } catch (error) {
      // Non-blocking; fall back to default
    }
  };

  useEffect(() => {
    axios.get(`${API}/copyedit/style-guides`).then((r) => {
      setStyleGuides(r.data.style_guides || []);
    }).catch(() => {});
    axios.get(`${API}/tts/voices`).then((r) => {
      setTtsVoices(r.data.voices || []);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    // Calculate word count
    const text = content.replace(/<[^>]*>/g, '').trim();
    const words = text.split(/\s+/).filter(word => word.length > 0);
    setWordCount(words.length);
  }, [content]);

  const fetchDocument = async () => {
    try {
      const response = await axios.get(`${API}/documents/${documentId}`, getAuthHeaders());
      setDocMeta(response.data);
      setContent(response.data.content);
      setTitle(response.data.title);
      setMetadata(response.data.metadata || {});
      if (response.data.format && response.data.format !== 'epub') {
        setPdfTrim(response.data.format);
      }
    } catch (error) {
      toast.error('Failed to load document');
      navigate('/dashboard');
    } finally {
      setLoading(false);
    }
  };

  const fetchVersions = async () => {
    try {
      const response = await axios.get(`${API}/documents/${documentId}/versions`, getAuthHeaders());
      setVersions(response.data);
    } catch (error) {
      console.error('Failed to load versions');
    }
  };

  const fetchComments = async () => {
    try {
      const response = await axios.get(`${API}/documents/${documentId}/comments`, getAuthHeaders());
      setComments(response.data);
    } catch (error) {
      console.error('Failed to load comments');
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      await axios.put(
        `${API}/documents/${documentId}`,
        { title, content, metadata },
        getAuthHeaders()
      );
      toast.success('Document saved');
      fetchVersions();
    } catch (error) {
      toast.error('Failed to save document');
    } finally {
      setSaving(false);
    }
  };

  const handleAddComment = async (e) => {
    e.preventDefault();
    if (!newComment.trim()) return;

    try {
      await axios.post(
        `${API}/documents/${documentId}/comments`,
        { content: newComment },
        getAuthHeaders()
      );
      toast.success('Comment added');
      setNewComment('');
      fetchComments();
    } catch (error) {
      toast.error('Failed to add comment');
    }
  };

  const handleExport = async (format, trim) => {
    try {
      const trimQuery = format === 'pdf' && trim ? `&trim=${encodeURIComponent(trim)}` : '';
      const response = await axios.post(
        `${API}/documents/${documentId}/export?format=${format}${trimQuery}`,
        {},
        { ...getAuthHeaders(), responseType: 'blob' }
      );
      const blob = new Blob([response.data], {
        type: format === 'pdf' ? 'application/pdf' : 'application/epub+zip',
      });
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      const safe = (title || 'document').replace(/[^A-Za-z0-9._-]+/g, '_');
      a.download = format === 'pdf' ? `${safe}_${trim || pdfTrim}.pdf` : `${safe}.epub`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Exported ${format.toUpperCase()}${format === 'pdf' ? ` (${trim || pdfTrim})` : ''}`);
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const runAiTool = async (toolKey) => {
    setAiRunning(toolKey);
    setAiResult(null);
    try {
      const response = await axios.post(
        `${API}/documents/${documentId}/ai`,
        { tool: toolKey, content },
        getAuthHeaders()
      );
      setAiResult(response.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'AI tool failed', { duration: 7000 });
    } finally {
      setAiRunning(null);
    }
  };

  const textToHtml = (text) => {
    if (!text) return '';
    return text
      .split(/\n{2,}/)
      .map((para) => `<p>${para.replace(/\n/g, '<br>')}</p>`)
      .join('');
  };

  const applyAiResult = () => {
    if (!aiResult) return;
    if (aiResult.result_type === 'prose') {
      setContent(textToHtml(aiResult.result));
      toast.success(`${aiResult.label} applied to manuscript`);
    } else {
      // Append blurb / synopsis / chapter titles at the end
      const heading = `<h2>${aiResult.label}</h2>`;
      setContent((prev) => `${prev || ''}${heading}${textToHtml(aiResult.result)}`);
      toast.success(`${aiResult.label} appended to manuscript`);
    }
    setAiResult(null);
  };

  const discardAiResult = () => {
    setAiResult(null);
  };

  const copyAiResult = async () => {
    if (!aiResult) return;
    try {
      await navigator.clipboard.writeText(aiResult.result);
      toast.success('Copied to clipboard');
    } catch (_) {
      toast.error('Copy failed');
    }
  };

  const runCopyEdit = async () => {
    setCopyEditRunning(true);
    setCopyEditData(null);
    try {
      const response = await axios.post(
        `${API}/documents/${documentId}/copyedit`,
        { content, style_guide: styleGuide },
        getAuthHeaders()
      );
      setCopyEditData(response.data);
      const n = response.data.issues?.length || 0;
      if (n === 0) {
        toast.success('Manuscript is clean — no issues found.');
      } else {
        toast.success(`Found ${n} issue${n === 1 ? '' : 's'} to review.`);
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Copy editor failed', { duration: 7000 });
    } finally {
      setCopyEditRunning(false);
    }
  };

  // Apply a single suggestion: replace `original` with `suggestion` in the matching paragraph.
  // We locate the paragraph (Nth <p>/<h*>/<li>/<blockquote>) and do a first-occurrence replace.
  // HTML-level replace is tried first so inline formatting (<strong>, <em>, etc.) is preserved.
  const applyCopyEditFix = (issue) => {
    if (!issue) return false;
    const PARA_TAGS = ['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li', 'blockquote'];
    const parser = new DOMParser();
    const doc = parser.parseFromString(`<root>${content || ''}</root>`, 'text/html');
    const root = doc.querySelector('root');
    if (!root) return false;
    const blocks = Array.from(root.querySelectorAll(PARA_TAGS.join(',')));
    const target = blocks[issue.paragraph_index];
    if (!target) return false;

    // 1) Try a direct HTML-level replace first — preserves all inline formatting.
    const html = target.innerHTML;
    if (html.includes(issue.original)) {
      target.innerHTML = html.replace(issue.original, issue.suggestion);
      setContent(root.innerHTML);
      setCopyEditData((prev) => prev ? {
        ...prev,
        issues: prev.issues.filter((i) => i.id !== issue.id),
      } : prev);
      return true;
    }

    // 2) Fallback: walk text nodes and patch the first matching span.
    //    Used when the issue.original is split across inline tags.
    const escapeRegex = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const pattern = new RegExp(escapeRegex(issue.original).replace(/\s+/g, '\\s+'), '');
    if (pattern.test(target.textContent)) {
      const walker = window.document.createTreeWalker(target, NodeFilter.SHOW_TEXT, null);
      let node = walker.nextNode();
      let combined = '';
      const nodes = [];
      while (node) {
        nodes.push(node);
        combined += node.nodeValue;
        node = walker.nextNode();
      }
      if (pattern.test(combined)) {
        const newCombined = combined.replace(pattern, issue.suggestion);
        if (nodes.length > 0) {
          nodes[0].nodeValue = newCombined;
          for (let i = 1; i < nodes.length; i += 1) {
            nodes[i].nodeValue = '';
          }
          setContent(root.innerHTML);
          setCopyEditData((prev) => prev ? {
            ...prev,
            issues: prev.issues.filter((i) => i.id !== issue.id),
          } : prev);
          return true;
        }
      }
    }
    return false;
  };

  const handleAcceptIssue = (issue) => {
    const ok = applyCopyEditFix(issue);
    if (ok) {
      toast.success('Fix applied');
    } else {
      toast.error('Could not auto-apply — edit manually', { duration: 5000 });
    }
  };

  const handleRejectIssue = (issue) => {
    setCopyEditData((prev) => prev ? {
      ...prev,
      issues: prev.issues.filter((i) => i.id !== issue.id),
    } : prev);
  };

  const handleAcceptAll = () => {
    if (!copyEditData?.issues?.length) return;
    let applied = 0;
    let skipped = 0;
    // Apply in reverse paragraph order so earlier indices stay valid
    const sorted = [...copyEditData.issues].sort(
      (a, b) => b.paragraph_index - a.paragraph_index
    );
    sorted.forEach((issue) => {
      if (applyCopyEditFix(issue)) applied += 1;
      else skipped += 1;
    });
    toast.success(`Applied ${applied} fix${applied === 1 ? '' : 'es'}${skipped ? `, ${skipped} skipped` : ''}`);
  };

  const handleRejectAll = () => {
    setCopyEditData((prev) => prev ? { ...prev, issues: [] } : prev);
  };

  // --- ElevenLabs handlers ---
  const loadElevenLabsStatus = async () => {
    try {
      const r = await axios.get(`${API}/auth/me`, getAuthHeaders());
      setHasElevenKey(!!r.data.has_elevenlabs_key);
      if (r.data.has_elevenlabs_key && elevenVoices.length === 0) {
        fetchElevenVoices();
      }
    } catch (_) {}
  };

  const saveElevenKey = async () => {
    if (!elevenKeyInput.trim()) {
      toast.error('Paste your ElevenLabs API key first');
      return;
    }
    setSavingElevenKey(true);
    try {
      await axios.put(
        `${API}/auth/me/elevenlabs-key`,
        { api_key: elevenKeyInput.trim() },
        getAuthHeaders()
      );
      setHasElevenKey(true);
      setElevenKeyInput('');
      toast.success('ElevenLabs key saved');
      fetchElevenVoices();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save key');
    } finally {
      setSavingElevenKey(false);
    }
  };

  const clearElevenKey = async () => {
    try {
      await axios.delete(`${API}/auth/me/elevenlabs-key`, getAuthHeaders());
      setHasElevenKey(false);
      setElevenVoices([]);
      setElevenVoiceId('');
      toast.success('ElevenLabs key removed');
    } catch (_) {
      toast.error('Could not remove key');
    }
  };

  const fetchElevenVoices = async () => {
    setElevenLoadingVoices(true);
    try {
      const r = await axios.get(`${API}/elevenlabs/voices`, getAuthHeaders());
      const list = r.data.voices || [];
      setElevenVoices(list);
      if (list.length > 0 && !elevenVoiceId) setElevenVoiceId(list[0].voice_id);
    } catch (error) {
      const status = error.response?.status;
      if (status === 401) {
        toast.error('ElevenLabs rejected your key — replace it below', { duration: 7000 });
      } else if (status !== 400) {
        toast.error(error.response?.data?.detail || 'Could not load voices');
      }
    } finally {
      setElevenLoadingVoices(false);
    }
  };

  const playElevenPreview = async () => {
    const voiceId = elevenCustomVoiceId.trim() || elevenVoiceId;
    if (!voiceId) {
      toast.error('Pick a voice or paste a custom Voice ID');
      return;
    }
    setElevenPreviewLoading(true);
    if (elevenPreviewUrl) {
      window.URL.revokeObjectURL(elevenPreviewUrl);
      setElevenPreviewUrl(null);
    }
    try {
      const r = await axios.post(
        `${API}/elevenlabs/preview`,
        { content, voice_id: voiceId },
        { ...getAuthHeaders(), responseType: 'blob' }
      );
      const url = window.URL.createObjectURL(new Blob([r.data], { type: 'audio/mpeg' }));
      setElevenPreviewUrl(url);
      toast.success('Preview ready');
    } catch (error) {
      const detail = error.response?.data?.detail || 'ElevenLabs preview failed';
      toast.error(detail, { duration: 7000 });
    } finally {
      setElevenPreviewLoading(false);
    }
  };

  const downloadElevenAudiobook = async () => {
    const voiceId = elevenCustomVoiceId.trim() || elevenVoiceId;
    if (!voiceId) {
      toast.error('Pick a voice or paste a custom Voice ID');
      return;
    }
    setElevenAudiobookLoading(true);
    try {
      const r = await axios.post(
        `${API}/documents/${documentId}/elevenlabs-audiobook?voice_id=${encodeURIComponent(voiceId)}`,
        {},
        { ...getAuthHeaders(), responseType: 'blob', timeout: 900000 }
      );
      const url = window.URL.createObjectURL(new Blob([r.data], { type: 'audio/mpeg' }));
      const a = window.document.createElement('a');
      a.href = url;
      const safe = (title || 'audiobook').replace(/[^A-Za-z0-9._-]+/g, '_');
      a.download = `${safe}_elevenlabs.mp3`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('ElevenLabs audiobook downloaded');
    } catch (error) {
      const detail = error.response?.data?.detail || 'ElevenLabs audiobook failed';
      toast.error(detail, { duration: 8000 });
    } finally {
      setElevenAudiobookLoading(false);
    }
  };

  // --- Audiobook upload handlers ---
  const fetchUploadedInfo = async () => {
    try {
      const r = await axios.get(`${API}/documents/${documentId}/audiobook/info`, getAuthHeaders());
      setUploadedAudiobookInfo(r.data);
      if (r.data.uploaded) {
        // Build playable URL via authenticated fetch → blob
        try {
          const audioR = await axios.get(`${API}/documents/${documentId}/audiobook`,
            { ...getAuthHeaders(), responseType: 'blob' });
          const url = window.URL.createObjectURL(audioR.data);
          setUploadedPlayerUrl(url);
        } catch (_) {}
      } else {
        setUploadedPlayerUrl(null);
      }
    } catch (_) {
      setUploadedAudiobookInfo({ uploaded: false });
    }
  };

  const uploadAudiobookFile = async (file) => {
    if (!file) return;
    setUploadingAudiobook(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await axios.post(`${API}/documents/${documentId}/audiobook/upload`, fd, {
        ...getAuthHeaders(),
        headers: { ...getAuthHeaders().headers, 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Audiobook uploaded');
      fetchUploadedInfo();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Upload failed', { duration: 7000 });
    } finally {
      setUploadingAudiobook(false);
    }
  };

  const deleteUploadedAudiobook = async () => {
    try {
      await axios.delete(`${API}/documents/${documentId}/audiobook`, getAuthHeaders());
      toast.success('Uploaded audiobook removed');
      setUploadedAudiobookInfo({ uploaded: false });
      if (uploadedPlayerUrl) {
        window.URL.revokeObjectURL(uploadedPlayerUrl);
        setUploadedPlayerUrl(null);
      }
    } catch (_) {
      toast.error('Could not remove audiobook');
    }
  };

  const playTtsPreview = async () => {
    setPreviewLoading(true);
    if (previewAudioUrl) {
      window.URL.revokeObjectURL(previewAudioUrl);
      setPreviewAudioUrl(null);
    }
    try {
      const response = await axios.post(
        `${API}/tts/preview`,
        { content, voice: ttsVoice, speed: ttsSpeed },
        { ...getAuthHeaders(), responseType: 'blob' }
      );
      const blob = new Blob([response.data], { type: 'audio/mpeg' });
      const url = window.URL.createObjectURL(blob);
      setPreviewAudioUrl(url);
      toast.success(`Preview ready — ${ttsVoice}`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Read Aloud failed', { duration: 7000 });
    } finally {
      setPreviewLoading(false);
    }
  };

  const downloadAudiobook = async () => {
    setAudiobookLoading(true);
    try {
      const response = await axios.post(
        `${API}/documents/${documentId}/audiobook?voice=${encodeURIComponent(ttsVoice)}&speed=${ttsSpeed}`,
        {},
        { ...getAuthHeaders(), responseType: 'blob', timeout: 600000 }
      );
      const blob = new Blob([response.data], { type: 'audio/mpeg' });
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      const safe = (title || 'audiobook').replace(/[^A-Za-z0-9._-]+/g, '_');
      a.download = `${safe}_audiobook.mp3`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Audiobook generated — ${ttsVoice} @ ${ttsSpeed}×`);
    } catch (error) {
      const detail = error.response?.data?.detail
        || (error.response?.status === 413 ? 'Manuscript is too long for a single audiobook' : 'Audiobook generation failed');
      toast.error(detail, { duration: 8000 });
    } finally {
      setAudiobookLoading(false);
    }
  };

  const fetchChapterPreview = async () => {
    setChapterPreviewLoading(true);
    try {
      const r = await axios.get(
        `${API}/documents/${documentId}/audiobook/chapters/preview`,
        getAuthHeaders()
      );
      setChapterPreview(r.data);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not detect chapters');
    } finally {
      setChapterPreviewLoading(false);
    }
  };

  const downloadChapterAudiobook = async () => {
    setChapterAudiobookLoading(true);
    try {
      const response = await axios.post(
        `${API}/documents/${documentId}/audiobook/chapters?voice=${encodeURIComponent(ttsVoice)}&speed=${ttsSpeed}`,
        {},
        { ...getAuthHeaders(), responseType: 'blob', timeout: 1200000 }
      );
      const blob = new Blob([response.data], { type: 'application/zip' });
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      const safe = (title || 'audiobook').replace(/[^A-Za-z0-9._-]+/g, '_');
      a.download = `${safe}_chapters.zip`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success('Per-chapter audiobook downloaded');
    } catch (error) {
      const detail = error.response?.data?.detail || 'Per-chapter export failed';
      toast.error(detail, { duration: 8000 });
    } finally {
      setChapterAudiobookLoading(false);
    }
  };

  // --- Book Setup (metadata + cover) ---
  const updateMetadataField = (key, value) => {
    setMetadata((prev) => ({ ...prev, [key]: value }));
  };

  const saveMetadata = async () => {
    setSavingMetadata(true);
    try {
      await axios.put(
        `${API}/documents/${documentId}`,
        { metadata },
        getAuthHeaders()
      );
      toast.success('Book details saved');
      fetchDocument();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Could not save details');
    } finally {
      setSavingMetadata(false);
    }
  };

  const loadCoverPreview = async () => {
    if (!docMeta?.cover_image_ext) {
      if (coverPreviewUrl) window.URL.revokeObjectURL(coverPreviewUrl);
      setCoverPreviewUrl(null);
      return;
    }
    try {
      const r = await axios.get(`${API}/documents/${documentId}/cover`, {
        ...getAuthHeaders(),
        responseType: 'blob',
      });
      if (coverPreviewUrl) window.URL.revokeObjectURL(coverPreviewUrl);
      setCoverPreviewUrl(window.URL.createObjectURL(r.data));
    } catch (_) {
      setCoverPreviewUrl(null);
    }
  };

  useEffect(() => {
    loadCoverPreview();
  }, [docMeta?.cover_image_ext]);

  const uploadCoverFile = async (file) => {
    if (!file) return;
    setUploadingCover(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      await axios.post(`${API}/documents/${documentId}/cover/upload`, fd, {
        ...getAuthHeaders(),
        headers: { ...getAuthHeaders().headers, 'Content-Type': 'multipart/form-data' },
      });
      toast.success('Cover uploaded');
      fetchDocument();
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Cover upload failed', { duration: 7000 });
    } finally {
      setUploadingCover(false);
    }
  };

  const removeCover = async () => {
    try {
      await axios.delete(`${API}/documents/${documentId}/cover`, getAuthHeaders());
      toast.success('Cover removed');
      fetchDocument();
    } catch (_) {
      toast.error('Could not remove cover');
    }
  };

  const downloadCoverPdf = async () => {
    setDownloadingCoverPdf(true);
    try {
      const r = await axios.post(
        `${API}/documents/${documentId}/cover/pdf?trim=${encodeURIComponent(pdfTrim)}&include_bleed=true`,
        {},
        { ...getAuthHeaders(), responseType: 'blob' }
      );
      const blob = new Blob([r.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      const safe = (title || 'cover').replace(/[^A-Za-z0-9._-]+/g, '_');
      a.download = `${safe}_cover_${pdfTrim}.pdf`;
      window.document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Full-bleed cover PDF downloaded (${pdfTrim}, 0.125-inch bleed)`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Cover PDF generation failed');
    } finally {
      setDownloadingCoverPdf(false);
    }
  };

  const downloadCoverSpread = async () => {
    const pageCount = Number(metadata.page_count || 0);
    if (!backCoverFile) return toast.error('Choose a back cover image first');
    if (!Number.isInteger(pageCount) || pageCount < 24 || pageCount > 828) {
      return toast.error('Enter the final formatted page count, from 24 through 828');
    }
    setGeneratingCoverSpread(true);
    try {
      const formData = new FormData();
      formData.append('back_cover', backCoverFile);
      const query = new URLSearchParams({
        trim: pdfTrim,
        page_count: String(pageCount),
        paper_type: coverPaperType,
        reserve_barcode: 'true',
      });
      const response = await axios.post(
        `${API}/documents/${documentId}/cover/spread?${query.toString()}`,
        formData,
        { ...getAuthHeaders(), responseType: 'blob' },
      );
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const anchor = window.document.createElement('a');
      anchor.href = url;
      const safe = (title || 'book').replace(/[^A-Za-z0-9._-]+/g, '_');
      anchor.download = `${safe}_full_cover_${pdfTrim}.pdf`;
      window.document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(url);
      toast.success(`Full cover exported. Spine: ${response.headers['x-spine-width']} inches`);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Full cover generation failed');
    } finally {
      setGeneratingCoverSpread(false);
    }
  };

  // --- Dictation (Whisper) ---
  const insertAtCursor = (text, sourceId) => {
    if (!text) return null;
    const editor = quillRef.current?.getEditor?.();
    if (editor) {
      const range = editor.getSelection(true);
      const index = range ? range.index : editor.getLength();
      const prefix = index > 0 ? ' ' : '';
      const insertText = prefix + text;
      editor.insertText(index, insertText, 'user');
      editor.setSelection(index + insertText.length, 0);
      setContent(editor.root.innerHTML);
      return { index, length: insertText.length };
    }
    // Fallback append
    setContent((prev) => `${prev || ''}<p>${text.replace(/\n/g, '<br>')}</p>`);
    return null;
  };

  const transcribeBlob = async (blob, mime) => {
    if (!blob || blob.size < 256) return null;
    setTranscribing(true);
    try {
      const fd = new FormData();
      fd.append('file', blob, mime.includes('ogg') ? 'recording.ogg' : 'recording.webm');
      const r = await axios.post(`${API}/transcribe`, fd, {
        ...getAuthHeaders(),
        headers: { ...getAuthHeaders().headers, 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });
      const text = (r.data?.text || '').trim();
      if (!text) return null;
      const chunkId = `dict_${Date.now()}_${Math.random().toString(36).slice(2, 6)}`;
      const range = insertAtCursor(text, chunkId);
      setDictationHistory((prev) => [
        {
          id: chunkId,
          text,
          insertedAt: new Date().toISOString(),
          index: range?.index ?? null,
          length: range?.length ?? null,
          undone: false,
        },
        ...prev,
      ].slice(0, 30));
      return text;
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Transcription failed', { duration: 7000 });
      return null;
    } finally {
      setTranscribing(false);
    }
  };

  const _startRecorderCycle = (stream) => {
    const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/ogg';
    const chunks = [];
    const recorder = new MediaRecorder(stream, { mimeType: mime });
    mediaRecorderRef.current = recorder;

    recorder.ondataavailable = (e) => {
      if (e.data && e.data.size > 0) chunks.push(e.data);
    };
    recorder.onstop = async () => {
      const blob = new Blob(chunks, { type: mime });
      // Continue with next cycle BEFORE awaiting transcription so recording stays seamless
      if (continuousRef.current && mediaStreamRef.current) {
        _startRecorderCycle(mediaStreamRef.current);
      } else {
        // We're stopping for good — release the mic
        if (mediaStreamRef.current) {
          mediaStreamRef.current.getTracks().forEach((t) => t.stop());
          mediaStreamRef.current = null;
        }
        setIsRecording(false);
      }
      if (blob.size > 256) {
        await transcribeBlob(blob, mime);
      }
    };
    recorder.start();
    // In continuous mode, auto-stop after 30s; one-shot mode runs until user clicks Stop
    if (continuousRef.current) {
      window.setTimeout(() => {
        if (recorder.state === 'recording') recorder.stop();
      }, 30000);
    }
  };

  const startDictation = async () => {
    if (isRecording || transcribing) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      toast.error('Microphone is not available in this browser');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaStreamRef.current = stream;
      continuousRef.current = continuousMode;
      setIsRecording(true);
      _startRecorderCycle(stream);
      toast.success(continuousMode
        ? 'Continuous dictation — recording 30s segments'
        : 'Recording — click Stop when done');
    } catch (error) {
      toast.error(error.message || 'Microphone permission denied');
    }
  };

  const stopDictation = () => {
    continuousRef.current = false;
    const recorder = mediaRecorderRef.current;
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
    }
    // setIsRecording will flip to false inside the recorder.onstop handler
  };

  const undoDictationChunk = (chunk) => {
    if (!chunk || chunk.undone) return;
    const editor = quillRef.current?.getEditor?.();
    if (!editor) {
      toast.error('Editor not ready');
      return;
    }
    // Search-and-remove first remaining occurrence (robust to later edits)
    const fullText = editor.getText();
    const idx = fullText.indexOf(chunk.text);
    if (idx < 0) {
      toast.error('Could not locate dictation in manuscript');
      return;
    }
    // Also remove a leading space if it was added on insert
    const removeFrom = (idx > 0 && fullText[idx - 1] === ' ') ? idx - 1 : idx;
    const removeLen = (idx > 0 && fullText[idx - 1] === ' ') ? chunk.text.length + 1 : chunk.text.length;
    editor.deleteText(removeFrom, removeLen, 'user');
    setContent(editor.root.innerHTML);
    setDictationHistory((prev) =>
      prev.map((c) => (c.id === chunk.id ? { ...c, undone: true } : c))
    );
    toast.success('Dictation chunk removed');
  };

  const clearDictationHistory = () => {
    setDictationHistory([]);
  };

  // --- Voice Memos ---
  const fetchMemos = async () => {
    try {
      const r = await axios.get(`${API}/documents/${documentId}/memos`, getAuthHeaders());
      setMemos(r.data.memos || []);
    } catch (_) {}
  };

  // Estimate current paragraph index based on Quill cursor position
  const getCurrentParagraphIndex = () => {
    const editor = quillRef.current?.getEditor?.();
    if (!editor) return null;
    const sel = editor.getSelection();
    if (!sel) return null;
    const fullText = editor.getText().slice(0, sel.index);
    // Quill represents blocks separated by \n; an empty paragraph is also a \n
    const blockIndex = (fullText.match(/\n/g) || []).length;
    return blockIndex;
  };

  const startMemoRecording = async () => {
    if (memoRecording || memoSaving) return;
    if (!navigator.mediaDevices?.getUserMedia) {
      toast.error('Microphone is not available in this browser');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      memoStreamRef.current = stream;
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
        ? 'audio/webm;codecs=opus'
        : MediaRecorder.isTypeSupported('audio/webm')
          ? 'audio/webm'
          : 'audio/ogg';
      const recorder = new MediaRecorder(stream, { mimeType: mime });
      const chunks = [];
      recorder.ondataavailable = (e) => {
        if (e.data && e.data.size > 0) chunks.push(e.data);
      };
      recorder.onstop = async () => {
        if (memoStreamRef.current) {
          memoStreamRef.current.getTracks().forEach((t) => t.stop());
          memoStreamRef.current = null;
        }
        setMemoRecording(false);
        const blob = new Blob(chunks, { type: mime });
        if (blob.size < 256) {
          toast.error('Memo too short — try again');
          return;
        }
        setMemoSaving(true);
        try {
          const fd = new FormData();
          const filename = mime.includes('ogg') ? 'memo.ogg' : 'memo.webm';
          fd.append('file', blob, filename);
          const paraIdx = getCurrentParagraphIndex();
          const defaultTitle = `Memo ${new Date().toLocaleString([], {
            month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit'
          })}`;
          const qs = new URLSearchParams();
          qs.set('title', defaultTitle);
          if (paraIdx !== null) qs.set('paragraph_index', String(paraIdx));
          const r = await axios.post(
            `${API}/documents/${documentId}/memos?${qs.toString()}`,
            fd,
            {
              ...getAuthHeaders(),
              headers: { ...getAuthHeaders().headers, 'Content-Type': 'multipart/form-data' },
            }
          );
          toast.success('Voice memo saved');
          setMemos((prev) => [r.data, ...prev]);
        } catch (error) {
          toast.error(error.response?.data?.detail || 'Could not save memo');
        } finally {
          setMemoSaving(false);
        }
      };
      memoRecorderRef.current = recorder;
      recorder.start();
      setMemoRecording(true);
      toast.success('Recording memo — click again to stop');
    } catch (error) {
      toast.error(error.message || 'Microphone permission denied');
    }
  };

  const stopMemoRecording = () => {
    const recorder = memoRecorderRef.current;
    if (recorder && recorder.state === 'recording') {
      recorder.stop();
    }
  };

  const loadMemoAudio = async (memoId) => {
    if (memoAudioUrls[memoId]) return memoAudioUrls[memoId];
    try {
      const r = await axios.get(`${API}/documents/${documentId}/memos/${memoId}`, {
        ...getAuthHeaders(),
        responseType: 'blob',
      });
      const url = window.URL.createObjectURL(r.data);
      setMemoAudioUrls((prev) => ({ ...prev, [memoId]: url }));
      return url;
    } catch (_) {
      toast.error('Could not load memo audio');
      return null;
    }
  };

  const transcribeAndInsertMemo = async (memo) => {
    setMemoTranscribing(memo.id);
    try {
      const r = await axios.post(
        `${API}/documents/${documentId}/memos/${memo.id}/transcribe`,
        {},
        { ...getAuthHeaders(), timeout: 180000 }
      );
      const text = (r.data?.text || '').trim();
      if (!text) {
        toast.error('Nothing detected in memo');
        return;
      }
      insertAtCursor(text, `memo_${memo.id}`);
      // Update transcript cache locally
      setMemos((prev) => prev.map((m) => (m.id === memo.id ? { ...m, transcript: text } : m)));
      toast.success('Memo transcribed and inserted');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Transcription failed', { duration: 7000 });
    } finally {
      setMemoTranscribing(null);
    }
  };

  const deleteMemo = async (memo) => {
    try {
      await axios.delete(`${API}/documents/${documentId}/memos/${memo.id}`, getAuthHeaders());
      if (memoAudioUrls[memo.id]) {
        window.URL.revokeObjectURL(memoAudioUrls[memo.id]);
        setMemoAudioUrls((prev) => {
          const next = { ...prev };
          delete next[memo.id];
          return next;
        });
      }
      setMemos((prev) => prev.filter((m) => m.id !== memo.id));
      toast.success('Memo deleted');
    } catch (_) {
      toast.error('Could not delete memo');
    }
  };

  const handlePublish = async (platform) => {
    if (platform === 'lulu') {
      navigate(`/publishing?document=${documentId}`);
      return;
    }
    try {
      const endpoint = platform === 'kdp' ? '/integrations/kdp' : '/integrations/lulu';
      const response = await axios.post(
        `${API}${endpoint}?document_id=${documentId}`,
        {},
        getAuthHeaders()
      );
      toast.success(response.data.message);
      if (response.data.note) {
        toast.info(response.data.note, { duration: 5000 });
      }
    } catch (error) {
      toast.error('Publishing failed');
    }
  };

  const modules = {
    toolbar: [
      [{ 'header': [1, 2, 3, 4, 5, 6, false] }],
      [{ 'font': [] }],
      [{ 'size': ['small', false, 'large', 'huge'] }],
      ['bold', 'italic', 'underline', 'strike'],
      [{ 'color': [] }, { 'background': [] }],
      [{ 'script': 'sub'}, { 'script': 'super' }],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }, { 'indent': '-1'}, { 'indent': '+1' }],
      [{ 'align': [] }],
      [{ 'direction': 'rtl' }],
      ['blockquote', 'code-block'],
      ['link', 'image', 'video'],
      ['clean']
    ]
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', { 
      month: 'short', 
      day: 'numeric', 
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-background">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-3 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 flex-1 min-w-0">
            <Button
              data-testid="back-to-dashboard-btn"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/dashboard')}
              className="rounded-sm flex-shrink-0"
            >
              <ArrowLeft className="h-4 w-4" />
            </Button>
            <img src={LOGO_URL} alt="Divine Leadership Press" className="h-8 w-8 flex-shrink-0" />
            <Input
              data-testid="document-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="font-heading text-lg font-semibold border-0 focus-visible:ring-0 px-2"
            />
          </div>
          <div className="flex items-center gap-2">
            <Button
              data-testid="help-link-editor"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/help')}
              className="rounded-sm hidden sm:flex"
              title="Help & Documentation"
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
            <Button
              data-testid="preview-btn"
              variant="outline"
              size="sm"
              onClick={() => setShowPreview(!showPreview)}
              className="rounded-sm hidden sm:flex"
            >
              <Eye className="h-4 w-4 mr-2" />
              Preview
            </Button>
            <div className="flex items-center gap-1.5 rounded-sm border bg-card pl-2.5 pr-1 h-9">
              <Switch
                data-testid="continuous-mode-toggle"
                id="continuous-mode"
                checked={continuousMode}
                disabled={isRecording}
                onCheckedChange={setContinuousMode}
                className="h-4 w-7"
              />
              <Label
                htmlFor="continuous-mode"
                className="text-[11px] font-medium cursor-pointer select-none"
              >
                Continuous
              </Label>
              <Button
                data-testid={isRecording ? 'stop-dictate-btn' : 'start-dictate-btn'}
                variant={isRecording ? 'destructive' : 'ghost'}
                size="sm"
                onClick={isRecording ? stopDictation : startDictation}
                disabled={transcribing}
                className="rounded-sm h-7 px-2 ml-1"
                title={
                  isRecording
                    ? (continuousMode ? 'Stop continuous dictation' : 'Stop dictation')
                    : (continuousMode ? 'Start continuous dictation (30s segments)' : 'Dictate (Whisper)')
                }
              >
                {transcribing && !isRecording ? (
                  <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Transcribing…</>
                ) : isRecording ? (
                  <>
                    <MicOff className="h-3.5 w-3.5 mr-1" />
                    {continuousMode ? 'Stop' : 'Stop'}
                    {transcribing && <span className="ml-1 text-[10px] opacity-70">+ ⌛</span>}
                  </>
                ) : (
                  <><Mic className="h-3.5 w-3.5 mr-1" /> Dictate</>
                )}
              </Button>
            </div>
            <Button
              data-testid="agent-toggle-btn"
              variant={agentOpen ? 'default' : 'outline'}
              size="sm"
              onClick={() => setAgentOpen((v) => !v)}
              className="rounded-sm"
              title="Open writing agent"
            >
              <BotMessageSquare className="h-4 w-4 mr-1.5" />
              <span className="hidden sm:inline">Agent</span>
            </Button>
            <Button
              data-testid="save-btn"
              size="sm"
              onClick={handleSave}
              disabled={saving}
              className="rounded-sm"
            >
              <Save className="h-4 w-4 mr-2" />
              {saving ? 'Saving...' : 'Save'}
            </Button>
          </div>
        </div>
      </header>

      <div className="container mx-auto px-4 py-6 max-w-7xl">
        <div className="grid lg:grid-cols-[1fr,320px] gap-6">
          {/* Main Editor Area */}
          <div className="space-y-4">
            {/* Formatting Toolbar */}
            <Card data-testid="formatting-toolbar" className="p-4 bg-card/50 backdrop-blur-sm">
              <div className="flex items-center justify-between gap-4 flex-wrap">
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Label className="text-sm font-medium whitespace-nowrap">Style Template:</Label>
                    <Select value={styleTemplate} onValueChange={setStyleTemplate}>
                      <SelectTrigger data-testid="style-template-select" className="w-[180px] rounded-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="default">Default</SelectItem>
                        <SelectItem value="novel">Novel</SelectItem>
                        <SelectItem value="academic">Academic</SelectItem>
                        <SelectItem value="magazine">Magazine</SelectItem>
                        <SelectItem value="poetry">Poetry</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Separator orientation="vertical" className="h-6" />
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="track-changes"
                      data-testid="track-changes-toggle"
                      checked={trackChanges}
                      onChange={(e) => setTrackChanges(e.target.checked)}
                      className="rounded"
                    />
                    <Label htmlFor="track-changes" className="text-sm cursor-pointer">
                      Track Changes
                    </Label>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  <span data-testid="word-count">Words: <strong className="text-foreground">{wordCount}</strong></span>
                  <span>Characters: <strong className="text-foreground">{content.replace(/<[^>]*>/g, '').length}</strong></span>
                </div>
              </div>
            </Card>

            {showPreview ? (
              <Card data-testid="preview-panel" className="p-8 bg-card/50 backdrop-blur-sm min-h-[600px]">
                <div 
                  className={`prose prose-lg max-w-none font-editor ${
                    styleTemplate === 'novel' ? 'prose-headings:font-heading' :
                    styleTemplate === 'academic' ? 'prose-headings:font-mono' :
                    styleTemplate === 'magazine' ? 'prose-p:columns-2' :
                    styleTemplate === 'poetry' ? 'prose-p:text-center' : ''
                  }`}
                  dangerouslySetInnerHTML={{ __html: content }} 
                />
              </Card>
            ) : (
              <Card data-testid="editor-panel" className="p-6 bg-card/50 backdrop-blur-sm">
                {trackChanges && (
                  <div className="mb-4 p-3 bg-primary/10 border border-primary/20 rounded-sm">
                    <p className="text-sm text-primary font-medium">
                      ✓ Track Changes is ON - All edits will be saved in version history
                    </p>
                  </div>
                )}
                <ReactQuill
                  ref={quillRef}
                  theme="snow"
                  value={content}
                  onChange={setContent}
                  modules={modules}
                  className="h-[600px] mb-12"
                />
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            <Card data-testid="sidebar-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <Tabs value={activeTab} onValueChange={setActiveTab}>
                <TabsList className="grid w-full grid-cols-3">
                  <TabsTrigger data-testid="metadata-tab" value="metadata" className="text-xs">
                    <Settings className="h-3 w-3 mr-1" />
                    <span className="hidden sm:inline">Info</span>
                  </TabsTrigger>
                  <TabsTrigger data-testid="versions-tab" value="versions" className="text-xs">
                    <History className="h-3 w-3 mr-1" />
                    <span className="hidden sm:inline">History</span>
                  </TabsTrigger>
                  <TabsTrigger data-testid="comments-tab" value="comments" className="text-xs">
                    <MessageSquare className="h-3 w-3 mr-1" />
                    <span className="hidden sm:inline">Notes</span>
                  </TabsTrigger>
                </TabsList>

                <div className="mt-4 p-3 bg-accent/30 rounded-sm border">
                  <h4 className="text-xs font-semibold mb-2">Quick Tips</h4>
                  <ul className="text-xs text-muted-foreground space-y-1">
                    <li>• Use H1-H6 for chapter titles</li>
                    <li>• Toggle Track Changes to monitor edits</li>
                    <li>• Apply style templates for consistency</li>
                    <li>• Preview before export</li>
                  </ul>
                </div>

                <TabsContent value="metadata" className="space-y-4 mt-4">
                  <div>
                    <Label>Format</Label>
                    <Select value={docMeta?.format} disabled>
                      <SelectTrigger className="rounded-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="6x9">6×9</SelectItem>
                        <SelectItem value="5x8">5×8</SelectItem>
                        <SelectItem value="8.5x11">8.5×11</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Separator />
                  <div>
                    <Label htmlFor="isbn">ISBN</Label>
                    <Input
                      id="isbn"
                      data-testid="isbn-input"
                      value={metadata.isbn || ''}
                      onChange={(e) => setMetadata({ ...metadata, isbn: e.target.value })}
                      placeholder="978-3-16-148410-0"
                      className="rounded-sm font-mono"
                    />
                  </div>
                  <div>
                    <Label htmlFor="author">Author</Label>
                    <Input
                      id="author"
                      data-testid="author-input"
                      value={metadata.author || ''}
                      onChange={(e) => setMetadata({ ...metadata, author: e.target.value })}
                      placeholder="Author name"
                      className="rounded-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="publisher">Publisher</Label>
                    <Input
                      id="publisher"
                      data-testid="publisher-input"
                      value={metadata.publisher || ''}
                      onChange={(e) => setMetadata({ ...metadata, publisher: e.target.value })}
                      placeholder="Publisher name"
                      className="rounded-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="genre">Genre</Label>
                    <Input
                      id="genre"
                      data-testid="genre-input"
                      value={metadata.genre || ''}
                      onChange={(e) => setMetadata({ ...metadata, genre: e.target.value })}
                      placeholder="Fiction, Non-fiction, etc."
                      className="rounded-sm"
                    />
                  </div>
                </TabsContent>

                <TabsContent value="versions" className="mt-4">
                  <div className="space-y-3">
                    {versions.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-8">No version history</p>
                    ) : (
                      versions.slice().reverse().map((version) => (
                        <div key={version.id} data-testid={`version-${version.id}`} className="p-3 border rounded-sm hover:bg-accent/50 transition-colors">
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs font-mono text-muted-foreground">
                              Version {version.version_number}
                            </span>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(version.created_at)}
                            </span>
                          </div>
                          <p className="text-sm line-clamp-2">{version.content.substring(0, 100)}...</p>
                        </div>
                      ))
                    )}
                  </div>
                </TabsContent>

                <TabsContent value="comments" className="mt-4">
                  <form onSubmit={handleAddComment} className="space-y-3 mb-4">
                    <Textarea
                      data-testid="new-comment-input"
                      value={newComment}
                      onChange={(e) => setNewComment(e.target.value)}
                      placeholder="Add a note..."
                      className="rounded-sm resize-none"
                      rows={3}
                    />
                    <Button data-testid="add-comment-btn" type="submit" size="sm" className="w-full rounded-sm">
                      Add Note
                    </Button>
                  </form>
                  <Separator className="my-4" />
                  <div className="space-y-3">
                    {comments.length === 0 ? (
                      <p className="text-sm text-muted-foreground text-center py-8">No notes yet</p>
                    ) : (
                      comments.map((comment) => (
                        <div key={comment.id} data-testid={`comment-${comment.id}`} className="p-3 border rounded-sm bg-accent/30">
                          <div className="flex items-start justify-between mb-2">
                            <span className="text-xs font-medium">{comment.user_name}</span>
                            <span className="text-xs text-muted-foreground">
                              {formatDate(comment.created_at)}
                            </span>
                          </div>
                          <p className="text-sm">{comment.content}</p>
                        </div>
                      ))
                    )}
                  </div>
                </TabsContent>
              </Tabs>
            </Card>

            {/* Pipeline Progress */}
            {docMeta?.pipeline_status && (
              <Card data-testid="pipeline-progress-card" className="p-4 bg-card/50 backdrop-blur-sm">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-heading font-semibold flex items-center gap-2">
                    <BookOpen className="h-4 w-4 text-primary" />
                    Publication Pipeline
                  </h3>
                  <span data-testid="pipeline-progress-text" className="text-xs font-mono text-muted-foreground">
                    {Object.values(docMeta.pipeline_status).filter(Boolean).length}/6
                  </span>
                </div>
                <div className="grid grid-cols-6 gap-1">
                  {[
                    { key: 'manuscript', label: 'Manuscript' },
                    { key: 'metadata', label: 'Metadata' },
                    { key: 'cover', label: 'Cover' },
                    { key: 'pdf', label: 'PDF' },
                    { key: 'epub', label: 'ePub' },
                    { key: 'audiobook', label: 'Audio' },
                  ].map((step) => {
                    const ok = !!docMeta.pipeline_status[step.key];
                    return (
                      <div
                        key={step.key}
                        data-testid={`pipeline-side-${step.key}`}
                        data-status={ok ? 'done' : 'pending'}
                        title={`${step.label} — ${ok ? 'Complete' : 'Pending'}`}
                        className={`h-6 rounded-sm border flex items-center justify-center transition-colors ${
                          ok
                            ? 'bg-emerald-50 border-emerald-300'
                            : 'bg-muted/30 border-border'
                        }`}
                      >
                        {ok ? <Check className="h-3 w-3 text-emerald-700" /> : <span className="text-[10px] text-muted-foreground">{step.label[0]}</span>}
                      </div>
                    );
                  })}
                </div>
              </Card>
            )}

            {/* Voice Memos */}
            <Card data-testid="voice-memos-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-2 flex items-center gap-2">
                <Mic className="h-4 w-4 text-primary" />
                Voice Memos
              </h3>
              <p className="text-xs text-muted-foreground mb-3 font-body">
                Record raw audio notes anchored to a paragraph. Play them back later or transcribe-and-insert into the manuscript.
              </p>

              <Button
                data-testid={memoRecording ? 'memo-stop-btn' : 'memo-record-btn'}
                size="sm"
                variant={memoRecording ? 'destructive' : 'default'}
                className="w-full rounded-sm"
                disabled={memoSaving}
                onClick={memoRecording ? stopMemoRecording : startMemoRecording}
              >
                {memoSaving ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</>
                ) : memoRecording ? (
                  <><MicOff className="h-4 w-4 mr-2" /> Stop & Save Memo</>
                ) : (
                  <><Mic className="h-4 w-4 mr-2" /> Record Voice Memo</>
                )}
              </Button>

              {memos.length > 0 && (
                <div className="mt-3 space-y-2 max-h-80 overflow-y-auto pr-1" data-testid="memos-list">
                  {memos.map((memo) => (
                    <VoiceMemoCard
                      key={memo.id}
                      memo={memo}
                      audioUrl={memoAudioUrls[memo.id]}
                      transcribing={memoTranscribing === memo.id}
                      onLoadAudio={() => loadMemoAudio(memo.id)}
                      onTranscribe={() => transcribeAndInsertMemo(memo)}
                      onDelete={() => deleteMemo(memo)}
                    />
                  ))}
                </div>
              )}
              {memos.length === 0 && !memoRecording && (
                <p data-testid="memos-empty" className="mt-3 text-[11px] text-muted-foreground italic text-center">
                  No memos yet — record one to get started.
                </p>
              )}
            </Card>

            {/* Dictation History */}
            {dictationHistory.length > 0 && (
              <Card data-testid="dictation-history-panel" className="p-4 bg-card/50 backdrop-blur-sm">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-heading font-semibold flex items-center gap-2">
                    <Mic className="h-4 w-4 text-primary" />
                    Dictation History
                  </h3>
                  <button
                    data-testid="dictation-clear-btn"
                    type="button"
                    className="text-[10px] text-muted-foreground hover:text-destructive underline"
                    onClick={clearDictationHistory}
                  >
                    Clear
                  </button>
                </div>
                <div className="space-y-2 max-h-72 overflow-y-auto pr-1" data-testid="dictation-history-list">
                  {dictationHistory.map((chunk) => (
                    <div
                      key={chunk.id}
                      data-testid={`dictation-chunk-${chunk.id}`}
                      className={`p-2 rounded-sm border text-xs leading-relaxed transition-opacity ${
                        chunk.undone ? 'opacity-50 line-through bg-muted/40' : 'bg-card hover:bg-accent/30'
                      }`}
                    >
                      <div className="flex items-start justify-between gap-2 mb-1">
                        <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
                          {new Date(chunk.insertedAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
                        </span>
                        {!chunk.undone && (
                          <button
                            data-testid={`dictation-undo-${chunk.id}`}
                            type="button"
                            className="text-[10px] text-muted-foreground hover:text-destructive flex items-center gap-0.5"
                            onClick={() => undoDictationChunk(chunk)}
                            title="Remove this dictation chunk from the manuscript"
                          >
                            <X className="h-2.5 w-2.5" /> Undo
                          </button>
                        )}
                      </div>
                      <p className="font-body line-clamp-4">{chunk.text}</p>
                    </div>
                  ))}
                </div>
                {isRecording && continuousMode && (
                  <div data-testid="continuous-recording-indicator" className="mt-3 flex items-center gap-2 p-2 rounded-sm bg-red-50 border border-red-200 text-[11px] text-red-900">
                    <span className="relative flex h-2 w-2">
                      <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                      <span className="relative inline-flex rounded-full h-2 w-2 bg-red-500"></span>
                    </span>
                    Recording in 30-second segments…
                  </div>
                )}
              </Card>
            )}

            {/* Book Setup — Cover + KDP Metadata */}
            <Card data-testid="book-setup-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3 flex items-center gap-2">
                <ImageIcon className="h-4 w-4 text-primary" />
                Book Setup
              </h3>
              <p className="text-xs text-muted-foreground mb-3 font-body">
                Cover art and KDP metadata — required before submission to Amazon KDP / Lulu.
              </p>

              {/* Cover image */}
              <div className="mb-4">
                <Label className="text-xs">Cover Image</Label>
                <div className="mt-1 flex gap-3 items-start">
                  {coverPreviewUrl ? (
                    <img
                      data-testid="cover-preview-img"
                      src={coverPreviewUrl}
                      alt="Cover preview"
                      className="h-24 w-16 rounded-sm object-cover border"
                    />
                  ) : (
                    <div className="h-24 w-16 rounded-sm border-2 border-dashed flex items-center justify-center">
                      <ImageIcon className="h-5 w-5 text-muted-foreground" />
                    </div>
                  )}
                  <div className="flex-1 space-y-2">
                    <label data-testid="cover-upload-label" className="block">
                      <input
                        data-testid="cover-upload-input"
                        type="file"
                        accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                        className="hidden"
                        onChange={(e) => uploadCoverFile(e.target.files?.[0])}
                      />
                      <Button
                        size="sm"
                        variant="outline"
                        className="w-full rounded-sm text-xs"
                        disabled={uploadingCover}
                        type="button"
                        onClick={(e) => e.currentTarget.previousSibling.click()}
                      >
                        {uploadingCover ? (<><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Uploading…</>) :
                          (<>{coverPreviewUrl ? 'Replace Cover' : 'Upload Cover'}</>)}
                      </Button>
                    </label>
                    {coverPreviewUrl && (
                      <>
                        <Button
                          data-testid="cover-pdf-btn"
                          size="sm"
                          variant="outline"
                          className="w-full rounded-sm text-xs"
                          disabled={downloadingCoverPdf}
                          onClick={downloadCoverPdf}
                        >
                          {downloadingCoverPdf ? (
                            <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Generating…</>
                          ) : (
                            <><FileDown className="h-3.5 w-3.5 mr-1" /> Download Full-Bleed Cover PDF</>
                          )}
                        </Button>
                        <Button
                          data-testid="cover-remove-btn"
                          size="sm"
                          variant="ghost"
                          className="w-full rounded-sm text-xs"
                          onClick={removeCover}
                        >
                          <Trash2 className="h-3.5 w-3.5 mr-1" /> Remove
                        </Button>
                      </>
                    )}
                    <p className="text-[10px] text-muted-foreground">JPG/PNG/WebP, ≤10 MB. KDP recommends 1600×2560.</p>
                  </div>
                </div>
              </div>

              {coverPreviewUrl && (
                <div className="mb-4 rounded-sm border border-primary/20 bg-primary/5 p-3 space-y-3" data-testid="cover-spread-panel">
                  <div>
                    <div className="text-xs font-semibold">Paperback Full Cover Studio</div>
                    <p className="text-[10px] text-muted-foreground mt-1">
                      Combines the back cover, calculated spine, and front cover into one KDP-ready PDF with 0.125-inch bleed. The white barcode area is reserved automatically.
                    </p>
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <Label className="text-[10px]">Final page count</Label>
                      <Input
                        data-testid="cover-page-count-input"
                        type="number"
                        min="24"
                        max="828"
                        value={metadata.page_count || ''}
                        onChange={(e) => updateMetadataField('page_count', Number(e.target.value) || null)}
                        placeholder="200"
                        className="h-8 rounded-sm text-xs"
                      />
                    </div>
                    <div>
                      <Label className="text-[10px]">Paper and ink</Label>
                      <Select value={coverPaperType} onValueChange={setCoverPaperType}>
                        <SelectTrigger data-testid="cover-paper-select" className="h-8 rounded-sm text-xs">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {COVER_PAPER_TYPES.map((paper) => (
                            <SelectItem key={paper.value} value={paper.value} className="text-xs">
                              {paper.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                  <label className="block">
                    <span className="text-[10px] font-medium">Back cover artwork</span>
                    <Input
                      data-testid="back-cover-input"
                      type="file"
                      accept=".jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
                      onChange={(e) => setBackCoverFile(e.target.files?.[0] || null)}
                      className="mt-1 h-9 rounded-sm text-[10px] file:text-[10px]"
                    />
                  </label>
                  <Button
                    data-testid="cover-spread-download-btn"
                    size="sm"
                    className="w-full rounded-sm text-xs"
                    onClick={downloadCoverSpread}
                    disabled={generatingCoverSpread || !backCoverFile}
                  >
                    {generatingCoverSpread ? (
                      <><Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" /> Building Full Cover</>
                    ) : (
                      <><FileDown className="h-3.5 w-3.5 mr-1" /> Export Back, Spine, and Front</>
                    )}
                  </Button>
                  {Number(metadata.page_count) > 0 && Number(metadata.page_count) < 80 && (
                    <p className="text-[10px] text-amber-700">KDP does not permit spine text below 80 pages. The app will leave the spine unlettered.</p>
                  )}
                </div>
              )}

              <Separator className="my-3" />

              {/* Metadata fields */}
              <div className="space-y-3">
                <div>
                  <Label className="text-xs">Author</Label>
                  <Input
                    data-testid="meta-author-input"
                    value={metadata.author || ''}
                    onChange={(e) => updateMetadataField('author', e.target.value)}
                    placeholder="Jane Q. Author"
                    className="rounded-sm h-9 text-xs"
                  />
                </div>
                <div>
                  <Label className="text-xs">Subtitle</Label>
                  <Input
                    data-testid="meta-subtitle-input"
                    value={metadata.subtitle || ''}
                    onChange={(e) => updateMetadataField('subtitle', e.target.value)}
                    placeholder="An optional subtitle"
                    className="rounded-sm h-9 text-xs"
                  />
                </div>
                <div>
                  <Label className="text-xs">Description (for KDP)</Label>
                  <Textarea
                    data-testid="meta-description-input"
                    value={metadata.description || ''}
                    onChange={(e) => updateMetadataField('description', e.target.value)}
                    placeholder="A short book description that appears on Amazon / Lulu listings."
                    className="rounded-sm text-xs min-h-[80px]"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <Label className="text-xs">ISBN</Label>
                    <Input
                      data-testid="meta-isbn-input"
                      value={metadata.isbn || ''}
                      onChange={(e) => updateMetadataField('isbn', e.target.value)}
                      placeholder="978-…"
                      className="rounded-sm h-9 text-xs font-mono"
                    />
                  </div>
                  <div>
                    <Label className="text-xs">Language</Label>
                    <Input
                      data-testid="meta-language-input"
                      value={metadata.language || 'English'}
                      onChange={(e) => updateMetadataField('language', e.target.value)}
                      className="rounded-sm h-9 text-xs"
                    />
                  </div>
                </div>
                <div>
                  <Label className="text-xs">Category</Label>
                  <Input
                    data-testid="meta-category-input"
                    value={metadata.category || ''}
                    onChange={(e) => updateMetadataField('category', e.target.value)}
                    placeholder="e.g. Self-Help > Leadership"
                    className="rounded-sm h-9 text-xs"
                  />
                </div>
                <div>
                  <Label className="text-xs">Keywords (comma-separated)</Label>
                  <Input
                    data-testid="meta-keywords-input"
                    value={(metadata.keywords || []).join(', ')}
                    onChange={(e) => updateMetadataField(
                      'keywords',
                      e.target.value.split(',').map((k) => k.trim()).filter(Boolean)
                    )}
                    placeholder="leadership, crisis, decisions"
                    className="rounded-sm h-9 text-xs"
                  />
                </div>
                <div>
                  <Label className="text-xs">Publisher</Label>
                  <Input
                    data-testid="meta-publisher-input"
                    value={metadata.publisher || ''}
                    onChange={(e) => updateMetadataField('publisher', e.target.value)}
                    placeholder="Divine Leadership Press"
                    className="rounded-sm h-9 text-xs"
                  />
                </div>
                <Button
                  data-testid="meta-save-btn"
                  size="sm"
                  className="w-full rounded-sm"
                  onClick={saveMetadata}
                  disabled={savingMetadata}
                >
                  {savingMetadata ? (<><Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" /> Saving…</>) :
                    (<><Save className="h-3.5 w-3.5 mr-2" /> Save Book Details</>)}
                </Button>
              </div>
            </Card>

            {/* Editor's Desk: Full Copy-Edit Pass */}
            <Card data-testid="editors-desk-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3 flex items-center gap-2">
                <ScanSearch className="h-4 w-4 text-primary" />
                Editor's Desk
              </h3>
              <p className="text-xs text-muted-foreground mb-3 font-body">
                Full copy-edit pass for grammar, punctuation, run-ons, passive voice, consistency, and clarity.
              </p>
              <div className="mb-3 rounded-sm border border-primary/20 bg-primary/5 p-2 text-[11px] leading-relaxed text-foreground" data-testid="house-style-notice">
                <strong>Author-Protective Mode:</strong> Your wording and meaning remain unchanged unless you explicitly request a rewrite. DLP suggestions never introduce em dashes.
              </div>

              <div className="mb-3">
                <Label className="text-xs">Style Guide</Label>
                <Select value={styleGuide} onValueChange={setStyleGuide}>
                  <SelectTrigger data-testid="style-guide-select" className="rounded-sm h-9 text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(styleGuides.length > 0 ? styleGuides : [
                      { key: 'chicago', description: 'Chicago Manual of Style' },
                      { key: 'ap', description: 'AP Stylebook' },
                      { key: 'mla', description: 'MLA Handbook' },
                      { key: 'house', description: 'DLP House Style' },
                    ]).map((g) => (
                      <SelectItem key={g.key} value={g.key} className="text-xs">
                        {g.key.toUpperCase()}: {g.description}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              <Button
                data-testid="run-copyedit-btn"
                size="sm"
                className="w-full rounded-sm"
                disabled={copyEditRunning}
                onClick={runCopyEdit}
              >
                {copyEditRunning ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Editing…</>
                ) : (
                  <><FileSearch className="h-4 w-4 mr-2" /> Run Full Edit</>
                )}
              </Button>

              {copyEditData && (
                <div className="mt-4 space-y-3" data-testid="copyedit-results">
                  {/* Readability dashboard */}
                  <div className="grid grid-cols-2 gap-2 p-3 bg-accent/30 rounded-sm border">
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">FK Grade</div>
                      <div data-testid="metric-fk-grade" className="text-base font-heading font-semibold">
                        {copyEditData.readability.fk_grade}
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Avg Sentence</div>
                      <div data-testid="metric-avg-sentence" className="text-base font-heading font-semibold">
                        {copyEditData.readability.avg_sentence_length} <span className="text-xs font-normal text-muted-foreground">words</span>
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Passive</div>
                      <div data-testid="metric-passive" className="text-base font-heading font-semibold">
                        {copyEditData.readability.passive_pct}%
                      </div>
                    </div>
                    <div>
                      <div className="text-[10px] uppercase tracking-wider text-muted-foreground">Adverbs</div>
                      <div data-testid="metric-adverbs" className="text-base font-heading font-semibold">
                        {copyEditData.readability.adverb_pct}%
                      </div>
                    </div>
                  </div>
                  {copyEditData.readability.longest_sentence_words > 35 && (
                    <div className="flex gap-2 p-2 rounded-sm border border-amber-200 bg-amber-50 text-xs">
                      <AlertCircle className="h-3.5 w-3.5 text-amber-700 flex-shrink-0 mt-0.5" />
                      <div>
                        <div className="font-semibold text-amber-900">Longest sentence: {copyEditData.readability.longest_sentence_words} words</div>
                        <div className="text-amber-800 line-clamp-3 mt-1">"{copyEditData.readability.longest_sentence}"</div>
                      </div>
                    </div>
                  )}

                  {/* Issue list */}
                  {copyEditData.issues.length > 0 && (
                    <>
                      <div className="flex items-center justify-between gap-2">
                        <Select value={issueFilter} onValueChange={setIssueFilter}>
                          <SelectTrigger data-testid="issue-filter-select" className="rounded-sm h-8 text-xs flex-1">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="all" className="text-xs">All issues ({copyEditData.issues.length})</SelectItem>
                            <SelectItem value="must_fix" className="text-xs">Must fix</SelectItem>
                            <SelectItem value="suggested" className="text-xs">Suggested</SelectItem>
                            <SelectItem value="stylistic" className="text-xs">Stylistic</SelectItem>
                          </SelectContent>
                        </Select>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          data-testid="accept-all-btn"
                          size="sm"
                          variant="outline"
                          className="flex-1 rounded-sm h-8 text-xs"
                          onClick={handleAcceptAll}
                        >
                          <Check className="h-3.5 w-3.5 mr-1" /> Accept All
                        </Button>
                        <Button
                          data-testid="reject-all-btn"
                          size="sm"
                          variant="ghost"
                          className="flex-1 rounded-sm h-8 text-xs"
                          onClick={handleRejectAll}
                        >
                          <X className="h-3.5 w-3.5 mr-1" /> Reject All
                        </Button>
                      </div>
                      <div className="space-y-2 max-h-[460px] overflow-y-auto pr-1" data-testid="issue-list">
                        {copyEditData.issues
                          .filter((i) => issueFilter === 'all' || i.severity === issueFilter)
                          .map((issue) => (
                            <CopyEditIssueCard
                              key={issue.id}
                              issue={issue}
                              onAccept={() => handleAcceptIssue(issue)}
                              onReject={() => handleRejectIssue(issue)}
                            />
                          ))}
                      </div>
                    </>
                  )}
                  {copyEditData.issues.length === 0 && (
                    <div className="flex items-center gap-2 p-3 rounded-sm border border-emerald-200 bg-emerald-50 text-xs text-emerald-900">
                      <Check className="h-4 w-4" />
                      Manuscript is clean — no issues remain.
                    </div>
                  )}
                </div>
              )}
            </Card>

            {/* AI Editorial Panel */}
            <Card data-testid="ai-editor-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3 flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-primary" />
                AI Editorial Polish
              </h3>
              <p className="text-xs text-muted-foreground mb-3 font-body">
                Claude Sonnet 4.5 — your silent associate editor.
              </p>
              <div className="grid grid-cols-1 gap-2">
                {[
                  { key: 'tighten', label: 'Tighten Prose' },
                  { key: 'clarity', label: 'Improve Clarity' },
                  { key: 'blurb', label: 'Back-Cover Blurb' },
                  { key: 'chapter_titles', label: 'Suggest Chapter Titles' },
                  { key: 'synopsis', label: 'Generate Synopsis' },
                ].map((t) => (
                  <Button
                    key={t.key}
                    data-testid={`ai-tool-${t.key}-btn`}
                    variant="outline"
                    size="sm"
                    className="w-full justify-start rounded-sm text-xs"
                    disabled={aiRunning !== null}
                    onClick={() => runAiTool(t.key)}
                  >
                    {aiRunning === t.key ? (
                      <Loader2 className="h-3.5 w-3.5 mr-2 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5 mr-2" />
                    )}
                    {t.label}
                  </Button>
                ))}
              </div>

              {aiResult && (
                <motion.div
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-4 border rounded-sm bg-accent/20"
                  data-testid="ai-result-preview"
                >
                  <div className="flex items-center justify-between px-3 py-2 border-b bg-accent/40">
                    <span className="text-xs font-semibold">{aiResult.label}</span>
                    <span className="text-[10px] uppercase tracking-wider text-muted-foreground">
                      Preview
                    </span>
                  </div>
                  <div
                    data-testid="ai-result-content"
                    className="p-3 text-sm font-body whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed"
                  >
                    {aiResult.result}
                  </div>
                  <div className="flex items-center gap-2 px-3 py-2 border-t bg-card">
                    <Button
                      data-testid="ai-apply-btn"
                      size="sm"
                      className="flex-1 rounded-sm h-8 text-xs"
                      onClick={applyAiResult}
                    >
                      <Check className="h-3.5 w-3.5 mr-1" />
                      {aiResult.result_type === 'prose' ? 'Replace Manuscript' : 'Append to Manuscript'}
                    </Button>
                    <Button
                      data-testid="ai-copy-btn"
                      variant="outline"
                      size="sm"
                      className="rounded-sm h-8 text-xs"
                      onClick={copyAiResult}
                    >
                      Copy
                    </Button>
                    <Button
                      data-testid="ai-discard-btn"
                      variant="ghost"
                      size="sm"
                      className="rounded-sm h-8 text-xs"
                      onClick={discardAiResult}
                    >
                      <X className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </motion.div>
              )}
            </Card>

            {/* Format Preview */}
            <Card data-testid="format-preview-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3 flex items-center gap-2">
                <FileType className="h-4 w-4" />
                Format Preview
              </h3>
              <div className="space-y-2 text-xs">
                <div className="p-2 bg-accent/20 rounded border">
                  <div className="font-medium mb-1">Current: {docMeta?.format}</div>
                  <div className="text-muted-foreground">
                    {docMeta?.format === '6x9' && 'Standard novel size (152×229mm)'}
                    {docMeta?.format === '5x8' && 'Digest size (127×203mm)'}
                    {docMeta?.format === '8.5x11' && 'Magazine size (216×279mm)'}
                    {docMeta?.format === 'epub' && 'Digital ebook format'}
                  </div>
                </div>
                <div className="text-muted-foreground">
                  Approx. pages: <strong className="text-foreground">{Math.ceil(wordCount / 250)}</strong>
                </div>
              </div>
            </Card>

            {/* Audio Studio — TTS + Audiobook (3 providers) */}
            <Card data-testid="audio-studio-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3 flex items-center gap-2">
                <Headphones className="h-4 w-4 text-primary" />
                Audio Studio
              </h3>
              <p className="text-xs text-muted-foreground mb-3 font-body">
                Pick a voice provider, preview, or render a downloadable audiobook.
              </p>

              <Tabs defaultValue="openai" className="w-full">
                <TabsList className="w-full grid grid-cols-3 h-8">
                  <TabsTrigger data-testid="audio-tab-openai" value="openai" className="text-[11px]">OpenAI</TabsTrigger>
                  <TabsTrigger data-testid="audio-tab-elevenlabs" value="elevenlabs" className="text-[11px]">ElevenLabs</TabsTrigger>
                  <TabsTrigger data-testid="audio-tab-upload" value="upload" className="text-[11px]">Uploaded</TabsTrigger>
                </TabsList>

                {/* --- OpenAI tab --- */}
                <TabsContent value="openai" className="space-y-3 mt-3">
                  <div>
                    <Label className="text-xs">Narrator Voice</Label>
                    <Select value={ttsVoice} onValueChange={setTtsVoice}>
                      <SelectTrigger data-testid="tts-voice-select" className="rounded-sm h-9 text-xs">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {(ttsVoices.length > 0 ? ttsVoices : [
                          { key: 'onyx', label: 'Onyx — Deep, authoritative' },
                          { key: 'nova', label: 'Nova — Energetic, upbeat' },
                          { key: 'fable', label: 'Fable — British, literary' },
                        ]).map((v) => (
                          <SelectItem key={v.key} value={v.key} className="text-xs">{v.label}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div>
                    <div className="flex items-center justify-between mb-1">
                      <Label className="text-xs">Speech Speed</Label>
                      <span data-testid="tts-speed-value" className="text-xs font-mono">{ttsSpeed.toFixed(2)}×</span>
                    </div>
                    <input
                      data-testid="tts-speed-slider"
                      type="range" min="0.5" max="2.0" step="0.05"
                      value={ttsSpeed}
                      onChange={(e) => setTtsSpeed(parseFloat(e.target.value))}
                      className="w-full accent-primary"
                    />
                  </div>
                  <Button data-testid="tts-preview-btn" variant="outline" size="sm" className="w-full rounded-sm"
                    disabled={previewLoading || audiobookLoading} onClick={playTtsPreview}>
                    {previewLoading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Synthesising…</>) :
                      (<><Play className="h-4 w-4 mr-2" /> Read Aloud (Preview)</>)}
                  </Button>
                  {previewAudioUrl && (
                    <audio data-testid="tts-preview-player" controls autoPlay src={previewAudioUrl} className="w-full mt-2 rounded-sm">
                      <track kind="captions" />
                    </audio>
                  )}
                  <Separator className="my-2" />
                  <Button data-testid="audiobook-download-btn" size="sm" className="w-full rounded-sm"
                    disabled={audiobookLoading || previewLoading} onClick={downloadAudiobook}>
                    {audiobookLoading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Rendering audiobook…</>) :
                      (<><Download className="h-4 w-4 mr-2" /> Generate Audiobook (MP3)</>)}
                  </Button>
                  <p className="text-[10px] text-muted-foreground text-center">
                    Full manuscripts up to ~17,000 words. Larger books — generate per chapter.
                  </p>

                  {/* Per-chapter export */}
                  <div className="mt-3 pt-3 border-t space-y-2">
                    <div className="flex items-center gap-2">
                      <FileDown className="h-3.5 w-3.5 text-primary" />
                      <span className="text-xs font-semibold">Per-chapter audiobook</span>
                    </div>
                    <p className="text-[10px] text-muted-foreground">
                      Split at H1/H2 headings and bundle one MP3 per chapter (ZIP). Perfect for
                      KDP Audible uploads.
                    </p>
                    <div className="flex gap-2">
                      <Button
                        data-testid="chapter-preview-btn"
                        size="sm"
                        variant="outline"
                        className="flex-1 rounded-sm"
                        disabled={chapterPreviewLoading || chapterAudiobookLoading}
                        onClick={fetchChapterPreview}
                      >
                        {chapterPreviewLoading ? (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ) : (
                          <ScanSearch className="h-3 w-3 mr-1" />
                        )}
                        Detect chapters
                      </Button>
                      <Button
                        data-testid="chapter-audiobook-btn"
                        size="sm"
                        className="flex-1 rounded-sm"
                        disabled={chapterAudiobookLoading || audiobookLoading || previewLoading}
                        onClick={downloadChapterAudiobook}
                      >
                        {chapterAudiobookLoading ? (
                          <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                        ) : (
                          <Download className="h-3 w-3 mr-1" />
                        )}
                        Export ZIP
                      </Button>
                    </div>
                    {chapterPreview && chapterPreview.chapters && (
                      <div
                        data-testid="chapter-preview-list"
                        className="rounded-sm border bg-muted/30 max-h-40 overflow-y-auto"
                      >
                        <div className="px-2 py-1.5 text-[10px] uppercase tracking-wider font-mono text-muted-foreground border-b bg-muted/40">
                          {chapterPreview.total} chapter{chapterPreview.total === 1 ? '' : 's'} detected
                        </div>
                        <ul className="divide-y">
                          {chapterPreview.chapters.map((ch) => (
                            <li
                              key={ch.index}
                              data-testid={`chapter-row-${ch.index}`}
                              className="px-2 py-1 flex items-center justify-between text-[11px]"
                            >
                              <span className="font-mono text-muted-foreground mr-2 flex-shrink-0">
                                {String(ch.index).padStart(2, '0')}
                              </span>
                              <span className="flex-1 truncate">{ch.title}</span>
                              <span className="font-mono text-[10px] text-muted-foreground flex-shrink-0 ml-2">
                                {ch.word_count.toLocaleString()}w
                              </span>
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </TabsContent>

                {/* --- ElevenLabs tab --- */}
                <TabsContent value="elevenlabs" className="space-y-3 mt-3">
                  {!hasElevenKey ? (
                    <div data-testid="eleven-key-setup" className="space-y-2">
                      <div className="flex items-start gap-2 p-2 rounded-sm border border-amber-200 bg-amber-50 text-[11px] text-amber-900">
                        <AlertCircle className="h-3.5 w-3.5 flex-shrink-0 mt-0.5" />
                        <div>Paste your ElevenLabs API key to access stock voices, voice cloning, and premium narration. Get one at <span className="font-semibold">elevenlabs.io → Settings → API Keys</span>.</div>
                      </div>
                      <Input
                        data-testid="eleven-key-input"
                        type="password"
                        placeholder="sk_..."
                        value={elevenKeyInput}
                        onChange={(e) => setElevenKeyInput(e.target.value)}
                        className="rounded-sm h-9 text-xs font-mono"
                      />
                      <Button
                        data-testid="eleven-save-key-btn"
                        size="sm"
                        className="w-full rounded-sm"
                        disabled={savingElevenKey || !elevenKeyInput.trim()}
                        onClick={saveElevenKey}
                      >
                        {savingElevenKey ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Saving…</>) : 'Save Key'}
                      </Button>
                    </div>
                  ) : (
                    <>
                      <div className="flex items-center justify-between text-[11px]">
                        <span data-testid="eleven-connected-label" className="flex items-center gap-1 text-emerald-700">
                          <Check className="h-3 w-3" /> Connected to ElevenLabs
                        </span>
                        <button
                          data-testid="eleven-clear-key-btn"
                          type="button"
                          className="text-muted-foreground hover:text-destructive underline"
                          onClick={clearElevenKey}
                        >
                          Remove key
                        </button>
                      </div>
                      <div>
                        <Label className="text-xs">Stock / Cloned Voice</Label>
                        <Select value={elevenVoiceId} onValueChange={setElevenVoiceId}>
                          <SelectTrigger data-testid="eleven-voice-select" className="rounded-sm h-9 text-xs">
                            <SelectValue placeholder={elevenLoadingVoices ? 'Loading…' : 'Select a voice'} />
                          </SelectTrigger>
                          <SelectContent>
                            {elevenVoices.map((v) => (
                              <SelectItem key={v.voice_id} value={v.voice_id} className="text-xs">
                                {v.name} {v.category && v.category !== 'generated' ? `(${v.category})` : ''}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <button
                          data-testid="eleven-refresh-voices-btn"
                          type="button"
                          className="text-[10px] text-muted-foreground hover:text-primary underline mt-1"
                          onClick={fetchElevenVoices}
                        >
                          Refresh voice list
                        </button>
                      </div>
                      <div>
                        <Label className="text-xs">Or paste a custom Voice ID (e.g. cloned voice)</Label>
                        <Input
                          data-testid="eleven-custom-voice-input"
                          value={elevenCustomVoiceId}
                          onChange={(e) => setElevenCustomVoiceId(e.target.value)}
                          placeholder="21m00Tcm4Tlvxxxxxxxxx"
                          className="rounded-sm h-9 text-xs font-mono"
                        />
                      </div>
                      <Button
                        data-testid="eleven-preview-btn"
                        variant="outline"
                        size="sm"
                        className="w-full rounded-sm"
                        disabled={elevenPreviewLoading || elevenAudiobookLoading}
                        onClick={playElevenPreview}
                      >
                        {elevenPreviewLoading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Synthesising…</>) :
                          (<><Play className="h-4 w-4 mr-2" /> Preview with ElevenLabs</>)}
                      </Button>
                      {elevenPreviewUrl && (
                        <audio data-testid="eleven-preview-player" controls autoPlay src={elevenPreviewUrl} className="w-full mt-2 rounded-sm">
                          <track kind="captions" />
                        </audio>
                      )}
                      <Separator className="my-2" />
                      <Button
                        data-testid="eleven-audiobook-btn"
                        size="sm"
                        className="w-full rounded-sm"
                        disabled={elevenAudiobookLoading || elevenPreviewLoading}
                        onClick={downloadElevenAudiobook}
                      >
                        {elevenAudiobookLoading ? (<><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Rendering audiobook…</>) :
                          (<><Download className="h-4 w-4 mr-2" /> Generate Audiobook (ElevenLabs)</>)}
                      </Button>
                      <p className="text-[10px] text-muted-foreground text-center">
                        Up to ~17,000 words per run. Uses your ElevenLabs quota.
                      </p>
                    </>
                  )}
                </TabsContent>

                {/* --- Upload tab --- */}
                <TabsContent value="upload" className="space-y-3 mt-3">
                  <p className="text-[11px] text-muted-foreground">
                    Already have an audiobook? Upload an MP3, WAV, M4A, OGG, or FLAC file (≤200 MB) to attach it to this manuscript.
                  </p>
                  <label
                    data-testid="audiobook-upload-label"
                    className="block w-full p-4 border-2 border-dashed rounded-sm text-center cursor-pointer hover:bg-accent/30 transition-colors text-xs"
                  >
                    <input
                      data-testid="audiobook-upload-input"
                      type="file"
                      accept="audio/mpeg,audio/mp3,audio/wav,audio/m4a,audio/ogg,audio/flac,.mp3,.wav,.m4a,.ogg,.flac"
                      className="hidden"
                      onChange={(e) => uploadAudiobookFile(e.target.files?.[0])}
                    />
                    {uploadingAudiobook ? (
                      <span className="flex items-center justify-center gap-2"><Loader2 className="h-4 w-4 animate-spin" /> Uploading…</span>
                    ) : (
                      <>Click or drop a file here</>
                    )}
                  </label>
                  {uploadedAudiobookInfo?.uploaded && (
                    <div data-testid="uploaded-audiobook-status" className="space-y-2">
                      <div className="flex items-center justify-between text-[11px] text-emerald-700">
                        <span className="flex items-center gap-1">
                          <Check className="h-3 w-3" /> {uploadedAudiobookInfo.filename} ({Math.round(uploadedAudiobookInfo.size_bytes / 1024)} KB)
                        </span>
                        <button
                          data-testid="audiobook-remove-btn"
                          type="button"
                          className="text-muted-foreground hover:text-destructive underline"
                          onClick={deleteUploadedAudiobook}
                        >
                          Remove
                        </button>
                      </div>
                      {uploadedPlayerUrl && (
                        <audio data-testid="uploaded-audiobook-player" controls src={uploadedPlayerUrl} className="w-full rounded-sm">
                          <track kind="captions" />
                        </audio>
                      )}
                    </div>
                  )}
                </TabsContent>
              </Tabs>
            </Card>

            {/* Export & Publish */}
            <Card data-testid="export-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3">Export & Publish</h3>
              <div className="space-y-3">
                <div>
                  <Label className="text-xs">KDP Trim Size (PDF)</Label>
                  <Select value={pdfTrim} onValueChange={setPdfTrim}>
                    <SelectTrigger data-testid="pdf-trim-select" className="rounded-sm h-9 text-xs">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(trimSizes.length > 0 ? trimSizes : [
                        { key: '6x9', label: '6×9 — Standard novel' },
                        { key: '5x8', label: '5×8 — Mass-market' },
                        { key: '5.5x8.5', label: '5.5×8.5 — Digest' },
                        { key: '8.5x11', label: '8.5×11 — Magazine' },
                      ]).map((t) => (
                        <SelectItem key={t.key} value={t.key} className="text-xs">
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <Button
                  data-testid="export-pdf-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handleExport('pdf', pdfTrim)}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download PDF
                </Button>
                <Button
                  data-testid="export-epub-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handleExport('epub')}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Download ePub
                </Button>
                <Separator className="my-2" />
                <Button
                  data-testid="publish-kdp-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handlePublish('kdp')}
                >
                  <Globe className="h-4 w-4 mr-2" />
                  Prepare for Amazon KDP
                </Button>
                <Button
                  data-testid="publish-lulu-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handlePublish('lulu')}
                >
                  <Globe className="h-4 w-4 mr-2" />
                  Prepare for Lulu
                </Button>
                <Button
                  data-testid="publish-ingram-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => navigate(`/publishing?document=${documentId}`)}
                >
                  <Globe className="h-4 w-4 mr-2" />
                  Prepare for IngramSpark
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>

      {/* Writing Agent — chat sidebar */}
      <WritingAgentPanel
        documentId={documentId}
        editorRef={quillRef}
        open={agentOpen}
        onClose={() => setAgentOpen(false)}
      />

      {/* Floating "Cmd-K" hint when nothing is open */}
      {!cmdkOpen && !agentOpen && (
        <button
          data-testid="cmdk-hint-btn"
          type="button"
          onClick={() => {
            const quill = quillRef.current?.getEditor?.();
            if (quill) {
              const range = quill.getSelection();
              const selectionText = range && range.length > 0
                ? quill.getText(range.index, range.length)
                : '';
              setCmdkSelection(selectionText.trim());
              setCmdkRange(range);
            }
            setCmdkOpen(true);
          }}
          className="fixed bottom-4 left-4 z-30 px-3 py-2 rounded-sm border bg-card/95 backdrop-blur-md shadow-lg flex items-center gap-2 text-xs hover:bg-primary hover:text-primary-foreground transition-colors"
          title="Highlight text then press Cmd/Ctrl-K"
        >
          <Wand2 className="h-3.5 w-3.5" />
          <span className="font-mono uppercase tracking-wider">⌘K</span>
          <span className="hidden sm:inline text-muted-foreground">Inline rewrite</span>
        </button>
      )}

      <InlineCommandBar
        open={cmdkOpen}
        onClose={() => setCmdkOpen(false)}
        documentId={documentId}
        selectedText={cmdkSelection}
        onAccept={applyCmdkResult}
      />
    </div>
  );
}
