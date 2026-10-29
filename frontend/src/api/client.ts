/**
 * Cliente de API — todas as chamadas ao backend.
 *
 * SEGURANÇA:
 * - Nenhuma chave ou credencial no frontend.
 * - Toda chamada ao LLM passa pelo backend.
 * - O texto da mensagem nunca é persistido (sem localStorage, sem console.log).
 */

import type { GuardiaoRequest, GuardiaoResponse, BBDecisionRequest, BBDecisionResponse } from '../types/api'

const API_BASE = import.meta.env.VITE_API_URL ?? ''

async function post<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let message = `Erro ${response.status}`
    try {
      const data = await response.json()
      // Expõe apenas a mensagem de erro do backend, nunca detalhes internos
      message = data?.detail?.error ?? data?.detail ?? message
    } catch {
      // ignora falha de parse
    }
    throw new Error(message)
  }

  return response.json() as Promise<T>
}

export async function analyzeMessage(req: GuardiaoRequest): Promise<GuardiaoResponse> {
  return post<GuardiaoResponse>('/api/guardiao/analyze', req)
}

export async function simulate(req: BBDecisionRequest): Promise<BBDecisionResponse> {
  return post<BBDecisionResponse>('/api/bbdecision/simulate', req)
}
