import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Save, Download, History, MessageSquare, Settings, Eye, Globe, Loader2 } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Card } from '../components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Separator } from '../components/ui/separator';
import { Textarea } from '../components/ui/textarea';
import axios from 'axios';
import { toast } from 'sonner';
import { useNavigate, useParams } from 'react-router-dom';
import ReactQuill from 'react-quill-new';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;
const LOGO_URL = 'https://customer-assets.emergentagent.com/job_book-press/artifacts/gwdawx4q_Divine%20Leadership%20Press%20Emblem%281%29.png';

const getAuthHeaders = () => ({
  headers: { Authorization: `Bearer ${localStorage.getItem('token')}` }
});

export default function EditorPage({ user }) {
  const navigate = useNavigate();
  const { documentId } = useParams();
  const [document, setDocument] = useState(null);
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

  useEffect(() => {
    fetchDocument();
    fetchVersions();
    fetchComments();
  }, [documentId]);

  const fetchDocument = async () => {
    try {
      const response = await axios.get(`${API}/documents/${documentId}`, getAuthHeaders());
      setDocument(response.data);
      setContent(response.data.content);
      setTitle(response.data.title);
      setMetadata(response.data.metadata || {});
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

  const handleExport = async (format) => {
    try {
      await axios.post(
        `${API}/documents/${documentId}/export?format=${format}`,
        {},
        getAuthHeaders()
      );
      toast.success(`Exported to ${format}`);
    } catch (error) {
      toast.error('Export failed');
    }
  };

  const handlePublish = async (platform) => {
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
      [{ 'header': [1, 2, 3, false] }],
      ['bold', 'italic', 'underline', 'strike'],
      [{ 'list': 'ordered'}, { 'list': 'bullet' }],
      [{ 'align': [] }],
      ['link'],
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
            <Input
              data-testid="document-title-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="font-heading text-lg font-semibold border-0 focus-visible:ring-0 px-2"
            />
          </div>
          <div className="flex items-center gap-2">
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
          <div className="space-y-6">
            {showPreview ? (
              <Card data-testid="preview-panel" className="p-8 bg-card/50 backdrop-blur-sm">
                <div className="prose prose-lg max-w-none font-editor" dangerouslySetInnerHTML={{ __html: content }} />
              </Card>
            ) : (
              <Card data-testid="editor-panel" className="p-6 bg-card/50 backdrop-blur-sm">
                <ReactQuill
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

                <TabsContent value="metadata" className="space-y-4 mt-4">
                  <div>
                    <Label>Format</Label>
                    <Select value={document?.format} disabled>
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

            {/* Export & Publish */}
            <Card data-testid="export-panel" className="p-4 bg-card/50 backdrop-blur-sm">
              <h3 className="text-sm font-heading font-semibold mb-3">Export & Publish</h3>
              <div className="space-y-2">
                <Button
                  data-testid="export-pdf-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handleExport('pdf')}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export PDF
                </Button>
                <Button
                  data-testid="export-epub-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handleExport('epub')}
                >
                  <Download className="h-4 w-4 mr-2" />
                  Export ePub
                </Button>
                <Separator className="my-3" />
                <Button
                  data-testid="publish-kdp-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handlePublish('kdp')}
                >
                  <Globe className="h-4 w-4 mr-2" />
                  Publish to KDP
                </Button>
                <Button
                  data-testid="publish-lulu-btn"
                  variant="outline"
                  size="sm"
                  className="w-full justify-start rounded-sm"
                  onClick={() => handlePublish('lulu')}
                >
                  <Globe className="h-4 w-4 mr-2" />
                  Publish to LULU
                </Button>
              </div>
            </Card>
          </div>
        </div>
      </div>
    </div>
  );
}
