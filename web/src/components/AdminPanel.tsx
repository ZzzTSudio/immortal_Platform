import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Users, Mail, Lock, Image, Trash2, Save, X, Database, UploadCloud, FileText } from 'lucide-react';
import { useStore } from '@/store/useStore';
import * as api from '@/lib/api';

interface User {
  id: number;
  email: string;
  avatar: string;
  is_admin: boolean;
  created_at: string;
}

export default function AdminPanel() {
  const { state, dispatch } = useStore();
  const { adminPanelOpen, colleagues, currentSessionId, sessions } = state;
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingUser, setEditingUser] = useState<number | null>(null);
  const [editForm, setEditForm] = useState({ email: '', password: '', avatar: '' });
  const [ragSkillId, setRagSkillId] = useState('');
  const [ragTag, setRagTag] = useState('api_doc');
  const [ragFiles, setRagFiles] = useState<File[]>([]);
  const [ragUploading, setRagUploading] = useState(false);
  const [ragMessage, setRagMessage] = useState('');
  const [ragStats, setRagStats] = useState<api.RagStats | null>(null);
  const [ragStatsLoading, setRagStatsLoading] = useState(false);
  const [ragDeletingDocId, setRagDeletingDocId] = useState<string | null>(null);
  const [chunkDialogDoc, setChunkDialogDoc] = useState<api.RagDocument | null>(null);
  const [chunkDialogChunks, setChunkDialogChunks] = useState<api.RagDocumentChunk[]>([]);
  const [chunkDialogLoading, setChunkDialogLoading] = useState(false);

  useEffect(() => {
    if (adminPanelOpen) {
      loadUsers();
      loadRagStats();
      const currentSkillId = sessions.find(s => s.id === currentSessionId)?.skillId;
      setRagSkillId(currentSkillId || colleagues[0]?.colleague_id || '');
    }
  }, [adminPanelOpen, colleagues, currentSessionId, sessions]);

  const loadUsers = async () => {
    try {
      const res = await api.getAdminUsers();
      setUsers(res.users || []);
    } catch (err) {
      console.error('Failed to load users', err);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (user: User) => {
    setEditingUser(user.id);
    setEditForm({ email: user.email, password: '', avatar: user.avatar });
  };

  const handleSave = async (userId: number) => {
    try {
      const data: any = {};
      if (editForm.email) data.email = editForm.email;
      if (editForm.password) data.password = editForm.password;
      if (editForm.avatar !== undefined) data.avatar = editForm.avatar;
      await api.updateAdminUser(userId, data);
      await loadUsers();
      setEditingUser(null);
    } catch (err: any) {
      alert('更新失败：' + err.message);
    }
  };

  const handleDelete = async (userId: number) => {
    if (!confirm('确定要删除该用户吗？')) return;
    try {
      await api.deleteAdminUser(userId);
      await loadUsers();
    } catch (err: any) {
      alert('删除失败：' + err.message);
    }
  };

  const loadRagStats = async () => {
    setRagStatsLoading(true);
    try {
      const stats = await api.getRagStats();
      setRagStats(stats);
    } catch (err) {
      console.error('Failed to load RAG stats', err);
      setRagStats(null);
    } finally {
      setRagStatsLoading(false);
    }
  };

  const displayNameForSkill = (skillId: string) => {
    const c = colleagues.find(item => item.colleague_id === skillId);
    return c ? c.display_name : skillId;
  };

  const handleDeleteRagDocument = async (doc: api.RagDocument) => {
    const label = doc.filename || doc.doc_id;
    if (!confirm(`确定删除「${label}」对应的 ${doc.chunk_count} 个向量片段吗？删除后该 Skill 将不再检索这份文档。`)) return;
    setRagDeletingDocId(doc.doc_id);
    setRagMessage(`正在删除 ${label}...`);
    try {
      await api.deleteRagDocument(doc.skill_id, doc.doc_id);
      setRagMessage(`已删除：${label}`);
      await loadRagStats();
    } catch (err: any) {
      setRagMessage(`删除失败：${err.message || err}`);
    } finally {
      setRagDeletingDocId(null);
    }
  };

  const handleOpenDocumentChunks = async (doc: api.RagDocument) => {
    setChunkDialogDoc(doc);
    setChunkDialogChunks([]);
    setChunkDialogLoading(true);
    try {
      const result = await api.getRagDocumentChunks(doc.skill_id, doc.doc_id);
      setChunkDialogChunks(result.chunks || []);
    } catch (err: any) {
      setRagMessage(`读取分块失败：${err.message || err}`);
      setChunkDialogDoc(null);
    } finally {
      setChunkDialogLoading(false);
    }
  };

  const handleRagUpload = async () => {
    if (!ragSkillId) {
      setRagMessage('请先选择目标 Skill');
      return;
    }
    if (ragFiles.length === 0) {
      setRagMessage('请先选择要导入的文档');
      return;
    }
    setRagUploading(true);
    setRagMessage('正在清洗、切片并写入本地向量库...');
    try {
      const result = await api.uploadRagDocuments({
        targetSkillId: ragSkillId,
        files: ragFiles,
        tag: ragTag,
      });
      const fileSummary = result.files.map(f => `${f.filename}: ${f.chunks} chunks`).join('；');
      setRagFiles([]);
      setRagMessage(`导入成功：共 ${result.total_chunks} 个 chunks。${fileSummary}`);
      await loadRagStats();
    } catch (err: any) {
      setRagMessage(`导入失败：${err.message || err}`);
    } finally {
      setRagUploading(false);
    }
  };

  if (!adminPanelOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
        onClick={() => dispatch({ type: 'TOGGLE_ADMIN_PANEL' })}
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
          className="relative w-full max-w-6xl max-h-[80vh] overflow-hidden bg-[#1E1E1E] border border-[rgba(255,255,255,0.08)] rounded-lg flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.08)]">
            <div className="flex items-center gap-3">
              <Users size={20} className="text-[#E8D5B5]" />
              <h2 className="text-[18px] font-medium text-white">管理员后台</h2>
            </div>
            <button onClick={() => dispatch({ type: 'TOGGLE_ADMIN_PANEL' })} className="p-2 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors">
              <X size={20} className="text-[#8B8B8B]" />
            </button>
          </div>
        <div className="flex-1 overflow-y-auto scrollbar-hide p-6">
          {loading ? <div className="text-center text-[#8B8B8B] py-8">加载中...</div> : (
            <div className="space-y-5">
              <div className="bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Database size={18} className="text-[#E8D5B5]" />
                      <h3 className="text-[15px] font-medium text-white">RAG 知识库导入</h3>
                    </div>
                    <p className="mt-1 text-[12px] text-[#8B8B8B]">
                      文档会写入当前选择的 Skill 私有知识库，之后该 Skill 聊天时会自动检索。
                    </p>
                  </div>
                  <span className="rounded-full border border-[#E8D5B5]/25 px-2.5 py-1 text-[10px] text-[#E8D5B5]">
                    pdf / docx / md / txt
                  </span>
                </div>

                <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-[1fr_160px]">
                  <label className="space-y-1">
                    <span className="text-[11px] text-[#6F6F6F]">目标 Skill</span>
                    <select
                      value={ragSkillId}
                      onChange={(e) => setRagSkillId(e.target.value)}
                      className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-[rgba(255,255,255,0.08)] rounded-lg text-[13px] text-white outline-none focus:border-[#E8D5B5]/50"
                    >
                      {colleagues.map((c) => (
                        <option key={c.colleague_id} value={c.colleague_id}>
                          {c.display_name} ({c.colleague_id})
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1">
                    <span className="text-[11px] text-[#6F6F6F]">标签</span>
                    <input
                      value={ragTag}
                      onChange={(e) => setRagTag(e.target.value)}
                      className="w-full px-3 py-2.5 bg-[#0A0A0A] border border-[rgba(255,255,255,0.08)] rounded-lg text-[13px] text-white outline-none focus:border-[#E8D5B5]/50"
                      placeholder="api_doc"
                    />
                  </label>
                </div>

                <div className="mt-3 flex flex-col gap-3 rounded-lg border border-dashed border-[rgba(255,255,255,0.14)] bg-[#0A0A0A]/70 p-4">
                  <label className="flex cursor-pointer items-center justify-between gap-4">
                    <div className="flex items-center gap-3">
                      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[#E8D5B5]/10">
                        <UploadCloud size={18} className="text-[#E8D5B5]" />
                      </div>
                      <div>
                        <div className="text-[13px] text-white">选择知识库文档</div>
                        <div className="text-[11px] text-[#6F6F6F]">支持多文件，上传后会自动清洗、切片、向量化</div>
                      </div>
                    </div>
                    <span className="rounded bg-[#2A2A2A] px-3 py-1.5 text-[12px] text-[#D6D6D6]">浏览文件</span>
                    <input
                      type="file"
                      multiple
                      accept=".pdf,.docx,.md,.txt"
                      className="hidden"
                      onChange={(e) => setRagFiles(Array.from(e.target.files || []))}
                    />
                  </label>

                  {ragFiles.length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {ragFiles.map((file) => (
                        <span key={`${file.name}-${file.size}`} className="inline-flex items-center gap-1.5 rounded-full bg-[#1E1E1E] px-2.5 py-1 text-[11px] text-[#CFCFCF]">
                          <FileText size={12} className="text-[#8B8B8B]" />
                          {file.name}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between gap-3">
                    <div className="min-h-5 text-[12px] text-[#8B8B8B]">{ragMessage}</div>
                    <button
                      onClick={handleRagUpload}
                      disabled={ragUploading || !ragSkillId || ragFiles.length === 0}
                      className="shrink-0 rounded-lg bg-[#E8D5B5] px-4 py-2 text-[12px] font-medium text-[#111111] transition-colors hover:bg-[#d9c9a8] disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      {ragUploading ? '导入中...' : '导入 RAG'}
                    </button>
                  </div>
                </div>
              </div>

              <div className="bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Database size={18} className="text-[#E8D5B5]" />
                      <h3 className="text-[15px] font-medium text-white">向量库管理</h3>
                    </div>
                    <p className="mt-1 text-[12px] text-[#8B8B8B]">
                      查看每个 Skill 已导入的文档和 chunks，也可以删除某份文档对应的向量内容。
                    </p>
                  </div>
                  <button
                    onClick={loadRagStats}
                    disabled={ragStatsLoading}
                    className="rounded bg-[#2A2A2A] px-3 py-1.5 text-[12px] text-[#D6D6D6] transition-colors hover:text-white disabled:opacity-50"
                  >
                    {ragStatsLoading ? '刷新中...' : '刷新'}
                  </button>
                </div>

                <div className="mt-4 grid grid-cols-3 gap-3">
                  <div className="rounded-lg bg-[#0A0A0A] border border-[rgba(255,255,255,0.06)] p-3">
                    <div className="text-[11px] text-[#6F6F6F]">Collection</div>
                    <div className="mt-1 truncate text-[13px] text-white">{ragStats?.collection || '-'}</div>
                  </div>
                  <div className="rounded-lg bg-[#0A0A0A] border border-[rgba(255,255,255,0.06)] p-3">
                    <div className="text-[11px] text-[#6F6F6F]">文档数</div>
                    <div className="mt-1 text-[18px] text-white">{ragStats?.total_documents ?? 0}</div>
                  </div>
                  <div className="rounded-lg bg-[#0A0A0A] border border-[rgba(255,255,255,0.06)] p-3">
                    <div className="text-[11px] text-[#6F6F6F]">Chunks</div>
                    <div className="mt-1 text-[18px] text-white">{ragStats?.total_chunks ?? 0}</div>
                  </div>
                </div>

                <div className="mt-4 space-y-3">
                  {ragStatsLoading && !ragStats ? (
                    <div className="rounded-lg bg-[#0A0A0A] p-4 text-center text-[12px] text-[#8B8B8B]">正在加载向量库统计...</div>
                  ) : !ragStats || ragStats.skills.length === 0 ? (
                    <div className="rounded-lg bg-[#0A0A0A] p-4 text-center text-[12px] text-[#8B8B8B]">还没有导入任何 RAG 文档</div>
                  ) : (
                    ragStats.skills.map((skill) => (
                      <div key={skill.skill_id} className="rounded-lg bg-[#0A0A0A] border border-[rgba(255,255,255,0.06)] p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div>
                            <div className="text-[13px] text-white">{displayNameForSkill(skill.skill_id)}</div>
                            <div className="text-[11px] text-[#6F6F6F]">{skill.skill_id}</div>
                          </div>
                          <div className="text-right text-[11px] text-[#8B8B8B]">
                            {skill.doc_count} docs / {skill.chunk_count} chunks
                          </div>
                        </div>
                        <div className="mt-3 space-y-2">
                          {skill.documents.map((doc) => (
                            <div key={`${doc.skill_id}-${doc.doc_id}`} className="flex items-center justify-between gap-3 rounded-md bg-[#151515] px-3 py-2">
                              <button
                                onClick={() => handleOpenDocumentChunks(doc)}
                                className="min-w-0 flex-1 text-left"
                                title="查看该文档向量化前的所有分块内容"
                              >
                                <div className="truncate text-[12px] text-[#EDEDED] hover:text-[#E8D5B5] transition-colors">{doc.filename || doc.doc_id}</div>
                                <div className="mt-0.5 text-[10px] text-[#6F6F6F]">
                                  {doc.source_type || 'unknown'} · {doc.tag || 'untagged'} · {doc.chunk_count} chunks · {doc.doc_id}
                                </div>
                              </button>
                              <button
                                onClick={() => handleDeleteRagDocument(doc)}
                                disabled={ragDeletingDocId === doc.doc_id}
                                className="shrink-0 rounded px-2 py-1 text-[11px] text-red-300 transition-colors hover:bg-red-500/10 disabled:opacity-50"
                              >
                                {ragDeletingDocId === doc.doc_id ? '删除中...' : '删除'}
                              </button>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              <div className="bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded-xl p-5">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2">
                      <Users size={18} className="text-[#E8D5B5]" />
                      <h3 className="text-[15px] font-medium text-white">用户管理</h3>
                    </div>
                    <p className="mt-1 text-[12px] text-[#8B8B8B]">
                      管理登录用户、头像、密码和管理员账号以外的用户删除操作。
                    </p>
                  </div>
                  <span className="rounded-full border border-[#E8D5B5]/25 px-2.5 py-1 text-[10px] text-[#E8D5B5]">
                    {users.length} users
                  </span>
                </div>

                <div className="mt-4 space-y-3">
                  {users.map((user) => (
                    <div key={user.id} className="rounded-lg bg-[#0A0A0A] border border-[rgba(255,255,255,0.06)] p-4">
                      {editingUser === user.id ? (
                        <div className="space-y-3">
                          <div className="flex items-center gap-2">
                            <Mail size={16} className="text-[#4D4D4D]" />
                            <input type="email" value={editForm.email} onChange={(e) => setEditForm({ ...editForm, email: e.target.value })} className="flex-1 px-3 py-2 bg-[#151515] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white" placeholder="邮箱" />
                          </div>
                          <div className="flex items-center gap-2">
                            <Lock size={16} className="text-[#4D4D4D]" />
                            <input type="password" value={editForm.password} onChange={(e) => setEditForm({ ...editForm, password: e.target.value })} className="flex-1 px-3 py-2 bg-[#151515] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white" placeholder="新密码（留空不修改）" />
                          </div>
                          <div className="flex items-center gap-2">
                            <Image size={16} className="text-[#4D4D4D]" />
                            <input type="text" value={editForm.avatar} onChange={(e) => setEditForm({ ...editForm, avatar: e.target.value })} className="flex-1 px-3 py-2 bg-[#151515] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white" placeholder="头像URL" />
                          </div>
                          <div className="flex gap-2">
                            <button onClick={() => handleSave(user.id)} className="flex items-center gap-1.5 px-3 py-2 bg-[#E8D5B5] text-[#111111] rounded text-[12px] hover:bg-[#d9c9a8] transition-colors"><Save size={14} />保存</button>
                            <button onClick={() => setEditingUser(null)} className="flex items-center gap-1.5 px-3 py-2 bg-[#2A2A2A] text-[#8B8B8B] rounded text-[12px] hover:text-white transition-colors"><X size={14} />取消</button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex items-center justify-between gap-3">
                          <div className="flex min-w-0 items-center gap-4">
                            <div className="w-10 h-10 rounded-full bg-[#2A2A2A] flex items-center justify-center overflow-hidden">{user.avatar ? <img src={user.avatar} alt="avatar" className="w-full h-full object-cover" /> : <Users size={16} className="text-[#8B8B8B]" />}</div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2"><span className="truncate text-[14px] text-white">{user.email}</span>{user.is_admin && <span className="shrink-0 px-2 py-0.5 bg-[#E8D5B5]/20 text-[#E8D5B5] rounded text-[10px]">管理员</span>}</div>
                              <span className="text-[11px] text-[#4D4D4D]">注册时间: {new Date(user.created_at).toLocaleString('zh-CN')}</span>
                            </div>
                          </div>
                          <div className="flex shrink-0 gap-2">
                            <button onClick={() => handleEdit(user)} className="px-3 py-1.5 bg-[#2A2A2A] text-[#8B8B8B] rounded text-[12px] hover:text-white transition-colors">编辑</button>
                            {!user.is_admin && <button onClick={() => handleDelete(user.id)} className="p-1.5 rounded hover:bg-[rgba(239,68,68,0.1)] transition-colors"><Trash2 size={14} className="text-red-400" /></button>}
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>

        {chunkDialogDoc && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="w-[min(860px,calc(100vw-64px))] max-h-[74vh] overflow-hidden rounded-xl border border-[rgba(255,255,255,0.1)] bg-[#141414] shadow-2xl">
              <div className="flex items-start justify-between gap-4 border-b border-[rgba(255,255,255,0.08)] px-5 py-4">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 text-[14px] text-white">
                    <FileText size={16} className="text-[#E8D5B5]" />
                    <span className="truncate">{chunkDialogDoc.filename || chunkDialogDoc.doc_id}</span>
                  </div>
                  <div className="mt-1 text-[11px] text-[#6F6F6F]">
                    {chunkDialogDoc.source_type} · {chunkDialogDoc.tag || 'untagged'} · {chunkDialogDoc.chunk_count} chunks · {chunkDialogDoc.doc_id}
                  </div>
                </div>
                <button
                  onClick={() => setChunkDialogDoc(null)}
                  className="rounded p-1.5 text-[#8B8B8B] transition-colors hover:bg-[rgba(255,255,255,0.06)] hover:text-white"
                >
                  <X size={18} />
                </button>
              </div>

              <div className="max-h-[58vh] overflow-y-auto scrollbar-hide p-5 space-y-3">
                {chunkDialogLoading ? (
                  <div className="rounded-lg bg-[#0A0A0A] p-6 text-center text-[12px] text-[#8B8B8B]">正在读取分块内容...</div>
                ) : (
                  chunkDialogChunks.map((chunk, index) => (
                    <div key={chunk.chunk_id} className="rounded-lg border border-[rgba(255,255,255,0.08)] bg-[#0A0A0A] p-3">
                      <div className="mb-2 flex items-center justify-between gap-3 text-[11px] text-[#6F6F6F]">
                        <span>Chunk {index + 1}</span>
                        <span className="truncate">{chunk.chunk_id}</span>
                      </div>
                      <pre className="whitespace-pre-wrap break-words text-[12px] leading-6 text-[#D8D8D8] font-sans">
                        {chunk.content}
                      </pre>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </motion.div>
    </motion.div>
    </AnimatePresence>
  );
}
