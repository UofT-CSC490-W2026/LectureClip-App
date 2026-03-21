import { useState } from 'react'
import type { FormEvent } from 'react'
import { queryVideo } from '@/lib/api.ts'
import type { Segment } from '@/lib/types.ts'

type QueryPageProps = {
  videoId: string
  onQueryComplete: (segments: Segment[]) => void
}

export function QueryPage({ videoId, onQueryComplete }: QueryPageProps) {
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

  return (
    <section className="page-content">
      <h2>Ask about the lecture</h2>
      <p>Video ready: <strong>{videoId}</strong></p>

      <form className="page-content" onSubmit={handleSubmit}>
        <div className="field-group">
          <label htmlFor="lecture-query">Your query</label>
          <input
            id="lecture-query"
            type="text"
            placeholder="What did the speaker say about neural networks?"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <button className="primary-button" type="submit" disabled={!query.trim() || isSearching}>
          {isSearching ? 'Searching...' : 'Find segments'}
        </button>
      </form>
    </section>
  )
}
