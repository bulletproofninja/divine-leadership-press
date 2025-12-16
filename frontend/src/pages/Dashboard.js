import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Plus, FileText, Upload, LogOut, Search, Calendar, File } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Card } from '../components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '../components/ui/dialog';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate } from 'react-router-dom';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_book-press/artifacts/gwdawx4q_Divine%20Leadership%20Press%20Emblem%281%29.png';

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

export default function Dashboard({ user, onLogout }) {
  const navigate = useNavigate();
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [showNewDialog, setShowNewDialog] = useState(false);
  const [newDocTitle, setNewDocTitle] = useState('');
  const [newDocFormat, setNewDocFormat] = useState('6x9');
  const [uploading, setUploading] = useState(false);

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
      toast.error(error.response?.data?.detail || 'Failed to upload document');
    } finally {
      setUploading(false);
    }
  };

  const filteredDocuments = documents.filter((doc) =>
    doc.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

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
              accept=".docx,.txt"
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
                  className="p-6 hover:shadow-lg transition-all duration-300 cursor-pointer border bg-card/50 backdrop-blur-sm h-full flex flex-col hover:scale-[1.02]"
                  onClick={() => navigate(`/editor/${doc.id}`)}
                >
                  <div className="flex items-start justify-between mb-4">
                    <div className="p-2 rounded-md bg-primary/10">
                      <File className="h-6 w-6 text-primary" />
                    </div>
                    <span className="text-xs font-mono text-muted-foreground px-2 py-1 bg-secondary rounded">
                      {doc.format}
                    </span>
                  </div>
                  <h3 className="text-lg font-heading font-semibold mb-2 line-clamp-2">{doc.title}</h3>
                  <p className="text-sm text-muted-foreground font-body line-clamp-3 mb-4 flex-1">
                    {doc.content || 'No content yet'}
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
                </Card>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
