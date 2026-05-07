import { useReducer, createContext, useContext, type ReactNode, useEffect } from 'react';
import type { AppState, AppAction, Colleague, Message } from '@/types';
import * as api from '@/lib/api';

function backendToSettings(data: any) {
  return {
    avatar: data.user_avatar_path || '',
    fontSize: data.chat_font_size || 15,
    apiUrl: data.api_base || 'https://api.siliconflow.cn/v1',
    apiKey: data.api_key || '',
    model: data.model || 'Pro/moonshotai/Kimi-K2.5',
    webSearchUrl: data.ollama_web_search_url || '',
    webSearchKey: data.ollama_web_search_api_key || '',
    webSearchEnabled: false,
    userAvatarPath: data.user_avatar_path || '',
    userEmail: data.user_email || '',
  };
}

function historiesToMessages(histories: Record<string, any[]>): Record<string, Message[]> {
  const out: Record<string, Message[]> = {};
  for (const [cid, list] of Object.entries(histories)) {
    out[cid] = (list || []).map((m, idx) => ({
      id: `hist-${cid}-${idx}`,
      role: m.role,
      content: m.content || '',
      timestamp: (m.ts || Date.now() / 1000) * 1000,
    }));
  }
  return out;
}

const initialState: AppState = {
  colleagues: [],
  sessions: [],
  currentSessionId: null,
  histories: {},
  histBoundaries: {},
  settings: {
    avatar: '',
    fontSize: 15,
    apiUrl: 'https://api.siliconflow.cn/v1',
    apiKey: '',
    model: 'Pro/moonshotai/Kimi-K2.5',
    webSearchUrl: '',
    webSearchKey: '',
    webSearchEnabled: false,
    userAvatarPath: '',
    userEmail: '',
  },
  leftPanelCollapsed: false,
  rightPanelCollapsed: false,
  settingsOpen: false,
  adminPanelOpen: false,
  apiTesting: false,
  apiTestResult: null,
  webTesting: false,
  webTestResult: null,
  streamingColleagueId: null,
  streamingStatus: '',
  historyExpandedIds: [],
  loaded: false,
};

