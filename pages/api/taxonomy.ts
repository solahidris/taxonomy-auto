import type { NextApiRequest, NextApiResponse } from 'next'
import fs from 'fs'
import path from 'path'

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  const fp = path.join(process.cwd(), 'data', 'taxonomy.json')

  if (!fs.existsSync(fp)) {
    return res.status(503).json({
      error: 'Taxonomy not generated yet. Run: bash pipeline/run.sh',
    })
  }

  const data = JSON.parse(fs.readFileSync(fp, 'utf-8'))
  res.setHeader('Cache-Control', 's-maxage=3600, stale-while-revalidate')
  res.status(200).json(data)
}
