import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { Loader2, Plus, X } from 'lucide-react';
import { useStore } from '@/store/useStore';
import type { PlatformSkill } from '@/types';
import * as api from '@/lib/api';

interface DigitalHumanPlatformModalProps {
  open: boolean;
  onClose: () => void;
}

export default function DigitalHumanPlatformModal({ open, onClose }: DigitalHumanPlatformModalProps) {
  const { state, dispatch } = useStore();
  const { colleagues } = state;
  const [skills, setSkills] = useState<PlatformSkill[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [importingId, setImportingId] = useState<string | null>(null);

  const importedIds = useMemo(
    () => new Set(colleagues.map((item) => item.colleague_id)),
    [colleagues]
  );

  useEffect(() => {
    if (!open) return;

    let cancelled = false;
    async function loadPlatformSkills() {
      setLoading(true);
      setError('');
      try {
        const res = await api.getPlatformSkills();
        if (!cancelled) {
          setSkills(res.skills || []);
        }
      } catch (err: any) {
        if (!cancelled) {
          setError(`读取数字人平台失败：${err.message || err}`);
          setSkills([]);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadPlatformSkills();
    return () => {
      cancelled = true;
    };
  }, [open]);

  const handleImport = async (skill: PlatformSkill) => {
    if (importedIds.has(skill.colleague_id) || importingId) return;

    setImportingId(skill.colleague_id);
    setError('');
    try {
      const res = await api.importPlatformSkill(skill.colleague_id);
      const skillsRes = await api.getSkills();
      dispatch({ type: 'SET_COLLEAGUES', payload: skillsRes.colleagues || [] });
      dispatch({ type: 'SELECT_COLLEAGUE', payload: res.colleague_id });
      setSkills((prev) => prev.map((item) => (
        item.colleague_id === skill.colleague_id ? { ...item, imported: true } : item
      )));
    } catch (err: any) {
      setError(`导入失败：${err.message || err}`);
    } finally {
      setImportingId(null);
    }
  };

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
        onClick={onClose}
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
          className="relative w-[min(860px,calc(100vw-48px))] max-h-[82vh] overflow-hidden rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#1E1E1E] shadow-2xl"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.08)] px-6 py-4">
            <div>
              <h2 className="text-[16px] font-medium text-white">数字人平台</h2>
              <p className="mt-1 text-[12px] text-[#8B8B8B]">从服务端仓库导入数字人到当前会话</p>
            </div>
            <button
              onClick={onClose}
              className="rounded p-1.5 text-[#8B8B8B] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
            >
              <X size={18} />
            </button>
          </div>

          <div className="max-h-[calc(82vh-76px)] overflow-y-auto p-6 scrollbar-hide">
            {error && (
              <div className="mb-4 rounded-lg border border-red-400/20 bg-red-400/10 px-3 py-2 text-[12px] text-red-200">
                {error}
              </div>
            )}

            {loading ? (
              <div className="flex items-center justify-center gap-2 py-16 text-[13px] text-[#8B8B8B]">
                <Loader2 size={16} className="animate-spin" />
                正在加载数字人平台...
              </div>
            ) : skills.length === 0 ? (
              <div className="rounded-lg bg-[#111111] p-10 text-center text-[13px] text-[#8B8B8B]">
                暂无可导入的数字人
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                {skills.map((skill) => {
                  const imported = skill.imported || importedIds.has(skill.colleague_id);
                  const importing = importingId === skill.colleague_id;
                  return (
                    <div
                      key={skill.colleague_id}
                      className="relative flex min-w-0 gap-3 rounded-xl border border-[rgba(255,255,255,0.08)] bg-[#111111] p-4 transition-colors hover:border-[#E8D5B5]/30"
                    >
                      <div className="h-14 w-14 shrink-0 overflow-hidden rounded-full border border-[rgba(255,255,255,0.08)] bg-[#2A2A2A]">
                        <img
                          src={skill.avatar_url}
                          alt={skill.display_name}
                          className="h-full w-full object-cover"
                          onError={(e) => { (e.target as HTMLImageElement).src = '/static/pic/icon_default.png'; }}
                        />
                      </div>
                      <div className="min-w-0 flex-1 pr-9">
                        <div className="truncate text-[14px] font-medium text-white">{skill.display_name}</div>
                        <div className="mt-1 truncate text-[12px] text-[#8B8B8B]">
                          {skill.intro_summary}
                        </div>
                      </div>
                      <button
                        onClick={() => handleImport(skill)}
                        disabled={imported || Boolean(importingId)}
                        className="absolute right-3 top-3 flex h-7 w-7 items-center justify-center rounded-full border border-[#E8D5B5]/30 text-[#E8D5B5] transition-colors hover:bg-[#E8D5B5]/10 disabled:cursor-not-allowed disabled:border-[rgba(255,255,255,0.08)] disabled:text-[#4D4D4D]"
                        title={imported ? '已导入' : '导入数字人'}
                      >
                        {importing ? <Loader2 size={14} className="animate-spin" /> : <Plus size={15} />}
                      </button>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
