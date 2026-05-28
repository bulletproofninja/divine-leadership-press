/**
 * WritingAgentPanel — collapsible chat sidebar that lives next to the editor.
 *
 * Props:
 *   documentId        – current doc id (drives history persistence)
 *   editorRef         – React ref to the Quill editor instance (for "insert at cursor")
 *   open              – boolean; controlled by parent
 *   onClose           – close handler
 *   onApplyToEditor   – fallback insert handler if editorRef can't do it
 */
import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Textarea } from '../components/ui/textarea';
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from '../components/ui/select';
import {
  Sparkles, X, Send, Loader2, Trash2, ClipboardCopy, PenLine, BotMessageSquare,
} from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
});

const STARTERS = [
  { label: 'Brainstorm next chapter', text: "I'm stuck — help me brainstorm what should happen in the next chapter. Ask me 2-3 short questions first if you need to." },
  { label: 'Polish current page', text: 'Read what I have so far and tell me the single weakest paragraph + how to fix it.' },
  { label: 'Find my hook', text: 'What is the strongest opening hook hiding in what I\'ve already written? Quote it back.' },
  { label: 'Draft an outline', text: 'Based on what I\'ve drafted, propose a 7-chapter outline for the rest of the book.' },
];

function InsertActions({ text, onInsert, onReplace }) {
  return (
    <div className="flex gap-1 mt-2">
      <Button
        data-testid="agent-msg-insert"
        size="sm"
        variant="ghost"
        className="h-7 text-xs rounded-sm"
        onClick={() => onInsert(text)}
      >
        <PenLine className="h-3 w-3 mr-1" /> Insert
      </Button>
      <Button
        data-testid="agent-msg-replace"
        size="sm"
        variant="ghost"
        className="h-7 text-xs rounded-sm"
        onClick={() => onReplace(text)}
      >
        Replace selection
      </Button>
      <Button
        data-testid="agent-msg-copy"
        size="sm"
        variant="ghost"
        className="h-7 text-xs rounded-sm"
        onClick={() => {
          navigator.clipboard.writeText(text);
          toast.success('Copied');
        }}
      >
        <ClipboardCopy className="h-3 w-3" />
      </Button>
    </div>
  );
}

