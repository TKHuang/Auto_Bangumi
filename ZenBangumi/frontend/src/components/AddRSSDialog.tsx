import React, { useState, useEffect } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

export interface AddRSSPayload {
  url: string;
  name: string;
  aggregate: boolean;
  parser: string;
  enabled: boolean;
}

interface AddRSSDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSubmit: (data: AddRSSPayload) => Promise<void>;
}

export const AddRSSDialog: React.FC<AddRSSDialogProps> = ({
  open,
  onOpenChange,
  onSubmit,
}) => {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [aggregate, setAggregate] = useState(false);
  const [parser, setParser] = useState('mikan');
  const [enabled, setEnabled] = useState(true);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (open) {
      setUrl('');
      setName('');
      setAggregate(false);
      setParser('mikan');
      setEnabled(true);
      setLoading(false);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setLoading(true);
    try {
      await onSubmit({
        url,
        name,
        aggregate,
        parser,
        enabled,
      });
      onOpenChange(false);
    } catch (error) {
      // Error handling should be done by the parent or global handler
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Add RSS Feed</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="grid gap-4 py-4">
          <div className="grid gap-2">
            <label htmlFor="url" className="text-sm font-medium">
              RSS URL <span className="text-red-500">*</span>
            </label>
            <Input
              id="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://mikanani.me/RSS/..."
              required
            />
          </div>
          <div className="grid gap-2">
            <label htmlFor="name" className="text-sm font-medium">
              Name
            </label>
            <Input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Optional feed name"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <label htmlFor="parser" className="text-sm font-medium">
                Parser
              </label>
              <Select value={parser} onValueChange={setParser}>
                <SelectTrigger id="parser">
                  <SelectValue placeholder="Select parser" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mikan">Mikan Project</SelectItem>
                  <SelectItem value="lilith">Lilith</SelectItem>
                  <SelectItem value="dmhy">Dmhy</SelectItem>
                  <SelectItem value="nyaa">Nyaa</SelectItem>
                  <SelectItem value="bangumi_moe">Bangumi.moe</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-2">
               <label className="text-sm font-medium">Options</label>
               <div className="flex items-center justify-between border p-2 rounded-md h-[40px]">
                 <span className="text-sm text-muted-foreground">Aggregate</span>
                 <Switch
                    checked={aggregate}
                    onCheckedChange={setAggregate}
                 />
               </div>
               <div className="flex items-center justify-between border p-2 rounded-md h-[40px]">
                 <span className="text-sm text-muted-foreground">Enabled</span>
                 <Switch
                    checked={enabled}
                    onCheckedChange={setEnabled}
                 />
               </div>
            </div>
          </div>
          <DialogFooter className="mt-4">
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading || !url}>
              {loading ? 'Adding...' : 'Add RSS'}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};
