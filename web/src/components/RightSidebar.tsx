import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Plus, Database, Tag
} from 'lucide-react';
import { useStore } from '@/store/useStore';

const knowledgeTags = [
  { id: 'uncategorized', name: '数字人', count: 12 },
  { id: 'finance', name: '财报数据', count: 8 },
  { id: 'scifi', name: '科幻设定', count: 23 },
  { id: 'research', name: '研究笔记', count: 15 },
  { id: 'prompts', name: '提示词库', count: 41 },
  { id: 'code-snippets', name: '代码片段', count: 19 },
];

export default function RightSidebar() {
  const { state } = useStore();
  const { rightPanelCollapsed } = state;
  const [knowledgeExpanded, setKnowledgeExpanded] = useState(true);
  const [hoveredTag, setHoveredTag] = useState<string | null>(null);

  if (rightPanelCollapsed) {
    return (
      <motion.div
        initial={{ width: 320 }}
        animate={{ width: 0, opacity: 0 }}
        transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
        className="h-full overflow-hidden border-l border-[rgba(255,255,255,0.08)]"
      />
    );
  }

  return (
    <motion.div
      initial={{ width: 0, opacity: 0 }}
      animate={{ width: 320, opacity: 1 }}
      transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
      className="h-full panel-surface border-l border-[rgba(255,255,255,0.08)] flex flex-col overflow-hidden"
    >
      <div className="flex-1 overflow-y-auto scrollbar-hide px-4 pt-6">
        {/* Knowledge Space */}
        <div className="mb-5">
          <button
            onClick={() => setKnowledgeExpanded(!knowledgeExpanded)}
            className="flex items-center justify-between w-full py-2 text-[12px] uppercase tracking-[0.15em] text-[#4D4D4D] hover:text-[#8B8B8B] transition-colors"
          >
            <span className="flex items-center gap-2">
              <Database size={13} />
              我的知识空间
            </span>
            <Plus size={12} />
          </button>

          {knowledgeExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              className="flex flex-wrap gap-2 pt-2"
            >
              {knowledgeTags.map(tag => (
                <motion.button
                  key={tag.id}
                  onMouseEnter={() => setHoveredTag(tag.id)}
                  onMouseLeave={() => setHoveredTag(null)}
                  className={`relative px-3 py-1.5 rounded text-[11px] border transition-all ${
                    hoveredTag === tag.id
                      ? 'border-[#E8D5B5]/30 text-[#E8D5B5] bg-[rgba(232,213,181,0.08)]'
                      : 'border-[rgba(255,255,255,0.06)] text-[#8B8B8B] bg-[#1E1E1E]'
                  }`}
                  whileHover={{ y: -2 }}
                >
                  <div className="flex items-center gap-1.5">
                    <Tag size={10} />
                    {tag.name}
                    <span className="text-[#4D4D4D]">{tag.count}</span>
                  </div>
                </motion.button>
              ))}
            </motion.div>
          )}
        </div>
      </div>

      {/* Bottom Status */}
      <div className="px-4 py-3 border-t border-[rgba(255,255,255,0.08)]">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse" />
            <span className="text-[11px] text-[#4D4D4D]">IMMORTAL-v4.0</span>
          </div>
          <span className="text-[11px] text-[#4D4D4D] font-mono-code">
            {Math.floor(Math.random() * 30 + 20)}ms
          </span>
        </div>
      </div>
    </motion.div>
  );
}
