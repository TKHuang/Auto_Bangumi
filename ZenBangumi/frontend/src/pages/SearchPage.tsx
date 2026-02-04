import { useState } from 'react'
import { Search, Loader2, AlertCircle } from 'lucide-react'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'

export default function SearchPage() {
  const [keyword, setKeyword] = useState('')
  const [provider, setProvider] = useState('mikan')
  const [isLoading, setIsLoading] = useState(false)
  const [message, setMessage] = useState<{ type: 'error' | 'info'; text: string } | null>(null)

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!keyword.trim()) return

    setIsLoading(true)
    setMessage(null)

    try {
      const res = await fetch(`/api/v1/search/${encodeURIComponent(keyword)}?provider=${provider}`)

      if (res.status === 501) {
        setMessage({
          type: 'info',
          text: 'Search functionality will be available after backend implementation (Task 20)',
        })
      } else if (!res.ok) {
        setMessage({
          type: 'error',
          text: `Search failed: ${res.statusText}`,
        })
      } else {
        setMessage({
          type: 'info',
          text: 'Search completed (Mock)',
        })
      }
    } catch {
      setMessage({
        type: 'error',
        text: 'An error occurred while searching',
      })
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="container max-w-4xl py-12 space-y-8 animate-in fade-in duration-500">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold tracking-tight">Search Anime</h1>
        <p className="text-muted-foreground">
          Find and subscribe to your favorite anime from various providers
        </p>
      </div>

      <Card className="w-full">
        <CardHeader>
          <CardTitle>Search Configuration</CardTitle>
          <CardDescription>Enter keywords and select a provider to search</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex flex-col md:flex-row gap-4">
            <div className="flex-1">
              <Input
                placeholder="Search by title..."
                value={keyword}
                onChange={(e) => setKeyword(e.target.value)}
                className="w-full"
                autoFocus
              />
            </div>
            <Select value={provider} onValueChange={setProvider}>
              <SelectTrigger className="w-full md:w-[180px]">
                <SelectValue placeholder="Select provider" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="mikan">Mikan Project</SelectItem>
                <SelectItem value="dmhy">Dmhy</SelectItem>
                <SelectItem value="bangumi_moe">Bangumi.moe</SelectItem>
              </SelectContent>
            </Select>
            <Button type="submit" disabled={isLoading || !keyword.trim()}>
              {isLoading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Searching
                </>
              ) : (
                <>
                  <Search className="mr-2 h-4 w-4" />
                  Search
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>

      {message && (
        <Card
          className={`border-l-4 ${
            message.type === 'error' ? 'border-l-destructive' : 'border-l-blue-500'
          }`}
        >
          <CardContent className="flex items-center p-6 gap-4">
            <AlertCircle
              className={`h-6 w-6 ${
                message.type === 'error' ? 'text-destructive' : 'text-blue-500'
              }`}
            />
            <div>
              <h3 className="font-semibold">
                {message.type === 'error' ? 'Error' : 'Not Implemented'}
              </h3>
              <p className="text-sm text-muted-foreground">{message.text}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {!message && !isLoading && (
        <div className="text-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
          Search results will appear here
        </div>
      )}
    </div>
  )
}
