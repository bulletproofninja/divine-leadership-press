import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, FileText, Upload, LogOut, Search, Calendar, File, Trash2, Edit, ImageIcon, BookOpen, FileType, Headphones, HelpCircle, Shield, CreditCard, DollarSign } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger, DialogDescription, DialogFooter } from '../components/ui/dialog';
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from '../components/ui/alert-dialog';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_book-press/artifacts/gwdawx4q_Divine%20Leadership%20Press%20Emblem%281%29.png';

const PIPELINE_STEPS = [
  { key: 'manuscript', label: 'Manuscript', icon: Edit },
  { key: 'metadata', label: 'Metadata', icon: FileText },
  { key: 'cover', label: 'Cover', icon: ImageIcon },
  { key: 'pdf', label: 'PDF', icon: BookOpen },
  { key: 'epub', label: 'ePub', icon: FileType },
  { key: 'audiobook', label: 'Audio', icon: Headphones },
];

function PipelineBadges({ status, docId }) {
  const s = status || {};
  const done = PIPELINE_STEPS.filter((step) => s[step.key]).length;
  return (
    <div data-testid={`pipeline-${docId}`} className="mt-3 pt-3 border-t border-border/60">
      <div className="flex items-center justify-between mb-1.5">
        <span className="text-[10px] uppercase tracking-wider font-mono text-muted-foreground">
          Pipeline
        </span>
        <span data-testid={`pipeline-progress-${docId}`} className="text-[10px] font-mono text-muted-foreground">
          {done}/{PIPELINE_STEPS.length}
        </span>
      </div>
      <div className="flex items-center gap-1.5">
        {PIPELINE_STEPS.map((step) => {
          const Icon = step.icon;
          const ok = !!s[step.key];
          return (
            <div
              key={step.key}
              data-testid={`pipeline-step-${docId}-${step.key}`}
              data-status={ok ? 'done' : 'pending'}
              title={`${step.label} — ${ok ? 'Complete' : 'Pending'}`}
              className={`flex-1 flex items-center justify-center h-7 rounded-sm border transition-colors ${
                ok
                  ? 'bg-emerald-50 border-emerald-300 text-emerald-700'
                  : 'bg-muted/30 border-border text-muted-foreground/60'
              }`}
            >
              <Icon className="h-3 w-3" />
            </div>
          );
        })}
      </div>
    </div>
  );
}

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

function CoverThumbnail({ docId, hasCover }) {
  const [src, setSrc] = useState(null);
  useEffect(() => {
    let url = null;
    if (!hasCover) return undefined;
    (async () => {
      try {
        const r = await axios.get(`${API}/documents/${docId}/cover`, {
          ...getAuthHeaders(),
          responseType: 'blob',
        });
        url = window.URL.createObjectURL(r.data);
        setSrc(url);
      } catch (_) {
        setSrc(null);
      }
    })();
    return () => {
      if (url) window.URL.revokeObjectURL(url);
    };
  }, [docId, hasCover]);

  if (!hasCover || !src) {
    return (
      <div className="p-2 rounded-md bg-primary/10">
        <File className="h-6 w-6 text-primary" />
      </div>
    );
  }
  return (
    <img
      data-testid={`cover-thumb-${docId}`}
      src={src}
      alt="Cover"
      className="h-14 w-10 rounded-sm object-cover border border-border/60"
    />
  );
}

