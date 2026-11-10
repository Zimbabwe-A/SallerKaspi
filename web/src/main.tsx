import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router'
import { useMe } from './api/auth'
import { Layout } from './components/Layout'
import './index.css'
import { BotPage } from './pages/BotPage'
import { CostsPage } from './pages/CostsPage'
import { WaybillsPage } from './pages/WaybillsPage'
import { MarketPage } from './pages/MarketPage'
import { OrdersPage } from './pages/OrdersPage'
import { OverviewPage } from './pages/OverviewPage'
import { ProductPage } from './pages/ProductPage'
import { ProductsPage } from './pages/ProductsPage'
import { StockPage } from './pages/StockPage'
import { WelcomePage } from './pages/WelcomePage'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 60_000, refetchOnWindowFocus: false, retry: 1 } },
})

/** Без входа показываем приглашение, после входа — сам сайт. */
function App() {
  const me = useMe()
  if (me.isPending) return null
  if (!me.data) return <WelcomePage />
  return (
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<OverviewPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="products/:id" element={<ProductPage />} />
            <Route path="market" element={<MarketPage />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="stock" element={<StockPage />} />
            <Route path="bot" element={<BotPage />} />
            <Route path="costs" element={<CostsPage />} />
            <Route path="waybills" element={<WaybillsPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
  )
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
    </QueryClientProvider>
  </StrictMode>,
)
