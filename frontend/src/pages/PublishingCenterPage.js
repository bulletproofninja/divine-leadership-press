import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import axios from 'axios';
import { toast } from 'sonner';
import { ArrowLeft, BookOpen, CheckCircle2, Circle, Globe2, Loader2, PackageCheck, Store } from 'lucide-react';
import { Button } from '../components/ui/button';
import { Card } from '../components/ui/card';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../components/ui/tabs';

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
const LOGO_URL = '/brand/divine-leadership-press-emblem.png';
const auth = () => ({ headers: { Authorization: `Bearer ${localStorage.getItem('token')}` } });

const emptyAddress = {
  quantity: 1, recipient_name: '', address_line_1: '', address_line_2: '', city: '',
  state: '', postal_code: '', country_code: 'US', shipping_level: 'mail',
};

function ReadinessList({ readiness, retail = false }) {
  if (!readiness) return <p className="text-sm text-muted-foreground">Select a manuscript to inspect its files.</p>;
  const retailOnly = new Set(['description', 'isbn', 'publisher']);
  return (
    <div className="space-y-2">
      {readiness.checks.filter((item) => retail || !retailOnly.has(item.key)).map((item) => (
        <div key={item.key} className="flex items-center gap-2 text-sm">
          {item.complete
            ? <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            : <Circle className="h-4 w-4 text-amber-600" />}
          <span className={item.complete ? 'text-foreground' : 'text-muted-foreground'}>{item.label}</span>
        </div>
      ))}
    </div>
  );
}

