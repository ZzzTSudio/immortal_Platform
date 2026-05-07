import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { motion } from 'framer-motion';
import {
  Send, Globe, Square, User, Copy, Check,
  RotateCcw, ThumbsUp, ThumbsDown, FileText, X, ExternalLink, Paperclip
} from 'lucide-react';
import { useStore } from '@/store/useStore';
import type { Message, RagSourceDocument, WebSourceDocument } from '@/types';
import * as api from '@/lib/api';
import { assistantPlainForDisplay, substituteBracketEmoticons } from '@/lib/text-utils';

const CHAT_TIME_GAP_MS = 120 * 1000;
const STICKER_COOLDOWN_MS = 3 * 60 * 1000; // 3 minutes cooldown
const MAX_CHAT_FILES = 3;
const MAX_CHAT_FILE_BYTES = 5 * 1024 * 1024;
const CHAT_FILE_EXTENSIONS = ['.pdf', '.md', '.doc', '.docx', '.txt'];

// Track last sticker time per colleague
const lastStickerTime: Record<string, number> = {};

function formatChatTime(ts: number): string {
  const d = new Date(ts);
  return `${d.getFullYear()}年${d.getMonth() + 1}月${d.getDate()}日 ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
}

function formatFileSize(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / 1024 / 1024).toFixed(1)} MB`;
}

function fileExtension(name: string): string {
  const dot = name.lastIndexOf('.');
  return dot >= 0 ? name.slice(dot).toLowerCase() : '';
}

function TypingIndicator() {
  return (
    <div className="flex items-center gap-1 px-1 py-2">
      <div className="w-1.5 h-1.5 rounded-full bg-[#E8D5B5] typing-dot" />
      <div className="w-1.5 h-1.5 rounded-full bg-[#E8D5B5] typing-dot" />
      <div className="w-1.5 h-1.5 rounded-full bg-[#E8D5B5] typing-dot" />
    </div>
  );
}

function StreamingCursor() {
  return <span className="inline-block w-[2px] h-[1em] bg-[#E8D5B5] ml-0.5 cursor-blink align-middle" />;
}

function MessageActions({ onCopy, onRegenerate }: { onCopy: () => void; onRegenerate?: () => void }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };
  return (
    <div className="flex items-center gap-1 mt-2 opacity-0 group-hover:opacity-100 transition-opacity">
      <button onClick={handleCopy} className="p-1.5 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors" title="复制">
        {copied ? <Check size={12} className="text-green-400" /> : <Copy size={12} className="text-[#4D4D4D]" />}
      </button>
      {onRegenerate && (
        <button onClick={onRegenerate} className="p-1.5 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors" title="重新生成">
          <RotateCcw size={12} className="text-[#4D4D4D]" />
        </button>
      )}
      <button className="p-1.5 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors" title="赞">
        <ThumbsUp size={12} className="text-[#4D4D4D]" />
      </button>
      <button className="p-1.5 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors" title="踩">
        <ThumbsDown size={12} className="text-[#4D4D4D]" />
      </button>
    </div>
  );
}

function RagCitations({ sources, onOpen }: { sources: RagSourceDocument[]; onOpen: (source: RagSourceDocument) => void }) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-[#6F6F6F]">
      <span>引用：</span>
      {sources.map((source, index) => (
        <button
          key={`${source.doc_id}-${source.filename}`}
          onClick={() => onOpen(source)}
          className="inline-flex items-center gap-1 rounded-full border border-[rgba(232,213,181,0.18)] bg-[#151515] px-2 py-1 text-[#AFAFAF] transition-colors hover:border-[#E8D5B5]/40 hover:text-[#E8D5B5]"
          title="查看该文件命中的索引内容"
        >
          <FileText size={11} />
          {index + 1}.{source.filename || source.doc_id}
        </button>
      ))}
    </div>
  );
}

