// API client for the Immortal backend

import type { PlatformSkill } from '@/types';

const API_BASE = '';

async function fetchJson(path: string, opts?: RequestInit) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`${res.status}: ${text}`);
  }
  if (res.status === 204) return null;
  return res.json();
}

export async function getSkills() {
  return fetchJson('/api/skills');
}

export async function getPlatformSkills(): Promise<{ skills: PlatformSkill[] }> {
  return fetchJson('/api/skills/platform');
}

export async function importPlatformSkill(colleagueId: string): Promise<{ success: boolean; colleague_id: string; imported: boolean }> {
  return fetchJson(`/api/skills/platform/${encodeURIComponent(colleagueId)}/import`, {
    method: 'POST',
  });
}

export async function importSkill(sourceDir: string, displayName: string) {
  return fetchJson('/api/skills/import', {
    method: 'POST',
    body: JSON.stringify({ source_dir: sourceDir, display_name: displayName }),
  });
}

export async function renameSkill(colleagueId: string, name: string) {
  return fetchJson(`/api/skills/${colleagueId}/rename`, {
    method: 'POST',
    body: JSON.stringify({ name }),
  });
}

export async function deleteSkill(colleagueId: string) {
  return fetchJson(`/api/skills/${colleagueId}`, { method: 'DELETE' });
}

export function getSkillIconUrl(colleagueId: string) {
  return `/api/skills/${colleagueId}/icon`;
}

export async function getSkillIntro(colleagueId: string) {
  return fetchJson(`/api/skills/${colleagueId}/intro`);
}

