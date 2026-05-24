import type { NextApiRequest, NextApiResponse } from 'next'
import { spawn } from 'child_process'

export const config = { api: { bodyParser: false } }

export default function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== 'POST') return res.status(405).end()

  res.setHeader('Content-Type', 'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection', 'keep-alive')
  res.flushHeaders()

  const send = (obj: object) => res.write(`data: ${JSON.stringify(obj)}\n\n`)

  const { step } = req.query
  const cwd = process.cwd()

  let cmd: string[]
  if (step && typeof step === 'string') {
    const stepMap: Record<string, string> = {
      '1': 'pipeline/v6/1_collect_youtube.py',
      '2': 'pipeline/v6/2_combine_datasets.py',
      '3': 'pipeline/v6/3_embed.py',
      '4': 'pipeline/v6/4_cluster.py',
      '5': 'pipeline/v6/5_name.py',
      '6': 'pipeline/v6/6_evaluate.py',
    }
    const script = stepMap[step]
    if (!script) {
      send({ type: 'error', text: `Unknown step: ${step}` })
      res.end()
      return
    }
    cmd = ['python3', script]
  } else {
    cmd = ['bash', 'pipeline/v6/run.sh']
  }

  send({ type: 'start', cmd: cmd.join(' ') })

  const proc = spawn(cmd[0], cmd.slice(1), { cwd })

  proc.stdout.on('data', chunk => send({ type: 'log', text: chunk.toString() }))
  proc.stderr.on('data', chunk => send({ type: 'log', text: chunk.toString() }))

  proc.on('close', code => {
    send({ type: 'done', code, success: code === 0 })
    res.end()
  })

  proc.on('error', err => {
    send({ type: 'error', text: err.message })
    res.end()
  })

  req.on('close', () => proc.kill())
}