export default function WritingAgentPanel({
  documentId,
  editorRef,
  open,
  onClose,
  onApplyToEditor,
}) {
  const [voices, setVoices] = useState([]);
  const [voice, setVoice] = useState('match_my_voice');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const endRef = useRef(null);

  // Load voices + saved history on first mount / when doc changes
  useEffect(() => {
    let cancelled = false;
    axios.get(`${API}/ai/agent/voices`)
      .then((r) => { if (!cancelled) setVoices(r.data?.voices || []); })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    if (!documentId) return;
    setLoaded(false);
    axios.get(`${API}/ai/agent/history/${documentId}`, getAuthHeaders())
      .then((r) => {
        setMessages(r.data?.messages || []);
        if (r.data?.voice) setVoice(r.data.voice);
      })
      .catch(() => setMessages([]))
      .finally(() => setLoaded(true));
  }, [documentId]);

  useEffect(() => {
    if (open && endRef.current) {
      endRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
  }, [messages, open]);

  const sendMessage = async (preset) => {
    const text = (preset || input).trim();
    if (!text || sending) return;
    setSending(true);
    const userMsg = { role: 'user', content: text, ts: new Date().toISOString() };
    setMessages((m) => [...m, userMsg]);
    setInput('');
    try {
      const r = await axios.post(
        `${API}/ai/agent/chat`,
        { document_id: documentId, message: text, voice },
        getAuthHeaders(),
      );
      const reply = r.data?.reply || '';
      setMessages((m) => [
        ...m,
        { role: 'assistant', content: reply, ts: new Date().toISOString() },
      ]);
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Agent did not respond');
      setMessages((m) => m.slice(0, -1));  // roll back the optimistic user message
    } finally {
      setSending(false);
    }
  };

  const clearHistory = async () => {
    if (!documentId) return;
    if (!window.confirm('Clear this conversation? The agent will start fresh.')) return;
    try {
      await axios.delete(`${API}/ai/agent/history/${documentId}`, getAuthHeaders());
      setMessages([]);
      toast.success('Conversation cleared');
    } catch (error) {
      toast.error('Could not clear history');
    }
  };

  // Insert reply at cursor / replace selection — uses Quill's editor handle when available
  const insertIntoEditor = (text, replaceSelection = false) => {
    const quill = editorRef?.current?.getEditor?.();
    if (quill) {
      const range = quill.getSelection(true);
      if (replaceSelection && range && range.length > 0) {
        quill.deleteText(range.index, range.length, 'user');
      }
      const index = (range && range.index) ?? quill.getLength();
      // Drop a paragraph break before/after for readability
      const insertText = (range && range.length === 0 ? '\n' : '') + text + '\n';
      quill.insertText(index, insertText, 'user');
      quill.setSelection(index + insertText.length, 0, 'user');
      toast.success(replaceSelection ? 'Selection replaced' : 'Inserted into manuscript');
      return;
    }
    if (typeof onApplyToEditor === 'function') {
      onApplyToEditor(text, replaceSelection);
      return;
    }
    navigator.clipboard.writeText(text);
    toast.info('Copied to clipboard (editor not ready)');
  };

  if (!open) return null;

  return (
    <Card
      data-testid="writing-agent-panel"
      className="fixed right-4 bottom-4 z-40 w-[380px] sm:w-[420px] max-h-[80vh] flex flex-col shadow-2xl border-2 border-primary/30 bg-card/95 backdrop-blur-md rounded-sm"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b">
        <div className="flex items-center gap-2 min-w-0">
          <span className="p-1.5 rounded-sm bg-primary/10 text-primary">
            <BotMessageSquare className="h-4 w-4" />
          </span>
          <div className="min-w-0">
            <div className="text-sm font-heading font-semibold leading-tight">
              Writing Agent
            </div>
            <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
              Claude · {voice.replace(/_/g, ' ')}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {messages.length > 0 && (
            <Button
              data-testid="agent-clear-btn"
              variant="ghost"
              size="sm"
              className="h-7 w-7 p-0 rounded-sm"
              onClick={clearHistory}
              title="Clear conversation"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            data-testid="agent-close-btn"
            variant="ghost"
            size="sm"
            className="h-7 w-7 p-0 rounded-sm"
            onClick={onClose}
            title="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Voice picker */}
      <div className="px-4 py-2 border-b">
        <Select value={voice} onValueChange={setVoice}>
          <SelectTrigger
            data-testid="agent-voice-select"
            className="rounded-sm h-8 text-xs"
          >
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {voices.map((v) => (
              <SelectItem key={v.key} value={v.key} className="text-xs">
                <div className="flex flex-col">
                  <span className="font-medium">{v.label}</span>
                  <span className="text-[10px] text-muted-foreground">{v.description}</span>
                </div>
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Messages */}
      <div
        data-testid="agent-messages"
        className="flex-1 overflow-y-auto px-4 py-3 space-y-3 text-sm min-h-[200px]"
      >
        {!loaded && (
          <div className="flex justify-center py-6">
            <Loader2 className="h-4 w-4 animate-spin text-primary" />
          </div>
        )}

        {loaded && messages.length === 0 && (
          <div className="space-y-3 py-2">
            <div className="text-xs text-muted-foreground italic">
              I've read your manuscript so far. What do you want to work on?
            </div>
            <div className="grid grid-cols-1 gap-1.5">
              {STARTERS.map((s) => (
                <Button
                  key={s.label}
                  data-testid={`agent-starter-${s.label.toLowerCase().replace(/\s+/g, '-')}`}
                  variant="outline"
                  size="sm"
                  className="justify-start h-auto py-2 text-left text-xs rounded-sm whitespace-normal"
                  onClick={() => sendMessage(s.text)}
                  disabled={sending}
                >
                  <Sparkles className="h-3 w-3 mr-2 flex-shrink-0 text-primary" />
                  {s.label}
                </Button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            data-testid={`agent-message-${m.role}`}
            className={m.role === 'user'
              ? 'ml-6 p-2 rounded-sm bg-primary/10 border border-primary/20 whitespace-pre-wrap'
              : 'mr-2 p-2 rounded-sm bg-muted/40 border whitespace-pre-wrap font-body'}
          >
            <div className="text-[9px] uppercase tracking-wider font-mono text-muted-foreground mb-1">
              {m.role === 'user' ? 'You' : 'Agent'}
            </div>
            {m.content}
            {m.role === 'assistant' && (
              <InsertActions
                text={m.content}
                onInsert={(t) => insertIntoEditor(t, false)}
                onReplace={(t) => insertIntoEditor(t, true)}
              />
            )}
          </div>
        ))}

        {sending && (
          <div className="mr-2 p-2 rounded-sm bg-muted/40 border flex items-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-3 w-3 animate-spin" /> Thinking…
          </div>
        )}
        <div ref={endRef} />
      </div>

      {/* Composer */}
      <div className="px-3 py-2 border-t">
        <div className="flex items-end gap-2">
          <Textarea
            data-testid="agent-input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                e.preventDefault();
                sendMessage();
              }
            }}
            placeholder="Ask, brainstorm, or paste a passage to rewrite…"
            className="text-sm rounded-sm min-h-[40px] resize-none flex-1"
            rows={2}
            disabled={sending}
          />
          <Button
            data-testid="agent-send-btn"
            size="sm"
            onClick={() => sendMessage()}
            disabled={sending || !input.trim()}
            className="rounded-sm"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
        <p className="text-[10px] text-muted-foreground mt-1 font-mono">
          ⌘/Ctrl + Enter to send
        </p>
      </div>
    </Card>
  );
}
