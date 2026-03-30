import { useState } from 'react'
import type { FormEvent } from 'react'
import { queryVideo } from '@/lib/api.ts'
import type { Segment } from '@/lib/types.ts'
import { Button } from '@/components/ui/button.tsx'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card.tsx'
import { Input } from '@/components/ui/input.tsx'
import { Label } from '@/components/ui/label.tsx'
import { ArrowLeft, Search } from 'lucide-react'

type QueryPageProps = {
  videoId: string
  onQueryComplete: (segments: Segment[]) => void
  onBack: () => void
}

export function QueryPage({ videoId, onQueryComplete, onBack }: QueryPageProps) {
  const [query, setQuery] = useState('')
  const [isSearching, setIsSearching] = useState(false)

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!query.trim()) return

    setIsSearching(true)

    try {
      const { segments } = await queryVideo(videoId, query.trim())
      onQueryComplete(segments)
    } finally {
      setIsSearching(false)
    }
  }

  const filename = videoId.split('/').pop() ?? videoId

  return (
    <div className="max-w-lg mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="sm" onClick={onBack} className="-ml-2">
          <ArrowLeft className="h-4 w-4 mr-1" />
          Back
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Ask about this lecture</CardTitle>
          <CardDescription className="truncate">
            {filename}
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="lecture-query">Your question</Label>
              <Input
                id="lecture-query"
                type="text"
                placeholder="What did the speaker say about neural networks?"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                autoFocus
              />
            </div>
            <Button type="submit" className="w-full" disabled={!query.trim() || isSearching}>
              {isSearching ? (
                <>Searching…</>
              ) : (
                <>
                  <Search className="h-4 w-4 mr-2" />
                  Find segments
                </>
              )}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
