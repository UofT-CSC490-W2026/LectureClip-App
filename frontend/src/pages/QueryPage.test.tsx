import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { queryVideo } from '@/lib/api.ts'
import { QueryPage } from '@/pages/QueryPage.tsx'

vi.mock('@/lib/api.ts', () => ({
  queryVideo: vi.fn(),
}))

describe('QueryPage', () => {
  it('trims the query before searching and returns the new segments', async () => {
    const user = userEvent.setup()
    const onQueryComplete = vi.fn()
    const nextSegments = [{ start: 12, end: 28 }]
    let resolveSearch: ((value: { segments: { start: number; end: number }[] }) => void) | undefined

    vi.mocked(queryVideo).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveSearch = resolve
        }),
    )

    render(<QueryPage videoId="vid_query" onQueryComplete={onQueryComplete} onBack={vi.fn()} />)

    const submitButton = screen.getByRole('button', { name: 'Find segments' })
    expect(submitButton).toBeDisabled()

    await user.type(screen.getByLabelText('Your question'), '  neural networks  ')
    expect(submitButton).toBeEnabled()

    await user.click(submitButton)

    expect(queryVideo).toHaveBeenCalledWith('vid_query', 'neural networks')
    expect(screen.getByRole('button', { name: 'Searching…' })).toBeDisabled()

    resolveSearch?.({ segments: nextSegments })

    await waitFor(() => {
      expect(onQueryComplete).toHaveBeenCalledWith(nextSegments)
    })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Find segments' })).toBeEnabled()
    })
  })
})
