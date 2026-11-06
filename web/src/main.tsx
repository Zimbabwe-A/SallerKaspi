import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import { Layout } from './components/Layout'
import './index.css'
import { BotPage } from './pages/BotPage'
import { CostsPage } from './pages/CostsPage'
import { WaybillsPage } from './pages/WaybillsPage'
import { MarketPage } from './pages/MarketPage'
import { OverviewPage } from './pages/OverviewPage'
import { ProductPage } from './pages/ProductPage'
import { ProductsPage } from './pages/ProductsPage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="products/:id" element={<ProductPage />} />
            <Route path="market" element={<MarketPage />} />
            <Route path="bot" element={<BotPage />} />
            <Route path="costs" element={<CostsPage />} />
            <Route path="waybills" element={<WaybillsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  </StrictMode>,
)
