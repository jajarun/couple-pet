import { ReactElement } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'

/** 返回值多带一个 queryClient：需要直接读/喂缓存的用例（如模拟轮询落地）用得上。 */
export function renderWithProviders(
  ui: ReactElement,
  route = '/',
): ReturnType<typeof render> & { queryClient: QueryClient } {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  const utils = render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter
        initialEntries={[route]}
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        {ui}
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return { ...utils, queryClient }
}
