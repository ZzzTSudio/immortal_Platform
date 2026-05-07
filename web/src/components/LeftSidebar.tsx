import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Plus, Settings, ChevronRight, Trash2, ChevronDown, ChevronUp, Search, ChevronLeft, Shield
} from 'lucide-react';
import { useStore } from '@/store/useStore';
import * as api from '@/lib/api';
import DigitalHumanPlatformModal from './DigitalHumanPlatformModal';

export default function LeftSidebar() {
  const { state, dispatch } = useStore();
  const { colleagues, sessions, currentSessionId, settings, leftPanelCollapsed } = state;
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedCategories, setExpandedCategories] = useState<Record<string, boolean>>({});
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState('');
  const [currentUser, setCurrentUser] = useState<any>(null);
  const [platformOpen, setPlatformOpen] = useState(false);

  useEffect(() => {
    api.getCurrentUser().then(user => setCurrentUser(user)).catch(() => {});
  }, []);

  const toggleCategory = (cat: string) => {
    setExpandedCategories(prev => ({ ...prev, [cat]: !prev[cat] }));
  };

  const handleDelete = async (colleagueId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const c = colleagues.find(x => x.colleague_id === colleagueId);
    if (!c || c.is_builtin) return;
    if (!confirm(`确定要移除「${c.display_name}」吗？`)) return;
    try {
      await api.deleteSkill(colleagueId);
      dispatch({ type: 'REMOVE_COLLEAGUE', payload: colleagueId });
    } catch (err: any) {
      alert('移除失败：' + err.message);
    }
  };

  const handleRename = async (colleagueId: string) => {
    const name = renameValue.trim();
    if (!name) {
      setRenamingId(null);
      return;
    }
    try {
      await api.renameSkill(colleagueId, name);
      dispatch({ type: 'RENAME_COLLEAGUE', payload: { colleagueId, name } });
      setRenamingId(null);
    } catch (err: any) {
      alert('重命名失败：' + err.message);
    }
  };

  const handleImport = async () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.zip';
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) return;
      try {
        const res = await api.uploadSkill(file);
        if (res.success && res.colleague_id) {
          const skillsRes = await api.getSkills();
          dispatch({ type: 'SET_COLLEAGUES', payload: skillsRes.colleagues || [] });
          dispatch({ type: 'SELECT_COLLEAGUE', payload: res.colleague_id });
        }
      } catch (err: any) {
        alert('导入失败：' + err.message);
      }
    };
    input.click();
  };

  const filteredColleagues = colleagues.filter(c =>
    c.display_name.toLowerCase().includes(searchQuery.trim().toLowerCase())
  );

  // Group by category from meta.json
  const grouped = filteredColleagues.reduce<Record<string, typeof filteredColleagues>>((acc, c) => {
    const cat = c.meta?.category || '数字人';
    if (!acc[cat]) acc[cat] = [];
    acc[cat].push(c);
    return acc;
  }, {});

  // Ensure default expansion
  const allCats = Object.keys(grouped);
  allCats.forEach(cat => {
    if (!(cat in expandedCategories)) {
      expandedCategories[cat] = true;
    }
  });

  if (leftPanelCollapsed) {
    return (
      <motion.div
        initial={{ width: 320 }}
        animate={{ width: 48, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
        className="h-full overflow-hidden border-r border-[rgba(255,255,255,0.08)] bg-[#0A0A0A] flex flex-col items-center py-4"
      >
        <button
          onClick={() => dispatch({ type: 'TOGGLE_LEFT_PANEL' })}
          className="p-2 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors"
          title="展开侧边栏"
        >
          <ChevronRight size={20} className="text-[#8B8B8B]" />
        </button>
      </motion.div>
    );
  }

  return (
    <>
      <motion.div
        initial={{ width: 0, opacity: 0 }}
        animate={{ width: 320, opacity: 1 }}
        transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
        className="h-full panel-surface border-r border-[rgba(255,255,255,0.08)] flex flex-col overflow-hidden"
      >
      {/* Brand */}
      <div className="px-5 pt-6 pb-4">
        <div className="flex items-center gap-3 mb-4">
          <button
            onClick={() => dispatch({ type: 'TOGGLE_LEFT_PANEL' })}
            className="p-1 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors"
            title="收起侧边栏"
          >
            <ChevronLeft size={16} className="text-[#8B8B8B]" />
          </button>
          <img src="/logo.png" alt="Immortal" className="w-8 h-8" />
          <span className="text-[16px] font-medium tracking-wide font-serif-cn" style={{ color: '#E8D5B5' }}>
            IMMORTAL
          </span>
        </div>
        <button
          onClick={handleImport}
          className="w-full flex items-center justify-center gap-2 py-2.5 bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white hover:bg-[#333333] transition-all group relative overflow-hidden"
        >
          <Plus size={15} />
          导入数字人
          <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#E8D5B5] opacity-0 group-hover:opacity-100 transition-opacity" />
        </button>
        <button
          onClick={() => setPlatformOpen(true)}
          className="mt-2 w-full flex items-center justify-center gap-2 py-2.5 bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white hover:bg-[#333333] transition-all group relative overflow-hidden"
        >
          <Plus size={15} />
          数字人平台
          <div className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#E8D5B5] opacity-0 group-hover:opacity-100 transition-opacity" />
        </button>
      </div>

      {/* Search */}
      <div className="px-5 pb-3">
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4D4D4D]" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索同事..."
            className="w-full pl-9 pr-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
          />
        </div>
      </div>

      {/* Colleague List by Category */}
      <div className="flex-1 overflow-y-auto scrollbar-hide px-3">
        {Object.entries(grouped).map(([category, catColleagues]) => (
          <div key={category} className="mb-3">
            <button
              onClick={() => toggleCategory(category)}
              className="flex items-center gap-1.5 w-full px-2 py-2 text-[11px] uppercase tracking-[0.15em] text-[#4D4D4D] hover:text-[#8B8B8B] transition-colors"
            >
              {expandedCategories[category] !== false ? (
                <ChevronDown size={12} />
              ) : (
                <ChevronUp size={12} />
              )}
              {category}
            </button>

            {expandedCategories[category] !== false && (
              <div className="space-y-0.5">
                {catColleagues.map(c => {
                  const session = sessions.find(s => s.skillId === c.colleague_id);
                  const isActive = session?.id === currentSessionId;
                  return (
                    <motion.button
                      key={c.colleague_id}
                      onClick={() => dispatch({ type: 'SELECT_COLLEAGUE', payload: c.colleague_id })}
                      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded text-left group relative transition-all ${
                        isActive
                          ? 'bg-[#2A2A2A]'
                          : 'hover:bg-[rgba(255,255,255,0.03)]'
                      }`}
                      whileTap={{ scale: 0.98 }}
                    >
                      {isActive && (
                        <motion.div
                          layoutId="activeIndicator"
                          className="absolute left-0 top-0 bottom-0 w-[2px] bg-[#E8D5B5]"
                          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                        />
                      )}
                      <div className="w-6 h-6 rounded-full overflow-hidden flex-shrink-0 border border-[rgba(255,255,255,0.08)] relative">
                        <img
                          src={api.getSkillIconUrl(c.colleague_id)}
                          alt={c.display_name}
                          className="w-full h-full object-cover"
                          onError={(e) => { (e.target as HTMLImageElement).src = '/ai-avatar.png'; }}
                        />
                      </div>
                      {renamingId === c.colleague_id ? (
                        <input
                          autoFocus
                          className="flex-1 bg-transparent text-[13px] text-white border border-[rgba(255,255,255,0.2)] rounded px-1 outline-none"
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          onBlur={() => handleRename(c.colleague_id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') handleRename(c.colleague_id);
                            if (e.key === 'Escape') setRenamingId(null);
                          }}
                          onClick={(e) => e.stopPropagation()}
                        />
                      ) : (
                        <span
                          className={`flex-1 text-[13px] truncate ${isActive ? 'text-white' : 'text-[#8B8B8B]'}`}
                          onDoubleClick={() => {
                            if (!c.is_builtin) {
                              setRenamingId(c.colleague_id);
                              setRenameValue(c.display_name);
                            }
                          }}
                          title={c.is_builtin ? '' : '双击修改名称'}
                        >
                          {c.display_name}
                        </span>
                      )}
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                        {!c.is_builtin && (
                          <button
                            onClick={(e) => handleDelete(c.colleague_id, e)}
                            className="p-1 rounded hover:bg-[rgba(255,255,255,0.08)] transition-colors"
                          >
                            <Trash2 size={12} className="text-[#4D4D4D] hover:text-red-400" />
                          </button>
                        )}
                      </div>
                      {isActive && <ChevronRight size={13} className="text-[#E8D5B5]" />}
                    </motion.button>
                  );
                })}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Bottom: Admin Panel & User Settings */}
      {currentUser?.is_admin && (
        <div className="px-4 py-3 border-t border-[rgba(255,255,255,0.08)]">
          <button
            onClick={() => dispatch({ type: 'TOGGLE_ADMIN_PANEL' })}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-full bg-[#2A2A2A] hover:bg-[#333333] transition-colors group"
          >
            <Shield size={14} className="text-[#E8D5B5]" />
            <span className="text-[13px] text-[#8B8B8B] group-hover:text-white transition-colors">
              管理员后台
            </span>
          </button>
        </div>
      )}
      <div className="px-4 py-3 border-t border-[rgba(255,255,255,0.08)]">
        <button
          onClick={() => dispatch({ type: 'TOGGLE_SETTINGS' })}
          className="w-full flex items-center gap-3 px-3 py-2.5 rounded-full bg-[#2A2A2A] hover:bg-[#333333] transition-colors group"
        >
          <div className="w-7 h-7 rounded-full overflow-hidden bg-[#1E1E1E] flex items-center justify-center">
            {settings.avatar ? (
              <img src={settings.avatar} alt="avatar" className="w-full h-full object-cover" />
            ) : (
              <Settings size={14} className="text-[#8B8B8B]" />
            )}
          </div>
          <span className="text-[13px] text-[#8B8B8B] group-hover:text-white transition-colors">
            用户设置
          </span>
        </button>
      </div>
      </motion.div>
      <DigitalHumanPlatformModal open={platformOpen} onClose={() => setPlatformOpen(false)} />
    </>
  );
}
