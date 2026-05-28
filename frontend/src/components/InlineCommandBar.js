/**
 * InlineCommandBar — Cmd-K dialog for inline rewrites.
 *
 * Workflow:
 *   1. User highlights text in the editor.
 *   2. User hits Cmd/Ctrl + K (the parent EditorPage opens this component).
 *   3. User types an instruction like "make this more formal".
 *   4. Backend returns a rewritten version → user previews & accepts / rejects.
 *
 * Props:
 *   open, onClose       - controlled visibility
 *   documentId          - for voice-matching context
 *   selectedText        - the text currently highlighted in Quill
 *   onAccept(newText)   - parent applies the new text back to the editor
 */
import { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { toast } from 'sonner';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Loader2, Wand2, Check, X, RefreshCw } from 'lucide-react';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` },
});

const QUICK_COMMANDS = [
  'Make this more formal',
  'Make this more conversational',
  'Tighten without losing meaning',
  'Expand into two paragraphs',
  'Rewrite in active voice',
  'Add a sensory detail',
];

export default function InlineCommandBar({
  open,
  onClose,
  documentId,
  selectedText,
  onAccept,
}) {
  const [instruction, setInstruction] = useState('');
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef(null);

  useEffect(() => {
    if (open) {
      setInstruction('');
      setResult('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const run = async (presetInstruction) => {
    const inst = (presetInstruction || instruction).trim();
    if (!inst) {
      toast.error('Type an instruction first');
      return;
    }
    if (!selectedText?.trim()) {
      toast.error('Highlight some text in the editor first');
      return;
    }
    setLoading(true);
    setResult('');
    try {
      const r = await axios.post(
        `${API}/ai/agent/command`,
        {
          document_id: documentId,
          selected_text: selectedText,
          instruction: inst,
        },
        getAuthHeaders(),
      );
      setResult(r.data?.result || '');
    } catch (error) {
      toast.error(error.response?.data?.detail || 'Command failed');
    } finally {
      setLoading(false);
    }
  };

  if (!open) return null;

  return (
    <div
      data-testid="inline-command-overlay"
      className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh] bg-black/30 backdrop-blur-sm"
      onClick={onClose}
    >
      <Card
        data-testid="inline-command-bar"
        className="w-[640px] max-w-[92vw] p-5 shadow-2xl border-2 border-primary/40 rounded-sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-2 mb-3">
          <Wand2 className="h-4 w-4 text-primary" />
          <span className="text-[10px] uppercase tracking-[0.22em] font-mono text-muted-foreground">
            Inline command · Cmd-K
          </span>
          <Button
            data-testid="inline-command-close"
            variant="ghost"
            size="sm"
            className="ml-auto h-7 w-7 p-0 rounded-sm"
            onClick={onClose}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="mb-3 p-2 rounded-sm bg-muted/50 border text-xs text-muted-foreground font-body italic max-h-20 overflow-y-auto">
          {selectedText
            ? <>"{selectedText.slice(0, 240)}{selectedText.length > 240 ? '…' : ''}"</>
            : 'No text selected — close this and highlight a passage first.'}
        </div>

        <div className="flex gap-2 mb-3">
          <Input
            ref={inputRef}
            data-testid="inline-command-input"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') run();
              if (e.key === 'Escape') onClose();
            }}
            placeholder="Rewrite this as…  (e.g. more formal, more vivid, two paragraphs)"
            className="text-sm rounded-sm flex-1"
            disabled={loading || !selectedText}
          />
          <Button
            data-testid="inline-command-run"
            onClick={() => run()}
            disabled={loading || !instruction.trim() || !selectedText}
            size="sm"
            className="rounded-sm"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Run'}
          </Button>
        </div>

        {!result && !loading && (
          <div className="flex flex-wrap gap-1.5">
            {QUICK_COMMANDS.map((c) => (
              <Button
                key={c}
                data-testid={`inline-quick-${c.toLowerCase().replace(/\s+/g, '-')}`}
                variant="outline"
                size="sm"
                className="h-7 text-xs rounded-sm"
                onClick={() => { setInstruction(c); run(c); }}
                disabled={!selectedText}
              >
                {c}
              </Button>
            ))}
          </div>
        )}

        {loading && (
          <div className="py-6 flex items-center justify-center gap-2 text-xs text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Drafting…
          </div>
        )}

        {result && !loading && (
          <div data-testid="inline-command-result" className="mt-3 border-t pt-3">
            <div className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground mb-1.5">
              Proposed rewrite
            </div>
            <div className="p-3 rounded-sm bg-primary/5 border border-primary/20 text-sm font-body whitespace-pre-wrap max-h-64 overflow-y-auto">
              {result}
            </div>
            <div className="flex gap-2 mt-3 justify-end">
              <Button
                data-testid="inline-command-retry"
                variant="ghost"
                size="sm"
                onClick={() => run()}
                className="rounded-sm"
              >
                <RefreshCw className="h-3 w-3 mr-1" /> Retry
              </Button>
              <Button
                data-testid="inline-command-reject"
                variant="outline"
                size="sm"
                onClick={onClose}
                className="rounded-sm"
              >
                <X className="h-3 w-3 mr-1" /> Reject
              </Button>
              <Button
                data-testid="inline-command-accept"
                size="sm"
                onClick={() => { onAccept(result); onClose(); }}
                className="rounded-sm"
              >
                <Check className="h-3 w-3 mr-1" /> Replace selection
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