function appReducer(state: AppState, action: AppAction): AppState {
  switch (action.type) {
    case 'SET_LOADED':
      return { ...state, loaded: action.payload };
    case 'SET_COLLEAGUES': {
      const colleagues = action.payload;
      const sessions = colleagues.map((c: Colleague) => ({
        id: `session-${c.colleague_id}`,
        skillId: c.colleague_id,
        skillName: c.display_name,
        skillIcon: c.meta?.icon || 'Search',
        avatar: api.getSkillIconUrl(c.colleague_id),
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      }));
      return { ...state, colleagues, sessions };
    }
    case 'SET_HISTORIES': {
      const histories = action.payload;
      const boundaries: Record<string, number> = {};
      for (const cid of Object.keys(histories)) {
        boundaries[cid] = histories[cid].length;
      }
      return { ...state, histories, histBoundaries: boundaries };
    }
    case 'SET_HIST_BOUNDARIES':
      return { ...state, histBoundaries: action.payload };
    case 'SELECT_COLLEAGUE': {
      const cid = action.payload;
      const session = state.sessions.find(s => s.skillId === cid);
      return { ...state, currentSessionId: session ? session.id : null };
    }
    case 'SET_CURRENT_SESSION':
      return { ...state, currentSessionId: action.payload };
    case 'UPDATE_SETTINGS':
      return { ...state, settings: { ...state.settings, ...action.payload } };
    case 'TOGGLE_LEFT_PANEL':
      return { ...state, leftPanelCollapsed: !state.leftPanelCollapsed };
    case 'TOGGLE_RIGHT_PANEL':
      return { ...state, rightPanelCollapsed: !state.rightPanelCollapsed };
    case 'TOGGLE_SETTINGS':
      return { ...state, settingsOpen: !state.settingsOpen };
    case 'TOGGLE_ADMIN_PANEL':
      return { ...state, adminPanelOpen: !state.adminPanelOpen };
    case 'SET_API_TESTING':
      return { ...state, apiTesting: action.payload };
    case 'SET_API_TEST_RESULT':
      return { ...state, apiTestResult: action.payload };
    case 'SET_WEB_TESTING':
      return { ...state, webTesting: action.payload };
    case 'SET_WEB_TEST_RESULT':
      return { ...state, webTestResult: action.payload };
    case 'SET_STREAMING':
      return {
        ...state,
        streamingColleagueId: action.payload.colleagueId,
        streamingStatus: action.payload.status,
      };
    case 'TOGGLE_HISTORY_EXPANDED': {
      const set = new Set(state.historyExpandedIds);
      if (set.has(action.payload)) {
        set.delete(action.payload);
      } else {
        set.add(action.payload);
      }
      return { ...state, historyExpandedIds: Array.from(set) };
    }
    case 'ADD_LOCAL_MESSAGE': {
      const { colleagueId, message } = action.payload;
      const list = state.histories[colleagueId] ? [...state.histories[colleagueId]] : [];
      list.push(message);
      return { ...state, histories: { ...state.histories, [colleagueId]: list } };
    }
    case 'UPDATE_LOCAL_MESSAGE': {
      const { colleagueId, messageId, content } = action.payload;
      const list = (state.histories[colleagueId] || []).map(m =>
        m.id === messageId ? { ...m, content } : m
      );
      return { ...state, histories: { ...state.histories, [colleagueId]: list } };
    }
    case 'SET_MESSAGE_RAG_SOURCES': {
      const { colleagueId, messageId, sources } = action.payload;
      const list = (state.histories[colleagueId] || []).map(m =>
        m.id === messageId ? { ...m, ragSources: sources } : m
      );
      return { ...state, histories: { ...state.histories, [colleagueId]: list } };
    }
    case 'SET_MESSAGE_WEB_SOURCES': {
      const { colleagueId, messageId, sources } = action.payload;
      const list = (state.histories[colleagueId] || []).map(m =>
        m.id === messageId ? { ...m, webSources: sources } : m
      );
      return { ...state, histories: { ...state.histories, [colleagueId]: list } };
    }
    case 'CLEAR_LOCAL_MESSAGES': {
      const next = { ...state.histories };
      delete next[action.payload];
      return { ...state, histories: next };
    }
    case 'REMOVE_COLLEAGUE': {
      const id = action.payload;
      return {
        ...state,
        colleagues: state.colleagues.filter(c => c.colleague_id !== id),
        sessions: state.sessions.filter(s => s.skillId !== id),
      };
    }
    case 'RENAME_COLLEAGUE': {
      const { colleagueId, name } = action.payload;
      return {
        ...state,
        colleagues: state.colleagues.map(c =>
          c.colleague_id === colleagueId ? { ...c, display_name: name } : c
        ),
        sessions: state.sessions.map(s =>
          s.skillId === colleagueId ? { ...s, skillName: name } : s
        ),
      };
    }
    case 'ADD_COLLEAGUE': {
      const c = action.payload;
      if (state.colleagues.find(x => x.colleague_id === c.colleague_id)) return state;
      const session = {
        id: `session-${c.colleague_id}`,
        skillId: c.colleague_id,
        skillName: c.display_name,
        skillIcon: c.meta?.icon || 'Search',
        avatar: api.getSkillIconUrl(c.colleague_id),
        messages: [],
        createdAt: Date.now(),
        updatedAt: Date.now(),
      };
      return {
        ...state,
        colleagues: [...state.colleagues, c],
        sessions: [...state.sessions, session],
      };
    }
    default:
      return state;
  }
}

interface StoreContextType {
  state: AppState;
  dispatch: React.Dispatch<AppAction>;
}

const StoreContext = createContext<StoreContextType | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [state, dispatch] = useReducer(appReducer, initialState);

  useEffect(() => {
    let cancelled = false;
    async function init() {
      try {
        const [skillsRes, histRes, settingsRes] = await Promise.all([
          api.getSkills(),
          api.getHistories(),
          api.getSettings(),
        ]);
        if (cancelled) return;
        dispatch({ type: 'SET_COLLEAGUES', payload: skillsRes.colleagues || [] });
        dispatch({ type: 'SET_HISTORIES', payload: historiesToMessages(histRes || {}) });
        dispatch({ type: 'UPDATE_SETTINGS', payload: backendToSettings(settingsRes || {}) });
        // Select first colleague if none selected
        const first = (skillsRes.colleagues || [])[0];
        if (first) {
          dispatch({ type: 'SELECT_COLLEAGUE', payload: first.colleague_id });
        }
        dispatch({ type: 'SET_LOADED', payload: true });
      } catch (e) {
        console.error('Init failed', e);
        dispatch({ type: 'SET_LOADED', payload: true });
      }
    }
    init();
    return () => { cancelled = true; };
  }, []);

  return (
    <StoreContext.Provider value={{ state, dispatch }}>
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) throw new Error('useStore must be used within StoreProvider');
  return context;
}
