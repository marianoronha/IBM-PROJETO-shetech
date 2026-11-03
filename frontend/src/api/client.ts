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

/**
 * Envia um arquivo (imagem ou áudio) para análise multimodal.
 *
 * Usa multipart/form-data para enviar o arquivo bruto ao endpoint /analyze-file.
 * O backend extrai o conteúdo (via GPT-4o Vision ou Whisper) e retorna
 * GuardiaoResponse idêntico ao da análise de texto.
 *
 * SEGURANÇA: o arquivo nunca é armazenado no frontend nem logado.
 */
export async function analyzeFile(params: {
  file: File
  userId?: string
  languageProfile?: 'standard' | 'low'
  monitoringConsent?: boolean
  contextText?: string
}): Promise<GuardiaoResponse> {
  const form = new FormData()
  form.append('file', params.file)
  form.append('user_id', params.userId ?? '')
  form.append('language_profile', params.languageProfile ?? 'standard')
  form.append('monitoring_consent', String(params.monitoringConsent ?? true))
  form.append('context_text', params.contextText ?? '')

  const response = await fetch(`${API_BASE}/api/guardiao/analyze-file`, {
    method: 'POST',
    // Não definir Content-Type — o browser define automaticamente com boundary correto
    body: form,
  })

  if (!response.ok) {
    let message = `Erro ${response.status}`
    try {
      const data = await response.json()
      message = data?.detail?.error ?? data?.detail ?? message
    } catch {
      // ignora falha de parse
    }
    throw new Error(message)
  }

  return response.json() as Promise<GuardiaoResponse>
}

export async function simulate(req: BBDecisionRequest): Promise<BBDecisionResponse> {
  return post<BBDecisionResponse>('/api/bbdecision/simulate', req)
}
