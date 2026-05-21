import type { NextApiRequest, NextApiResponse } from 'next'
import OpenAI from 'openai'
import fs from 'fs'
import path from 'path'

const openai = new OpenAI({ apiKey: process.env.OPENAI_API_KEY })

type Centroid = {
  id: string
  name: string
  description: string
  path: string[]
  keywords: string[]
  centroid: number[]
}

let cache: Centroid[] | null = null

function loadCentroids(): Centroid[] | null {
  if (cache) return cache
  const fp = path.join(process.cwd(), 'data', 'centroids.json')
  if (!fs.existsSync(fp)) return null
  cache = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  return cache
}

function cosine(a: number[], b: number[]): number {
  let dot = 0, na = 0, nb = 0
  for (let i = 0; i < a.length; i++) {
    dot += a[i] * b[i]
    na += a[i] * a[i]
    nb += b[i] * b[i]
  }
  const denom = Math.sqrt(na) * Math.sqrt(nb)
  return denom === 0 ? 0 : dot / denom
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  const { text } = req.body as { text?: string }
  if (!text?.trim()) return res.status(400).json({ error: 'text required' })

  const centroids = loadCentroids()
  if (!centroids) {
    return res.status(503).json({
      error: 'Taxonomy not ready. Run: bash pipeline/run.sh',
    })
  }

  const embResp = await openai.embeddings.create({
    model: 'text-embedding-3-small',
    input: text.slice(0, 1000),
  })
  const vec = embResp.data[0].embedding

  const results = centroids
    .map(({ centroid, ...rest }) => ({ ...rest, score: cosine(vec, centroid) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, 5)

  res.status(200).json({ results })
}
