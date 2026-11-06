import { useState } from 'react'
import { Card, PageTitle } from '../components/ui'

type Tab = 'order' | 'trends' | 'risks'

// Разделы аналитики рынка. Данные — внешние, загрузятся позже; пока разделы пустые.
const SECTIONS: Record<Tab, { label: string; items: [string, string][] }> = {
  order: {
    label: 'Умный заказ',
    items: [
      ['Дефицит и скорость продаж', 'Сколько штук продаётся в день и на сколько дней хватит остатка.'],
      ['Упущенная выручка', 'Сколько денег теряется, когда ходовой товар закончился.'],
      ['ABC / XYZ-анализ', 'Какие товары заказывать всегда, а какие — мёртвый груз.'],
    ],
  },
  trends: {
    label: 'Что закупать нового',
    items: [
      ['Поисковые магниты', 'Что ищут на Kaspi, но не могут найти.'],
      ['Тренды TikTok / Instagram', 'Товары и бренды, которые набирают популярность в соцсетях.'],
      ['Новички-взлёты', 'Новые карточки, которые уже много продают.'],
    ],
  },
  risks: {
    label: 'Риски закупа',
    items: [
      ['Монополизация карточек', 'Сколько продавцов на товаре и есть ли крупные игроки.'],
      ['Индекс демпинга', 'Как падала цена на товар за последние 3 месяца.'],
    ],
  },
}

function Empty({ title, text }: { title: string; text: string }) {
  return (
    <Card>
      <p className="text-base font-bold">{title}</p>
      <p className="mt-1 text-sm text-ink-2">{text}</p>
      <div className="mt-4 grid place-items-center rounded-xl border border-dashed border-line py-10 text-sm text-muted">
        Данные появятся после загрузки
      </div>
    </Card>
  )
}

export function MarketPage() {
  const [tab, setTab] = useState<Tab>('order')
  const section = SECTIONS[tab]

  return (
    <>
      <PageTitle subtitle="Что и сколько закупать, что набирает спрос и где опасно заходить с товаром">Аналитика рынка</PageTitle>
      <div className="flex flex-wrap gap-1 rounded-2xl border border-line bg-surface p-1.5">
        {(Object.keys(SECTIONS) as Tab[]).map((id) => (
          <button
            key={id}
            type="button"
            onClick={() => setTab(id)}
            className={`flex-1 whitespace-nowrap rounded-xl px-4 py-2.5 text-sm font-bold transition ${
              tab === id ? 'cta-gradient text-white' : 'text-ink-2 hover:bg-hover'
            }`}
          >
            {SECTIONS[id].label}
          </button>
        ))}
      </div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {section.items.map(([title, text]) => (
          <Empty key={title} title={title} text={text} />
        ))}
      </div>
    </>
  )
}
