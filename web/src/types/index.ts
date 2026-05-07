export interface Skill {
  id: string;
  name: string;
  category: string;
  description: string;
  icon: string;
  welcomeMessage: string;
}

export interface Colleague {
  colleague_id: string;
  display_name: string;
  is_builtin: boolean;
  skill_path: string;
  meta: Record<string, any>;
}

export interface PlatformSkill {
  colleague_id: string;
  display_name: string;
  skill_path: string;
  meta: Record<string, any>;
  visibility: 'public' | 'private';
  intro_summary: string;
  avatar_url: string;
  imported: boolean;
}

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'sticker';
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  attachments?: MessageAttachment[];
  ragSources?: RagSourceDocument[];
  webSources?: WebSourceDocument[];
}

export interface MessageAttachment {
  name: string;
  size: number;
}

export interface WebSourceDocument {
  title: string;
  url: string;
  content: string;
}

export interface RagSourceChunk {
  chunk_id: string;
  content: string;
  score: number;
}

export interface RagSourceDocument {
  doc_id: string;
  filename: string;
  source_type: string;
  title: string;
  tag: string;
  chunks: RagSourceChunk[];
}

export interface Session {
  id: string;
  skillId: string;
  skillName: string;
  skillIcon: string;
  avatar?: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

export interface UserSettings {
  avatar: string;
  fontSize: number;
  apiUrl: string;
  apiKey: string;
  model: string;
  webSearchUrl: string;
  webSearchKey: string;
  webSearchEnabled: boolean;
  userAvatarPath: string;
  userEmail: string;
}

export interface AppState {
  colleagues: Colleague[];
  sessions: Session[];
  currentSessionId: string | null;
  histories: Record<string, Message[]>;
  histBoundaries: Record<string, number>;
  settings: UserSettings;
  leftPanelCollapsed: boolean;
  rightPanelCollapsed: boolean;
  settingsOpen: boolean;
  adminPanelOpen: boolean;
  apiTesting: boolean;
  apiTestResult: string | null;
  webTesting: boolean;
  webTestResult: string | null;
  streamingColleagueId: string | null;
  streamingStatus: string;
  historyExpandedIds: string[];
  loaded: boolean;
}

export type AppAction =
  | { type: 'SET_LOADED'; payload: boolean }
  | { type: 'SET_COLLEAGUES'; payload: Colleague[] }
  | { type: 'SET_HISTORIES'; payload: Record<string, Message[]> }
  | { type: 'SET_HIST_BOUNDARIES'; payload: Record<string, number> }
  | { type: 'SELECT_COLLEAGUE'; payload: string | null }
  | { type: 'SET_CURRENT_SESSION'; payload: string | null }
  | { type: 'UPDATE_SETTINGS'; payload: Partial<UserSettings> }
  | { type: 'TOGGLE_LEFT_PANEL' }
  | { type: 'TOGGLE_RIGHT_PANEL' }
  | { type: 'TOGGLE_SETTINGS' }
  | { type: 'TOGGLE_ADMIN_PANEL' }
  | { type: 'SET_API_TESTING'; payload: boolean }
  | { type: 'SET_API_TEST_RESULT'; payload: string | null }
  | { type: 'SET_WEB_TESTING'; payload: boolean }
  | { type: 'SET_WEB_TEST_RESULT'; payload: string | null }
  | { type: 'SET_STREAMING'; payload: { colleagueId: string | null; status: string } }
  | { type: 'TOGGLE_HISTORY_EXPANDED'; payload: string }
  | { type: 'ADD_LOCAL_MESSAGE'; payload: { colleagueId: string; message: Message } }
  | { type: 'UPDATE_LOCAL_MESSAGE'; payload: { colleagueId: string; messageId: string; content: string } }
  | { type: 'SET_MESSAGE_RAG_SOURCES'; payload: { colleagueId: string; messageId: string; sources: RagSourceDocument[] } }
  | { type: 'SET_MESSAGE_WEB_SOURCES'; payload: { colleagueId: string; messageId: string; sources: WebSourceDocument[] } }
  | { type: 'CLEAR_LOCAL_MESSAGES'; payload: string }
  | { type: 'REMOVE_COLLEAGUE'; payload: string }
  | { type: 'RENAME_COLLEAGUE'; payload: { colleagueId: string; name: string } }
  | { type: 'ADD_COLLEAGUE'; payload: Colleague };