export async function login(email: string, password: string) {
  return fetchJson('/api/auth/login', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function register(email: string, password: string) {
  return fetchJson('/api/auth/register', {
    method: 'POST',
    body: JSON.stringify({ email, password }),
  });
}

export async function logout() {
  return fetchJson('/api/auth/logout', { method: 'POST' });
}

export async function getCurrentUser() {
  return fetchJson('/api/auth/me');
}

export async function uploadSkill(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  const res = await fetch('/api/skills/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export interface RagUploadResult {
  success: boolean;
  target_skill_id: string;
  files: Array<{
    filename: string;
    doc_id: string;
    source_type: string;
    chunks: number;
  }>;
  total_chunks: number;
}

export interface RagDocument {
  skill_id: string;
  doc_id: string;
  filename: string;
  source_type: string;
  tag: string;
  chunk_count: number;
}

export interface RagDocumentChunk {
  point_id: string;
  chunk_id: string;
  doc_id: string;
  skill_id: string;
  content: string;
  metadata: Record<string, any>;
}

export interface RagDocumentChunksResult {
  skill_id: string;
  doc_id: string;
  chunks: RagDocumentChunk[];
}

export interface RagSkillStats {
  skill_id: string;
  doc_count: number;
  chunk_count: number;
  documents: RagDocument[];
}

export interface RagStats {
  collection: string;
  mode: string;
  total_documents: number;
  total_chunks: number;
  skills: RagSkillStats[];
}

export async function getRagStats(): Promise<RagStats> {
  return fetchJson('/api/admin/rag/stats');
}

export async function deleteRagDocument(skillId: string, docId: string) {
  return fetchJson(`/api/admin/rag/documents/${encodeURIComponent(skillId)}/${encodeURIComponent(docId)}`, {
    method: 'DELETE',
  });
}

export async function getRagDocumentChunks(skillId: string, docId: string): Promise<RagDocumentChunksResult> {
  return fetchJson(`/api/admin/rag/documents/${encodeURIComponent(skillId)}/${encodeURIComponent(docId)}/chunks`);
}

export async function uploadRagDocuments(params: {
  targetSkillId: string;
  files: File[];
  tag?: string;
}): Promise<RagUploadResult> {
  const formData = new FormData();
  formData.append('target_skill_id', params.targetSkillId);
  if (params.tag?.trim()) {
    formData.append('preprocess_config', JSON.stringify({ tag: params.tag.trim() }));
  }
  for (const file of params.files) {
    formData.append('files', file);
  }
  const res = await fetch('/api/admin/rag/upload', {
    method: 'POST',
    body: formData,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => 'Unknown error');
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export async function getAdminUsers() {
  return fetchJson('/api/admin/users');
}

export async function updateAdminUser(userId: number, data: { email?: string; password?: string; avatar?: string }) {
  return fetchJson(`/api/admin/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export async function deleteAdminUser(userId: number) {
  return fetchJson(`/api/admin/users/${userId}`, { method: 'DELETE' });
}

export async function getHistories() {
  return fetchJson('/api/histories');
}

export async function addHistoryMessage(colleagueId: string, role: string, content: string, ts?: number) {
  return fetchJson(`/api/histories/${colleagueId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ role, content, ts: ts || Date.now() / 1000 }),
  });
}

export async function clearHistory(colleagueId: string) {
  return fetchJson(`/api/histories/${colleagueId}/clear`, { method: 'POST' });
}

export async function getSettings() {
  return fetchJson('/api/settings');
}

export async function updateSettings(payload: Record<string, any>) {
  return fetchJson('/api/settings', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function testApi(apiBase: string, apiKey: string, model: string) {
  return fetchJson('/api/settings/test-api', {
    method: 'POST',
    body: JSON.stringify({ api_base: apiBase, api_key: apiKey, model }),
  });
}

export async function testWebSearch(url: string, apiKey: string) {
  return fetchJson('/api/settings/test-web-search', {
    method: 'POST',
    body: JSON.stringify({ url, api_key: apiKey }),
  });
}

export async function getRandomSticker() {
  const res = await fetchJson('/api/stickers/random');
  return res?.url || null;
}

export interface StreamCallbacks {
  onChunk: (content: string) => void;
  onStatus?: (message: string) => void;
  onRagSources?: (sources: import('@/types').RagSourceDocument[]) => void;
  onWebSources?: (sources: import('@/types').WebSourceDocument[]) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

export function streamChat(
  colleagueId: string,
  messages: Array<{ role: string; content: string }>,
  webSearchEnabled: boolean,
  files: File[],
  callbacks: StreamCallbacks
): { abort: () => void } {
  const ctrl = new AbortController();
  let finished = false;

  const finishOnce = () => {
    if (finished) return;
    finished = true;
    callbacks.onDone?.();
  };

  const formData = new FormData();
  formData.append('colleague_id', colleagueId);
  formData.append('messages', JSON.stringify(messages));
  formData.append('web_search_enabled', String(webSearchEnabled));
  for (const file of files) {
    formData.append('files', file);
  }

  fetch(`${API_BASE}/api/chat`, {
    method: 'POST',
    body: formData,
    signal: ctrl.signal,
  }).then(async (res) => {
    if (!res.ok || !res.body) {
      const text = await res.text().catch(() => '请求失败');
      callbacks.onError?.(text);
      return;
    }
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const payload = trimmed.slice(6);
          if (payload === '[DONE]') continue;
          try {
            const data = JSON.parse(payload);
            if (data.type === 'chunk') callbacks.onChunk(data.content);
            else if (data.type === 'status') callbacks.onStatus?.(data.message);
            else if (data.type === 'rag_sources') callbacks.onRagSources?.(data.sources || []);
            else if (data.type === 'web_sources') callbacks.onWebSources?.(data.sources || []);
            else if (data.type === 'done') finishOnce();
            else if (data.type === 'error') callbacks.onError?.(data.message);
          } catch {
            // ignore parse errors for partial chunks
          }
        }
      }
      // flush remaining buffer
      if (buffer.trim()) {
        const trimmed = buffer.trim();
        if (trimmed.startsWith('data: ')) {
          try {
            const data = JSON.parse(trimmed.slice(6));
            if (data.type === 'done') finishOnce();
            else if (data.type === 'error') callbacks.onError?.(data.message);
            else if (data.type === 'rag_sources') callbacks.onRagSources?.(data.sources || []);
            else if (data.type === 'web_sources') callbacks.onWebSources?.(data.sources || []);
          } catch {}
        }
      }
      finishOnce();
    } catch (e: any) {
      if (e.name === 'AbortError') {
        finishOnce();
      } else {
        callbacks.onError?.(e.message || 'Stream error');
      }
    }
  }).catch((e: any) => {
    if (e.name !== 'AbortError') {
      callbacks.onError?.(e.message || '请求失败');
    }
  });

  return {
    abort: () => {
      ctrl.abort();
      // Also tell backend to stop
      fetch(`${API_BASE}/api/chat/stop`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ colleague_id: colleagueId, messages: [], web_search_enabled: false }),
      }).catch(() => {});
    },
  };
}