export default function PublishingCenterPage() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [documents, setDocuments] = useState([]);
  const [documentId, setDocumentId] = useState(params.get('document') || '');
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [order, setOrder] = useState(emptyAddress);

  const selected = useMemo(() => documents.find((d) => d.id === documentId), [documents, documentId]);

  useEffect(() => {
    axios.get(`${API}/documents`, auth()).then((r) => {
      setDocuments(r.data);
      if (!documentId && r.data.length) setDocumentId(r.data[0].id);
    }).catch(() => toast.error('Could not load manuscripts')).finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!documentId) return;
    setReadiness(null);
    axios.get(`${API}/publishing/readiness/${documentId}`, auth())
      .then((r) => setReadiness(r.data))
      .catch(() => toast.error('Could not inspect publishing readiness'));
  }, [documentId]);

  const update = (key, value) => setOrder((current) => ({ ...current, [key]: value }));

  const createDraft = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await axios.post(`${API}/publishing/orders`, {
        ...order, quantity: Number(order.quantity), document_id: documentId, provider: 'lulu',
      }, auth());
      toast.success('Print order draft created');
      setOrder(emptyAddress);
    } catch (error) {
      const detail = error.response?.data?.detail;
      const missing = detail?.missing?.join(', ');
      toast.error(missing ? `Complete these items first: ${missing}` : detail?.message || detail || 'Could not create order draft');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card/95">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between max-w-6xl">
          <div className="flex items-center gap-3">
            <img src={LOGO_URL} alt="Divine Leadership Press" className="h-10 w-10" />
            <div>
              <h1 className="text-xl font-heading font-bold">Print and Distribution Center</h1>
              <p className="text-xs text-muted-foreground">From approved files to readers worldwide</p>
            </div>
          </div>
          <Button variant="ghost" onClick={() => navigate('/dashboard')} className="rounded-sm">
            <ArrowLeft className="h-4 w-4 mr-2" /> Dashboard
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-8 max-w-6xl">
        <Card className="p-5 mb-6 border-l-4 border-l-primary">
          <div className="grid gap-4 md:grid-cols-[1fr_320px] md:items-end">
            <div>
              <h2 className="font-heading text-2xl font-semibold">Choose a finished manuscript</h2>
              <p className="text-sm text-muted-foreground mt-1">Direct fulfillment and retail distribution use the same approved source files.</p>
            </div>
            <Select value={documentId} onValueChange={setDocumentId} disabled={loading || !documents.length}>
              <SelectTrigger data-testid="publishing-document-select" className="rounded-sm"><SelectValue placeholder="Select manuscript" /></SelectTrigger>
              <SelectContent>{documents.map((doc) => <SelectItem key={doc.id} value={doc.id}>{doc.title}</SelectItem>)}</SelectContent>
            </Select>
          </div>
        </Card>

        <Tabs defaultValue="fulfillment">
          <TabsList className="grid w-full max-w-xl grid-cols-2 rounded-sm">
            <TabsTrigger value="fulfillment"><PackageCheck className="h-4 w-4 mr-2" /> Print and Ship</TabsTrigger>
            <TabsTrigger value="distribution"><Store className="h-4 w-4 mr-2" /> Retail Distribution</TabsTrigger>
          </TabsList>

          <TabsContent value="fulfillment" className="mt-5">
            <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
              <Card className="p-6">
                <div className="flex items-start gap-3 mb-5">
                  <PackageCheck className="h-6 w-6 text-primary" />
                  <div><h2 className="font-heading text-xl font-semibold">Lulu Direct</h2><p className="text-sm text-muted-foreground">Single-copy and bulk customer fulfillment</p></div>
                </div>
                <ReadinessList readiness={readiness} />
                <div className="mt-5 p-3 bg-secondary/60 text-xs text-muted-foreground rounded-sm">
                  Orders remain drafts until live Lulu credentials, a verified quote, payment, and final approval are complete.
                </div>
              </Card>

              <Card className="p-6">
                <h2 className="font-heading text-xl font-semibold mb-1">Create print order draft</h2>
                <p className="text-sm text-muted-foreground mb-5">Set the quantity and delivery destination for {selected?.title || 'this book'}.</p>
                <form onSubmit={createDraft} className="grid gap-4 sm:grid-cols-2">
                  <div><Label>Quantity</Label><Input type="number" min="1" max="5000" value={order.quantity} onChange={(e) => update('quantity', e.target.value)} required /></div>
                  <div><Label>Recipient</Label><Input value={order.recipient_name} onChange={(e) => update('recipient_name', e.target.value)} required /></div>
                  <div className="sm:col-span-2"><Label>Street address</Label><Input value={order.address_line_1} onChange={(e) => update('address_line_1', e.target.value)} required /></div>
                  <div><Label>City</Label><Input value={order.city} onChange={(e) => update('city', e.target.value)} required /></div>
                  <div><Label>State or province</Label><Input value={order.state} onChange={(e) => update('state', e.target.value)} required /></div>
                  <div><Label>Postal code</Label><Input value={order.postal_code} onChange={(e) => update('postal_code', e.target.value)} required /></div>
                  <div><Label>Country code</Label><Input maxLength={2} value={order.country_code} onChange={(e) => update('country_code', e.target.value.toUpperCase())} required /></div>
                  <div className="sm:col-span-2"><Label>Shipping level</Label><Select value={order.shipping_level} onValueChange={(v) => update('shipping_level', v)}><SelectTrigger><SelectValue /></SelectTrigger><SelectContent><SelectItem value="mail">Mail</SelectItem><SelectItem value="priority">Priority</SelectItem><SelectItem value="express">Express</SelectItem></SelectContent></Select></div>
                  <Button data-testid="create-print-order" type="submit" disabled={saving || !documentId} className="sm:col-span-2 rounded-sm">
                    {saving ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <BookOpen className="h-4 w-4 mr-2" />} Create Draft
                  </Button>
                </form>
              </Card>
            </div>
          </TabsContent>

          <TabsContent value="distribution" className="mt-5">
            <div className="grid gap-6 lg:grid-cols-[0.85fr_1.15fr]">
              <Card className="p-6">
                <div className="flex items-start gap-3 mb-5"><Globe2 className="h-6 w-6 text-primary" /><div><h2 className="font-heading text-xl font-semibold">IngramSpark Package</h2><p className="text-sm text-muted-foreground">Bookstores, libraries, and online retailers</p></div></div>
                <ReadinessList readiness={readiness} retail />
              </Card>
              <Card className="p-6">
                <h2 className="font-heading text-xl font-semibold">Mainstream distribution path</h2>
                <ol className="mt-5 space-y-4">
                  {['Approve the final interior and full-cover PDFs', 'Complete ISBN, imprint, description, categories, and keywords', 'Choose list price, wholesale discount, territories, and return policy', 'Upload the validated title package to the publisher account', 'Review the digital proof before enabling distribution'].map((label, index) => (
                    <li key={label} className="flex gap-3"><span className="h-7 w-7 flex-none rounded-full bg-primary text-primary-foreground flex items-center justify-center text-xs font-semibold">{index + 1}</span><span className="text-sm pt-1">{label}</span></li>
                  ))}
                </ol>
                <div className="mt-6 p-4 border rounded-sm bg-card">
                  <p className="text-sm font-medium">Distribution readiness</p>
                  <p className="text-xs text-muted-foreground mt-1">{readiness?.retail_distribution_ready ? 'This title has the core files and metadata needed for package review.' : 'Complete every readiness item before final submission.'}</p>
                  <Button className="mt-4 rounded-sm" variant="outline" disabled={!documentId} onClick={() => navigate(`/editor/${documentId}`)}>Open manuscript setup</Button>
                </div>
              </Card>
            </div>
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
}

