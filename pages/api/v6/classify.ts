import type { NextApiRequest, NextApiResponse } from 'next'
import { classifyText, loadTaxonomy } from '../../../lib/v6classify'

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const taxonomy = loadTaxonomy()
  if (!taxonomy) {
    return res.status(503).json({ error: 'V6 Taxonomy not ready. Run pipeline/v6/run.sh first.' })
  }

  const result = await classifyText(text)
  if (!result) {
    return res.status(503).json({ error: 'Classification failed' })
  }

  res.status(200).json(result)
}
