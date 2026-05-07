// Best-effort plain-text conversion for assistant messages (matches Qt behavior)

const BRACKET_EMOJI: Record<string, string> = {
  '捂脸哭': '😂', '笑哭': '😂', '大哭': '😭', '流泪': '😭',
  '破涕为笑': '😂', '滑稽': '🤪', 'doge': '🐶', '二哈': '🐶',
  '666': '👍', '强': '👍', '弱': '👎', '爱心': '❤️', '心碎': '💔',
  '狗头': '🐶', '吃瓜': '🍉', '打call': '📣', 'OK': '👌', '好的': '👌',
  '再见': '👋', '握手': '🤝', '加油': '💪', '叹气': '😮‍💨',
  '无语': '😑', '白眼': '🙄', '害羞': '😳', '机智': '😏',
};

export function substituteBracketEmoticons(text: string): string {
  if (!text || !text.includes('[')) return text;
  return text.replace(/\[([^\[\]]{1,12})\]/g, (match, inner) => {
    const key = inner.trim();
    return BRACKET_EMOJI[key] || match;
  });
}

export function stripMarkdownLikeToPlain(s: string): string {
  if (!s) return s;
  let text = s;
  text = text.replace(/```[^\n]*\n([\s\S]*?)```/g, '$1');
  text = text.replace(/```([\s\S]*?)```/g, '$1');
  text = text.replace(/<[^>]+>/g, '');
  text = text.replace(/!\[([^\]]*)\]\([^)]*\)/g, '$1');
  text = text.replace(/\[([^\]]+)\]\([^)]*\)/g, '$1');
  text = text.replace(/<(https?:\/\/[^>]+)>/g, '$1');
  text = text.replace(/^(#{1,6})\s+/gm, '');
  text = text.replace(/^>\s?/gm, '');
  text = text.replace(/^\s*([-*_])(?:\s*\1){2,}\s*$/gm, '');
  text = text.replace(/^\s*\d+\.\s+/gm, '');
  text = text.replace(/^\s*[-*+]\s+/gm, '');
  text = text.replace(/~~([^~]+)~~/g, '$1');
  text = text.replace(/`([^`]+)`/g, '$1');
  for (let i = 0; i < 4; i++) {
    text = text.replace(/\*\*([^*]+)\*\*/g, '$1');
    text = text.replace(/__([^_]+)__/g, '$1');
    text = text.replace(/(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)/g, '$1');
    text = text.replace(/(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)/g, '$1');
  }
  text = text.replace(/\*\*/g, '').replace(/__/g, '');
  text = text.replace(/\n{3,}/g, '\n\n');
  return text.trim();
}

export function assistantPlainForDisplay(raw: string): string {
  return substituteBracketEmoticons(stripMarkdownLikeToPlain(raw));
}