export default function Dashboard({ user, onLogout }) {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [newDocTitle, setNewDocTitle] = useState('');
  const [newDocFormat, setNewDocFormat] = useState('6x9');
  const [uploading, setUploading] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [documentToDelete, setDocumentToDelete] = useState(null);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await axios.get(`${API}/documents`, getAuthHeaders());
      setDocuments(response.data);
    } catch (error) {
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateDocument = async (e) => {
    e.preventDefault();
    try {
      const response = await axios.post(
        `${API}/documents`,
        { title: newDocTitle, format: newDocFormat },
        getAuthHeaders()
      );
      toast.success('Document created');
      setShowNewDialog(false);
      setNewDocTitle('');
      navigate(`/editor/${response.data.id}`);
    } catch (error) {
      toast.error('Failed to create document');
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API}/documents/upload`, formData, {
        ...getAuthHeaders(),
        headers: {
          ...getAuthHeaders().headers,
          'Content-Type': 'multipart/form-data'
        }
      });

      toast.success('Document uploaded');
      navigate(`/editor/${response.data.id}`);
    } catch (error) {
      const detail = error.response?.data?.detail || 'Failed to upload document';
      toast.error(detail, { duration: 8000 });
    } finally {
      setUploading(false);
      e.target.value = '';
    }
  };

  const filteredDocuments = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleDeleteDocument = async () => {
    if (!documentToDelete) return;

    try {
      await axios.delete(`${API}/documents/${documentToDelete.id}`, getAuthHeaders());
      toast.success('Document deleted');
      setDocuments(documents.filter(doc => doc.id !== documentToDelete.id));
      setDeleteDialogOpen(false);
      setDocumentToDelete(null);
    } catch (error) {
      toast.error('Failed to delete document');
    }
  };

  const openDeleteDialog = (doc, e) => {
    e.stopPropagation();
    setDocumentToDelete(doc);
    setDeleteDialogOpen(true);
  };

  const formatDate = (dateString) => {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  };

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur-md">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <img src={LOGO_URL} alt="Divine Leadership Press" className="h-10 w-10" />
            <h1 className="text-xl sm:text-2xl font-heading font-bold">Divine Leadership Press</h1>
          </div>
          <div className="flex items-center gap-4">
            <span className="text-sm font-body text-muted-foreground hidden sm:block">
              Welcome, <span className="text-foreground font-medium">{user.name}</span>
            </span>
            <Button
              data-testid="help-link-dashboard"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/help')}
              className="rounded-sm"
              title="Help & Documentation"
            >
              <HelpCircle className="h-4 w-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Help</span>
            </Button>
            <Button
              data-testid="billing-link-dashboard"
              variant="ghost"
              size="sm"
              onClick={() => navigate('/billing')}
              className="rounded-sm"
              title="Plans & Billing"
            >
              <CreditCard className="h-4 w-4 sm:mr-1.5" />
              <span className="hidden sm:inline">Plans</span>
            </Button>
            {user?.is_super_admin && (
              <Button
                data-testid="admin-link-dashboard"
                variant="ghost"
                size="sm"
                onClick={() => navigate('/admin/affiliate')}
                className="rounded-sm text-primary"
                title="Owner — Affiliate Settings"
              >
                <Shield className="h-4 w-4 sm:mr-1.5" />
                <span className="hidden sm:inline">Admin</span>
              </Button>
            )}
            {user?.is_super_admin && (
              <Button
                data-testid="commissions-link-dashboard"
                variant="ghost"
                size="sm"
                onClick={() => navigate('/admin/commissions')}
                className="rounded-sm text-primary"
                title="Owner — Commissions & Payouts"
              >
                <DollarSign className="h-4 w-4 sm:mr-1.5" />
                <span className="hidden sm:inline">Payouts</span>
              </Button>
            )}
            <Button data-testid="logout-btn" variant="ghost" size="sm" onClick={onLogout} className="rounded-sm">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <div className="container mx-auto px-4 py-8 max-w-7xl">
        {/* Actions Bar */}
        <div className="mb-8 flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
          <div className="flex-1 max-w-md">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                data-testid="search-input"
                type="text"
                placeholder="Search documents..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-10 rounded-sm"
              />
            </div>
          </div>
          <div className="flex gap-3">
            <Button
              data-testid="upload-document-btn"
              variant="outline"
              className="rounded-sm"
              disabled={uploading}
              onClick={() => document.getElementById('file-upload').click()}
            >
              <Upload className="h-4 w-4 mr-2" />
              {uploading ? 'Uploading...' : 'Upload'}
            </Button>
            <input
              id="file-upload"
              type="file"
              accept=".docx,.txt,.pages"
              className="hidden"
              onChange={handleFileUpload}
            />
            <Dialog open={showNewDialog} onOpenChange={setShowNewDialog}>
              <DialogTrigger asChild>
                <Button data-testid="new-document-btn" className="rounded-sm">
                  <Plus className="h-4 w-4 mr-2" />
                  New Document
                </Button>
              </DialogTrigger>
              <DialogContent data-testid="new-document-dialog">
                <DialogHeader>
                  <DialogTitle className="font-heading text-2xl">Create New Document</DialogTitle>
                </DialogHeader>
                <form onSubmit={handleCreateDocument} className="space-y-4 mt-4">
                  <div>
                    <Label htmlFor="doc-title">Document Title</Label>
                    <Input
                      id="doc-title"
                      data-testid="new-doc-title-input"
                      value={newDocTitle}
                      onChange={(e) => setNewDocTitle(e.target.value)}
                      placeholder="My New Book"
                      required
                      className="rounded-sm"
                    />
                  </div>
                  <div>
                    <Label htmlFor="doc-format">Format</Label>
                    <Select value={newDocFormat} onValueChange={setNewDocFormat}>
                      <SelectTrigger data-testid="format-select" className="rounded-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="6x9">6×9 (Standard Book)</SelectItem>
                        <SelectItem value="5x8">5×8 (Digest)</SelectItem>
                        <SelectItem value="8.5x11">8.5×11 (Magazine)</SelectItem>
                        <SelectItem value="epub">ePub (Digital)</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <Button data-testid="create-doc-submit-btn" type="submit" className="w-full rounded-sm">
                    Create Document
                  </Button>
                </form>
              </DialogContent>
            </Dialog>
          </div>
        </div>

        {/* Documents Grid */}
        {loading ? (
          <div className="flex items-center justify-center py-20">
            <div className="text-lg font-body text-muted-foreground">Loading documents...</div>
          </div>
        ) : filteredDocuments.length === 0 ? (
          <div className="text-center py-20">
            <FileText className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
            <h3 className="text-xl font-heading font-semibold mb-2">
              {searchQuery ? 'No documents found' : 'No documents yet'}
            </h3>
            <p className="text-muted-foreground font-body mb-6">
              {searchQuery ? 'Try a different search term' : 'Create your first document to get started'}
            </p>
            {!searchQuery && (
              <Button data-testid="create-first-doc-btn" onClick={() => setShowNewDialog(true)} className="rounded-sm">
                <Plus className="h-4 w-4 mr-2" />
                Create Document
              </Button>
            )}
          </div>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredDocuments.map((doc, idx) => (
              <motion.div
                key={doc.id}
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.3, delay: idx * 0.05 }}
              >
                <Card
                  data-testid={`document-card-${doc.id}`}
                  className="p-6 hover:shadow-lg transition-all duration-300 cursor-pointer border bg-card/50 backdrop-blur-sm h-full flex flex-col hover:scale-[1.02] relative group"
                  onClick={() => navigate(`/editor/${doc.id}`)}
                >
                  <Button
                    data-testid={`delete-document-btn-${doc.id}`}
                    variant="ghost"
                    size="sm"
                    className="absolute top-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity rounded-sm h-8 w-8 p-0 hover:bg-destructive/10 hover:text-destructive"
                    onClick={(e) => openDeleteDialog(doc, e)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                  <div className="flex items-start justify-between mb-4">
                    <CoverThumbnail docId={doc.id} hasCover={!!doc.cover_image_ext} />
                    <span className="text-xs font-mono text-muted-foreground px-2 py-1 bg-secondary rounded">
                      {doc.format}
                    </span>
                  </div>
                  <h3 className="text-lg font-heading font-semibold mb-2 line-clamp-2">{doc.title}</h3>
                  <p className="text-sm text-muted-foreground font-body line-clamp-3 mb-4 flex-1">
                    {doc.metadata?.description
                      || (doc.content ? doc.content.replace(/<[^>]+>/g, ' ').replace(/\s+/g, ' ').trim().slice(0, 200)
                                        : 'No content yet')}
                  </p>
                  <div className="flex items-center justify-between text-xs text-muted-foreground pt-4 border-t">
                    <div className="flex items-center gap-1">
                      <Calendar className="h-3 w-3" />
                      <span>{formatDate(doc.updated_at)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span>{doc.version_count} versions</span>
                      <span>{doc.comment_count} comments</span>
                    </div>
                  </div>
                  <PipelineBadges status={doc.pipeline_status} docId={doc.id} />
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="font-heading">Delete Document</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete "{documentToDelete?.title}"? This action cannot be undone.
              All versions and comments will be permanently deleted.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel data-testid="delete-cancel-btn" className="rounded-sm">Cancel</AlertDialogCancel>
            <AlertDialogAction
              data-testid="delete-confirm-btn"
              onClick={handleDeleteDocument}
              className="rounded-sm bg-destructive text-destructive-foreground hover:bg-destructive/90"
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
