import type { NextApiRequest, NextApiResponse } from 'next'
import { classifyText, loadTaxonomy } from '../../../lib/v6classify'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const taxonomy = loadTaxonomy()
  if (!taxonomy) return res.status(503).json({ error: 'V6 taxonomy not ready' })

  const { rows } = req.body as { rows?: Array<{ id?: string; text: string }> }
  if (!Array.isArray(rows) || rows.length === 0) {
    return res.status(400).json({ error: 'rows array required' })
  }
  if (rows.length > 200) {
    return res.status(400).json({ error: 'Maximum 200 rows per batch' })
  }

  const results = await Promise.all(
    rows.map(async (row, i) => {
      if (!row.text?.trim()) {
        return { id: row.id ?? String(i), error: 'empty text', classification: null }
      }
      try {
        const classification = await classifyText(row.text)
        return { id: row.id ?? String(i), classification }
      } catch (err) {
        return { id: row.id ?? String(i), error: String(err), classification: null }
      }
    })
  )

  res.status(200).json({
    total: rows.length,
    successful: results.filter(r => r.classification).length,
    failed: results.filter(r => !r.classification).length,
    results,
  })
}