function WebCitations({ sources, onOpen }: { sources: WebSourceDocument[]; onOpen: (source: WebSourceDocument) => void }) {
  if (!sources.length) return null;
  return (
    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-[#6F6F6F]">
      <span>联网：</span>
      {sources.map((source, index) => (
        <button
          key={`${source.url}-${index}`}
          onClick={() => onOpen(source)}
          className="inline-flex max-w-full items-center gap-1 rounded-full border border-[rgba(96,165,250,0.2)] bg-[#101820] px-2 py-1 text-[#AFC7E8] transition-colors hover:border-blue-300/50 hover:text-blue-200"
          title="查看网页检索摘要"
        >
          <ExternalLink size={11} />
          <span className="truncate">
            {index + 1}.{source.title || '未命名网页'} {source.url}
          </span>
        </button>
      ))}
    </div>
  );
}

function MessageBubble({ message, fontSize, onRegenerate, isUserAvatar, peerAvatar, onOpenRagSource, onOpenWebSource }: {
  message: Message;
  fontSize: number;
  onRegenerate?: () => void;
  isUserAvatar?: string;
  peerAvatar?: string;
  onOpenRagSource?: (source: RagSourceDocument) => void;
  onOpenWebSource?: (source: WebSourceDocument) => void;
}) {
  const isUser = message.role === 'user';
  const isSticker = message.role === 'sticker';

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content);
  };

  if (isSticker) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
        className="flex gap-3 flex-row group"
      >
        <div className="flex-shrink-0 w-8 h-8 rounded-full overflow-hidden flex items-center justify-center bg-[#1E1E1E] border border-[rgba(232,213,181,0.15)]">
          {peerAvatar ? (
            <img src={peerAvatar} alt="AI" className="w-full h-full object-cover" />
          ) : (
            <User size={16} className="text-[#8B8B8B]" />
          )}
        </div>
        <div className="flex-1 max-w-[80%]">
          <img
            src={message.content}
            alt="sticker"
            className="max-h-[88px] max-w-[110px] rounded-lg"
            onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
          />
        </div>
      </motion.div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} group`}
    >
      <div className={`flex-shrink-0 w-8 h-8 rounded-full overflow-hidden flex items-center justify-center ${
        isUser
          ? 'bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)]'
          : 'bg-[#1E1E1E] border border-[rgba(232,213,181,0.15)]'
      }`}>
        {isUser ? (
          isUserAvatar ? (
            <img src={isUserAvatar} alt="user" className="w-full h-full object-cover" />
          ) : (
            <User size={16} className="text-[#8B8B8B]" />
          )
        ) : (
          peerAvatar ? (
            <img src={peerAvatar} alt="AI" className="w-full h-full object-cover" />
          ) : (
            <User size={16} className="text-[#8B8B8B]" />
          )
        )}
      </div>

      <div className={`flex-1 max-w-[80%] ${isUser ? 'text-right' : 'text-left'}`}>
        {isUser ? (
          <div className="inline-block px-4 py-2.5 bg-[#2A2A2A] rounded text-left">
            <p style={{ fontSize: `${fontSize}px`, lineHeight: 1.6, color: '#FFFFFF' }}>
              {message.content}
            </p>
            {!!message.attachments?.length && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {message.attachments.map((file) => (
                  <span
                    key={`${file.name}-${file.size}`}
                    className="inline-flex max-w-[220px] items-center gap-1 rounded border border-[rgba(232,213,181,0.18)] bg-[#1E1E1E] px-2 py-1 text-[11px] text-[#AFAFAF]"
                  >
                    <FileText size={11} className="shrink-0 text-[#E8D5B5]" />
                    <span className="truncate">{file.name}</span>
                    <span className="shrink-0 text-[#6F6F6F]">{formatFileSize(file.size)}</span>
                  </span>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div>
            <div className="relative">
              <div className="font-serif-cn text-white" style={{ fontSize: `${fontSize}px`, lineHeight: 1.6 }}>
                {message.content.split('\n').map((line, i, arr) => (
                  <p key={i} className={line.trim() === '' ? 'h-4' : ''}>
                    {line}
                    {message.isStreaming && i === arr.length - 1 && <StreamingCursor />}
                  </p>
                ))}
                {message.isStreaming && message.content === '' && <TypingIndicator />}
              </div>
            </div>
            {message.role === 'assistant' && message.ragSources && onOpenRagSource && (
              <RagCitations sources={message.ragSources} onOpen={onOpenRagSource} />
            )}
            {message.role === 'assistant' && message.webSources && onOpenWebSource && (
              <WebCitations sources={message.webSources} onOpen={onOpenWebSource} />
            )}
            <MessageActions onCopy={handleCopy} onRegenerate={onRegenerate} />
          </div>
        )}
      </div>
    </motion.div>
  );
}

function TimeSeparator({ timestamp }: { timestamp: number }) {
  return (
    <div className="flex justify-center my-4">
      <span className="px-3 py-1 bg-[#2A2A2A] rounded-full text-[11px] text-[#8B8B8B]">
        {formatChatTime(timestamp)}
      </span>
    </div>
  );
}

function EmptyState({ welcomeMessage, introContent, skillIcon }: {
  welcomeMessage: string;
  introContent?: string;
  skillIcon?: string;
}) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex-1 flex flex-col items-center justify-center px-8"
    >
      <div className="text-center max-w-lg">
        <motion.div
          initial={{ scale: 0.9, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ delay: 0.1, duration: 0.6, ease: [0.25, 1, 0.5, 1] }}
        >
          <img
            src={skillIcon || "/ai-avatar.png"}
            alt="AI"
            className="w-16 h-16 mx-auto mb-5 opacity-60 rounded-full object-cover"
            onError={(e) => { (e.target as HTMLImageElement).src = '/ai-avatar.png'; }}
          />
        </motion.div>
        <motion.p
          initial={{ y: 10, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.2, duration: 0.5 }}
          className="text-[22px] font-medium text-white font-serif-cn mb-3 tracking-wide"
        >
          {welcomeMessage}
        </motion.p>
        {introContent && (
          <motion.div
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-[14px] text-[#8B8B8B] leading-relaxed whitespace-pre-wrap"
          >
            {introContent}
          </motion.div>
        )}
        {!introContent && (
          <motion.p
            initial={{ y: 10, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3, duration: 0.5 }}
            className="text-[13px] text-[#4D4D4D] mb-8"
          >
            <span className="cursor-blink">_</span>
          </motion.p>
        )}
      </div>
    </motion.div>
  );
}

export default function ChatArea() {
  const { state, dispatch } = useStore();
  const {
    colleagues,
    sessions,
    currentSessionId,
    settings,
    histories,
    histBoundaries,
    streamingColleagueId,
    streamingStatus,
    historyExpandedIds,
  } = state;

  const [inputText, setInputText] = useState('');
  const [webSearchEnabled, setWebSearchEnabled] = useState(false);
  const [localStreaming, setLocalStreaming] = useState(false);
  const [introContent, setIntroContent] = useState<string>('');
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [selectedRagSource, setSelectedRagSource] = useState<RagSourceDocument | null>(null);
  const [selectedWebSource, setSelectedWebSource] = useState<WebSourceDocument | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const streamAbortRef = useRef<(() => void) | null>(null);
  const streamingBufferRef = useRef('');
  const streamFinishedRef = useRef(false);
  const currentAssistantIdRef = useRef<string | null>(null);
  const manuallyStoppedRef = useRef(false);

  const currentSession = sessions.find(s => s.id === currentSessionId);
  const currentColleagueId = currentSession?.skillId || null;
  const colleague = colleagues.find(c => c.colleague_id === currentColleagueId);
  const allMessages = currentColleagueId ? (histories[currentColleagueId] || []) : [];
  const boundary = currentColleagueId ? (histBoundaries[currentColleagueId] || 0) : 0;
  const isExpanded = currentColleagueId ? historyExpandedIds.includes(currentColleagueId) : false;

  // Filter messages based on history fold
  const messages = useMemo(() => {
    if (boundary <= 0 || isExpanded) return allMessages;
    return allMessages.slice(boundary);
  }, [allMessages, boundary, isExpanded]);

  const hasPreSessionHistory = boundary > 0;

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  useEffect(() => {
    if (currentColleagueId) {
      api.getSkillIntro(currentColleagueId).then(res => {
        setIntroContent(res?.content || '');
      }).catch(() => {
        setIntroContent('');
      });
    } else {
      setIntroContent('');
    }
  }, [currentColleagueId]);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
    }
  }, [inputText]);

  const handleStop = useCallback(() => {
    manuallyStoppedRef.current = true;
    if (streamAbortRef.current) {
      streamAbortRef.current();
      streamAbortRef.current = null;
    }
    setLocalStreaming(false);
    if (currentAssistantIdRef.current && currentColleagueId) {
      const content = streamingBufferRef.current;
      dispatch({
        type: 'UPDATE_LOCAL_MESSAGE',
        payload: { colleagueId: currentColleagueId, messageId: currentAssistantIdRef.current, content },
      });
      const plainContent = assistantPlainForDisplay(content);
      if (plainContent) {
        dispatch({
          type: 'UPDATE_LOCAL_MESSAGE',
          payload: { colleagueId: currentColleagueId, messageId: currentAssistantIdRef.current, content: plainContent },
        });
        api.addHistoryMessage(currentColleagueId, 'assistant', plainContent, Date.now() / 1000).catch(() => {});
      }
    }
    dispatch({ type: 'SET_STREAMING', payload: { colleagueId: null, status: '' } });
  }, [currentColleagueId, dispatch]);

  // Stop streaming when switching colleague
  useEffect(() => {
    if (localStreaming && streamingColleagueId && streamingColleagueId !== currentColleagueId) {
      handleStop();
    }
  }, [currentColleagueId, localStreaming, streamingColleagueId, handleStop]);

  const handleNewSession = useCallback(async () => {
    if (!currentColleagueId) return;
    handleStop();
    try {
      await api.clearHistory(currentColleagueId);
      dispatch({ type: 'CLEAR_LOCAL_MESSAGES', payload: currentColleagueId });
      dispatch({ type: 'SET_HIST_BOUNDARIES', payload: { ...histBoundaries, [currentColleagueId]: 0 } });
    } catch (err: any) {
      alert('清空失败：' + err.message);
    }
  }, [currentColleagueId, dispatch, handleStop, histBoundaries]);

  const handleFileSelect = useCallback((event: React.ChangeEvent<HTMLInputElement>) => {
    const picked = Array.from(event.target.files || []);
    if (!picked.length) return;

    const next = [...selectedFiles];
    for (const file of picked) {
      if (next.length >= MAX_CHAT_FILES) {
        alert(`最多上传 ${MAX_CHAT_FILES} 个文件`);
        break;
      }
      if (!CHAT_FILE_EXTENSIONS.includes(fileExtension(file.name))) {
        alert(`不支持的文件格式：${file.name}`);
        continue;
      }
      if (file.size > MAX_CHAT_FILE_BYTES) {
        alert(`文件超过 5MB：${file.name}`);
        continue;
      }
      next.push(file);
    }
    setSelectedFiles(next);
    event.target.value = '';
  }, [selectedFiles]);

  const removeSelectedFile = useCallback((index: number) => {
    setSelectedFiles(files => files.filter((_, i) => i !== index));
  }, []);

  const handleSend = useCallback(async (text: string) => {
    if ((!text.trim() && selectedFiles.length === 0) || !currentColleagueId || !colleague) return;
    if (localStreaming) {
      handleStop();
      return;
    }

    const trimmed = substituteBracketEmoticons(text.trim()) || '请参考我上传的文件。';
    const filesForRequest = selectedFiles;
    setInputText('');

    // Build messages for API BEFORE adding assistant placeholder
    const allMsgs = histories[currentColleagueId] || [];
    const apiMessages = allMsgs
      .filter(m => (m.role === 'user' || m.role === 'assistant') && !m.isStreaming)
      .map(m => ({ role: m.role, content: m.content }));
    // Append the new user message
    apiMessages.push({ role: 'user', content: trimmed });

    // Add user message locally and persist
    const userMsgId = `msg-${Date.now()}`;
    const userMsg: Message = {
      id: userMsgId,
      role: 'user',
      content: trimmed,
      timestamp: Date.now(),
      attachments: filesForRequest.map(file => ({ name: file.name, size: file.size })),
    };
    dispatch({ type: 'ADD_LOCAL_MESSAGE', payload: { colleagueId: currentColleagueId, message: userMsg } });
    try {
      await api.addHistoryMessage(currentColleagueId, 'user', trimmed, Date.now() / 1000);
    } catch (e) {
      console.error('Failed to save user message', e);
    }

    // Add assistant placeholder
    const aiMsgId = `msg-${Date.now() + 1}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: Date.now() + 1,
      isStreaming: true,
    };
    dispatch({ type: 'ADD_LOCAL_MESSAGE', payload: { colleagueId: currentColleagueId, message: aiMsg } });
    currentAssistantIdRef.current = aiMsgId;
    streamingBufferRef.current = '';
    streamFinishedRef.current = false;
    manuallyStoppedRef.current = false;
    setLocalStreaming(true);
    dispatch({ type: 'SET_STREAMING', payload: { colleagueId: currentColleagueId, status: '正在准备请求…' } });

    const { abort } = api.streamChat(
      currentColleagueId,
      apiMessages,
      webSearchEnabled,
      filesForRequest,
      {
        onChunk: (chunk) => {
          const current = streamingBufferRef.current;
          if (chunk.startsWith(current) && chunk.length > current.length) {
            streamingBufferRef.current = chunk;
          } else if (!current.endsWith(chunk)) {
            streamingBufferRef.current += chunk;
          }
          dispatch({
            type: 'UPDATE_LOCAL_MESSAGE',
            payload: { colleagueId: currentColleagueId, messageId: aiMsgId, content: streamingBufferRef.current },
          });
        },
        onStatus: (msg) => {
          dispatch({ type: 'SET_STREAMING', payload: { colleagueId: currentColleagueId, status: msg } });
        },
        onRagSources: (sources) => {
          dispatch({
            type: 'SET_MESSAGE_RAG_SOURCES',
            payload: { colleagueId: currentColleagueId, messageId: aiMsgId, sources },
          });
        },
        onWebSources: (sources) => {
          dispatch({
            type: 'SET_MESSAGE_WEB_SOURCES',
            payload: { colleagueId: currentColleagueId, messageId: aiMsgId, sources },
          });
        },
        onDone: async () => {
          if (streamFinishedRef.current) return;
          streamFinishedRef.current = true;
          if (manuallyStoppedRef.current) return;
          setLocalStreaming(false);
          streamAbortRef.current = null;
          dispatch({ type: 'SET_STREAMING', payload: { colleagueId: null, status: '' } });
          // Save assistant message to backend
          const plainContent = assistantPlainForDisplay(streamingBufferRef.current);
          if (plainContent) {
            // Update local state with plain text (matching Qt behavior)
            dispatch({
              type: 'UPDATE_LOCAL_MESSAGE',
              payload: { colleagueId: currentColleagueId, messageId: aiMsgId, content: plainContent },
            });
            try {
              await api.addHistoryMessage(currentColleagueId, 'assistant', plainContent, Date.now() / 1000);
            } catch (e) {
              console.error('Failed to save assistant message', e);
            }
            // Random sticker with 10% probability and 3-minute cooldown
            const now = Date.now();
            const lastTime = lastStickerTime[currentColleagueId] || 0;
            const canSendSticker = (now - lastTime) >= STICKER_COOLDOWN_MS;

            if (canSendSticker && Math.random() < 0.10) {
              try {
                const stickerUrl = await api.getRandomSticker();
                if (stickerUrl) {
                  const stickerMsg: Message = {
                    id: `sticker-${Date.now()}`,
                    role: 'sticker',
                    content: stickerUrl,
                    timestamp: Date.now(),
                  };
                  dispatch({ type: 'ADD_LOCAL_MESSAGE', payload: { colleagueId: currentColleagueId, message: stickerMsg } });
                  await api.addHistoryMessage(currentColleagueId, 'sticker', stickerUrl, Date.now() / 1000);
                  lastStickerTime[currentColleagueId] = now;
                }
              } catch (e) {
                console.error('Sticker failed', e);
              }
            }
          }
        },
        onError: async (msg) => {
          setLocalStreaming(false);
          streamAbortRef.current = null;
          dispatch({ type: 'SET_STREAMING', payload: { colleagueId: null, status: '' } });
          if (manuallyStoppedRef.current) return;
          // Update empty/error assistant message
          if (currentAssistantIdRef.current) {
            dispatch({
              type: 'UPDATE_LOCAL_MESSAGE',
              payload: { colleagueId: currentColleagueId, messageId: aiMsgId, content: streamingBufferRef.current.trim() ? streamingBufferRef.current : `请求出错：${msg}` },
            });
          }
        },
      }
    );

    streamAbortRef.current = abort;
    setSelectedFiles([]);
  }, [currentColleagueId, colleague, localStreaming, handleStop, dispatch, histories, webSearchEnabled, selectedFiles]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (inputText.trim() || selectedFiles.length > 0) {
        handleSend(inputText);
      }
    }
  };

  // Determine visible messages with time separators
  const renderedItems: Array<{ type: 'msg'; message: Message } | { type: 'time'; timestamp: number }> = [];
  let prevTs: number | null = null;
  for (const msg of messages) {
    if (prevTs === null || msg.timestamp - prevTs >= CHAT_TIME_GAP_MS) {
      renderedItems.push({ type: 'time', timestamp: msg.timestamp });
    }
    renderedItems.push({ type: 'msg', message: msg });
    prevTs = msg.timestamp;
  }

  const isStreaming = localStreaming && streamingColleagueId === currentColleagueId;
  const welcomeMessage = colleague?.meta?.welcome_message || `你好，我是${colleague?.display_name || 'AI助手'}。`;

  return (
    <div className="flex-1 flex flex-col h-full relative">
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-3 border-b border-[rgba(255,255,255,0.08)]">
        <div className="flex items-center gap-3">
          {colleague && (
            <>
              <span className="text-[13px] text-[#E8D5B5]">{colleague.display_name}</span>
              <span className="text-[11px] text-[#4D4D4D]">/</span>
            </>
          )}
          <span className="text-[13px] text-[#8B8B8B]">
            {colleague ? '对话中' : '未选择同事'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {isStreaming && (
            <button
              onClick={handleStop}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2A2A2A] rounded text-[12px] text-[#8B8B8B] hover:text-white transition-colors"
            >
              <Square size={11} />
              停止生成
            </button>
          )}
          {colleague && (
            <button
              onClick={handleNewSession}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#2A2A2A] rounded text-[12px] text-[#8B8B8B] hover:text-white transition-colors"
              title="清空会话"
            >
              <RotateCcw size={11} />
              清空会话
            </button>
          )}
        </div>
      </div>

      {/* History Fold Bar */}
      {hasPreSessionHistory && currentColleagueId && (
        <div className="flex justify-center py-2">
          <button
            onClick={() => dispatch({ type: 'TOGGLE_HISTORY_EXPANDED', payload: currentColleagueId })}
            className="px-3 py-1 bg-[#2A2A2A] rounded text-[11px] text-[#8B8B8B] hover:text-white transition-colors"
          >
            {isExpanded ? '▽ 收起历史聊天记录' : '△ 展开历史聊天记录'}
          </button>
        </div>
      )}

      {/* Messages Area */}
      {messages.length === 0 && !isStreaming ? (
        <EmptyState
          welcomeMessage={welcomeMessage}
          introContent={introContent}
          skillIcon={colleague ? api.getSkillIconUrl(colleague.colleague_id) : undefined}
        />
      ) : (
        <div className="flex-1 overflow-y-auto scrollbar-hide px-6 py-6">
          <div className="max-w-3xl mx-auto space-y-6">
            {renderedItems.map((item, idx) => {
              if (item.type === 'time') {
                return <TimeSeparator key={`t-${idx}`} timestamp={item.timestamp} />;
              }
              const msg = item.message;
              return (
                <MessageBubble
                  key={msg.id}
                  message={msg}
                  fontSize={settings.fontSize}
                  isUserAvatar={settings.avatar}
                  peerAvatar={colleague ? api.getSkillIconUrl(colleague.colleague_id) : undefined}
                  onOpenRagSource={setSelectedRagSource}
                  onOpenWebSource={setSelectedWebSource}
                  onRegenerate={msg.role === 'assistant' ? () => {
                    const msgIndex = messages.findIndex(m => m.id === msg.id);
                    const userMsg = messages.slice(0, msgIndex).reverse().find(m => m.role === 'user');
                    if (userMsg) handleSend(userMsg.content);
                  } : undefined}
                />
              );
            })}
            {isStreaming && streamingStatus && (
              <div className="flex items-center gap-2 text-[12px] text-[#4D4D4D]">
                <span className="animate-spin">⠋</span>
                {streamingStatus}
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      )}

      {/* Input Console */}
      {selectedRagSource && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="max-h-[76vh] w-[min(760px,calc(100vw-48px))] overflow-hidden rounded-xl border border-[rgba(255,255,255,0.1)] bg-[#141414] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-[14px] text-white">
                  <FileText size={16} className="text-[#E8D5B5]" />
                  <span className="truncate">{selectedRagSource.filename || selectedRagSource.doc_id}</span>
                </div>
                <div className="mt-1 text-[11px] text-[#6F6F6F]">
                  {selectedRagSource.source_type} · {selectedRagSource.tag || 'untagged'} · {selectedRagSource.chunks.length} 个命中片段
                </div>
              </div>
              <button
                onClick={() => setSelectedRagSource(null)}
                className="rounded p-1.5 text-[#8B8B8B] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-5 space-y-3">
              {selectedRagSource.chunks.map((chunk, index) => (
                <div key={chunk.chunk_id} className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A0A] p-3">
                  <div className="mb-2 flex items-center justify-between text-[11px] text-[#6F6F6F]">
                    <span>片段 {index + 1}</span>
                    <span>score {chunk.score.toFixed(3)}</span>
                  </div>
                  <pre className="whitespace-pre-wrap break-words text-[12px] leading-6 text-[#D8D8D8] font-sans">
                    {chunk.content}
                  </pre>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {selectedWebSource && (
        <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="max-h-[76vh] w-[min(760px,calc(100vw-48px))] overflow-hidden rounded-xl border border-[rgba(255,255,255,0.1)] bg-[#141414] shadow-2xl">
            <div className="flex items-start justify-between gap-4 border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
              <div className="min-w-0">
                <div className="flex items-center gap-2 text-[14px] text-white">
                  <ExternalLink size={16} className="text-blue-200" />
                  <span className="truncate">{selectedWebSource.title || '未命名网页'}</span>
                </div>
                <a
                  href={selectedWebSource.url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block truncate text-[11px] text-blue-300 hover:text-blue-200"
                >
                  {selectedWebSource.url}
                </a>
              </div>
              <button
                onClick={() => setSelectedWebSource(null)}
                className="rounded p-1.5 text-[#8B8B8B] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
              >
                <X size={18} />
              </button>
            </div>
            <div className="max-h-[60vh] overflow-y-auto p-5">
              <pre className="whitespace-pre-wrap break-words rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A0A] p-4 text-[12px] leading-6 text-[#D8D8D8] font-sans">
                {selectedWebSource.content || '该网页结果没有返回摘要内容。'}
              </pre>
            </div>
          </div>
        </div>
      )}

      <div className="px-6 pb-6 pt-2">
        <div className="max-w-3xl mx-auto">
          <div className="relative bg-[#1E1E1E] border border-[rgba(255,255,255,0.08)] rounded-lg hover:border-[rgba(255,255,255,0.12)] focus-within:border-[#E8D5B5]/30 transition-colors">
            {selectedFiles.length > 0 && (
              <div className="flex flex-wrap gap-2 px-3 pt-3">
                {selectedFiles.map((file, index) => (
                  <span
                    key={`${file.name}-${file.size}-${index}`}
                    className="inline-flex max-w-[220px] items-center gap-1.5 rounded-md border border-[rgba(232,213,181,0.18)] bg-[#151515] px-2 py-1 text-[11px] text-[#AFAFAF]"
                  >
                    <FileText size={12} className="shrink-0 text-[#E8D5B5]" />
                    <span className="truncate">{file.name}</span>
                    <span className="shrink-0 text-[#6F6F6F]">{formatFileSize(file.size)}</span>
                    <button
                      type="button"
                      onClick={() => removeSelectedFile(index)}
                      className="ml-0.5 rounded p-0.5 text-[#6F6F6F] hover:bg-[rgba(255,255,255,0.08)] hover:text-white"
                      title="移除文件"
                    >
                      <X size={12} />
                    </button>
                  </span>
                ))}
              </div>
            )}
            <textarea
              ref={textareaRef}
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={colleague ? "输入消息，Enter 发送，Shift+Enter 换行" : "请先选择左侧同事"}
              rows={1}
              disabled={!colleague}
              className={`w-full px-4 ${selectedFiles.length ? 'pt-2' : 'pt-3'} pb-12 bg-transparent text-white text-[15px] placeholder-[#4D4D4D] resize-none outline-none font-serif-cn disabled:opacity-50`}
              style={{ minHeight: '60px', maxHeight: '200px' }}
            />

            {/* Toolbar */}
            <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between">
              <div className="flex items-center gap-1">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.md,.doc,.docx,.txt"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={!colleague || isStreaming || selectedFiles.length >= MAX_CHAT_FILES}
                  className={`p-2 rounded-md transition-all ${
                    selectedFiles.length
                      ? 'text-[#E8D5B5] bg-[rgba(232,213,181,0.12)]'
                      : 'text-[#4D4D4D] hover:text-[#8B8B8B] hover:bg-[rgba(255,255,255,0.04)] disabled:opacity-50 disabled:hover:bg-transparent'
                  }`}
                  title="添加临时上下文文件"
                >
                  <Paperclip size={16} />
                </button>
                <button
                  onClick={() => setWebSearchEnabled(!webSearchEnabled)}
                  className={`p-2 rounded-md transition-all ${
                    webSearchEnabled
                      ? 'text-[#E8D5B5] bg-[rgba(232,213,181,0.12)]'
                      : 'text-[#4D4D4D] hover:text-[#8B8B8B] hover:bg-[rgba(255,255,255,0.04)]'
                  }`}
                  title="联网搜索"
                >
                  <Globe size={16} />
                </button>
                {webSearchEnabled && (
                  <motion.span
                    initial={{ opacity: 0, x: -5 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="text-[11px] text-[#E8D5B5] ml-1"
                  >
                    联网搜索已开启
                  </motion.span>
                )}
              </div>

              <button
                onClick={() => handleSend(inputText)}
                disabled={(!inputText.trim() && selectedFiles.length === 0) || !colleague || (isStreaming && (!!inputText.trim() || selectedFiles.length > 0))}
                className={`p-2 rounded-md transition-all ${
                  (inputText.trim() || selectedFiles.length > 0) && !isStreaming && colleague
                    ? 'text-[#111111] bg-[#E8D5B5] hover:bg-[#d9c9a8]'
                    : 'text-[#4D4D4D] bg-[#2A2A2A] cursor-not-allowed'
                }`}
              >
                <Send size={16} />
              </button>
            </div>
          </div>

          <p className="text-center text-[11px] text-[#4D4D4D] mt-2">
            IMMORTAL 可能会产生不准确的信息，请验证重要信息。
          </p>
        </div>
      </div>
    </div>
  );
}
