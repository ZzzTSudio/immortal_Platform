import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, User, Type, Globe, Key, TestTube, Wifi, Upload, Check, AlertCircle,
  Cpu, LogOut, Mail
} from 'lucide-react';
import { useStore } from '@/store/useStore';
import * as api from '@/lib/api';

export default function SettingsPanel() {
  const { state, dispatch } = useStore();
  const { settings, settingsOpen, apiTesting, apiTestResult, webTesting, webTestResult } = state;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [localSettings, setLocalSettings] = useState(settings);
  const [saveLoading, setSaveLoading] = useState(false);

  useEffect(() => {
    if (settingsOpen) {
      setLocalSettings(settings);
    }
  }, [settingsOpen, settings]);

  const handleChange = (key: string, value: string | number | boolean) => {
    setLocalSettings(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setSaveLoading(true);
    try {
      await api.updateSettings({
        api_base: localSettings.apiUrl,
        api_key: localSettings.apiKey,
        model: localSettings.model,
        user_avatar_path: localSettings.avatar,
        chat_font_size: localSettings.fontSize,
        ollama_web_search_url: localSettings.webSearchUrl,
        ollama_web_search_api_key: localSettings.webSearchKey,
      });
      dispatch({ type: 'UPDATE_SETTINGS', payload: localSettings });
      dispatch({ type: 'TOGGLE_SETTINGS' });
    } catch (err: any) {
      alert('保存失败：' + err.message);
    } finally {
      setSaveLoading(false);
    }
  };

  const handleLogout = async () => {
    try {
      await api.logout();
      window.location.href = '/';
    } catch (err: any) {
      alert('退出失败：' + err.message);
    }
  };

  const handleTestAPI = async () => {
    dispatch({ type: 'SET_API_TESTING', payload: true });
    dispatch({ type: 'SET_API_TEST_RESULT', payload: null });
    try {
      const res = await api.testApi(localSettings.apiUrl, localSettings.apiKey, localSettings.model);
      dispatch({ type: 'SET_API_TEST_RESULT', payload: res.success ? 'success' : 'error' });
    } catch (err: any) {
      dispatch({ type: 'SET_API_TEST_RESULT', payload: 'error' });
    } finally {
      dispatch({ type: 'SET_API_TESTING', payload: false });
    }
  };

  const handleTestWebSearch = async () => {
    dispatch({ type: 'SET_WEB_TESTING', payload: true });
    dispatch({ type: 'SET_WEB_TEST_RESULT', payload: null });
    try {
      const res = await api.testWebSearch(localSettings.webSearchUrl, localSettings.webSearchKey);
      dispatch({ type: 'SET_WEB_TEST_RESULT', payload: res.success ? 'success' : 'error' });
    } catch (err: any) {
      dispatch({ type: 'SET_WEB_TEST_RESULT', payload: 'error' });
    } finally {
      dispatch({ type: 'SET_WEB_TESTING', payload: false });
    }
  };

  const handleAvatarUpload = () => {
    fileInputRef.current?.click();
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      if (file.size > 2 * 1024 * 1024) {
        alert('头像文件不能超过 2MB');
        return;
      }
      const reader = new FileReader();
      reader.onload = (ev) => {
        const result = ev.target?.result as string;
        handleChange('avatar', result);
      };
      reader.readAsDataURL(file);
    }
  };

  if (!settingsOpen) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center"
        onClick={() => dispatch({ type: 'TOGGLE_SETTINGS' })}
      >
        <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
        <motion.div
          initial={{ opacity: 0, y: 20, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 20, scale: 0.95 }}
          transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
          className="relative max-h-[85vh] overflow-y-auto scrollbar-hide bg-[#1E1E1E] border border-[rgba(255,255,255,0.08)] rounded"
          style={{ width: 1000, minWidth: 1000, maxWidth: 1000 }}
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-6 py-4 border-b border-[rgba(255,255,255,0.08)]">
            <h2 className="text-[15px] font-medium text-white font-serif-cn">系统设置</h2>
            <button
              onClick={() => dispatch({ type: 'TOGGLE_SETTINGS' })}
              className="p-1.5 rounded hover:bg-[rgba(255,255,255,0.06)] transition-colors"
            >
              <X size={16} className="text-[#8B8B8B]" />
            </button>
          </div>

          <div className="p-6 space-y-6">
            {/* User Info Section */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-[13px] text-[#8B8B8B] uppercase tracking-wider">
                <Mail size={13} />
                <span>账号信息</span>
              </div>
              <div className="flex items-center justify-between px-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded">
                <span className="text-[13px] text-white">{settings.userEmail}</span>
                <button
                  onClick={handleLogout}
                  className="flex items-center gap-2 px-3 py-1.5 text-[13px] text-red-400 border border-red-400/30 rounded hover:bg-red-400/10 transition-colors"
                >
                  <LogOut size={13} />
                  退出登录
                </button>
              </div>
            </div>

            {/* Avatar Section */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-[13px] text-[#8B8B8B] uppercase tracking-wider">
                <User size={13} />
                <span>头像设置</span>
              </div>
              <div className="flex items-center gap-4">
                <div
                  className="w-14 h-14 rounded-full overflow-hidden bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)] cursor-pointer hover:border-[#E8D5B5]/40 transition-colors flex items-center justify-center"
                  onClick={handleAvatarUpload}
                >
                  {localSettings.avatar ? (
                    <img src={localSettings.avatar} alt="avatar" className="w-full h-full object-cover" />
                  ) : (
                    <User size={22} className="text-[#4D4D4D]" />
                  )}
                </div>
                <button
                  onClick={handleAvatarUpload}
                  className="flex items-center gap-2 px-3 py-1.5 text-[13px] text-[#E8D5B5] border border-[rgba(232,213,181,0.3)] rounded hover:bg-[rgba(232,213,181,0.08)] transition-colors"
                >
                  <Upload size={13} />
                  上传头像
                </button>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  className="hidden"
                  onChange={handleFileChange}
                />
              </div>
            </div>

            {/* Font Size */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-[13px] text-[#8B8B8B] uppercase tracking-wider">
                <Type size={13} />
                <span>聊天字号</span>
              </div>
              <div className="flex items-center gap-3">
                <input
                  type="range"
                  min={12}
                  max={20}
                  value={localSettings.fontSize}
                  onChange={(e) => handleChange('fontSize', Number(e.target.value))}
                  className="flex-1 h-1 bg-[#2A2A2A] rounded-full appearance-none cursor-pointer accent-[#E8D5B5]"
                />
                <span className="text-[13px] text-white w-8 text-right">{localSettings.fontSize}px</span>
              </div>
              <div className="text-[12px] text-[#4D4D4D]">
                <span style={{ fontSize: localSettings.fontSize }}>预览文本 - 这是聊天消息的显示效果</span>
              </div>
            </div>

            {/* API Configuration */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-[13px] text-[#8B8B8B] uppercase tracking-wider">
                <Globe size={13} />
                <span>API 配置</span>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-[12px] text-[#8B8B8B] mb-1.5">API 地址</label>
                  <input
                    type="text"
                    value={localSettings.apiUrl}
                    onChange={(e) => handleChange('apiUrl', e.target.value)}
                    className="w-full px-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                <div>
                  <label className="block text-[12px] text-[#8B8B8B] mb-1.5">API 密钥</label>
                  <div className="relative">
                    <Key size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4D4D4D]" />
                    <input
                      type="password"
                      value={localSettings.apiKey}
                      onChange={(e) => handleChange('apiKey', e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
                      placeholder="sk-..."
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[12px] text-[#8B8B8B] mb-1.5">模型</label>
                  <div className="relative">
                    <Cpu size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[#4D4D4D]" />
                    <input
                      type="text"
                      value={localSettings.model}
                      onChange={(e) => handleChange('model', e.target.value)}
                      className="w-full pl-9 pr-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
                      placeholder="Pro/moonshotai/Kimi-K2.5"
                    />
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleTestAPI}
                    disabled={apiTesting}
                    className="flex items-center gap-2 px-4 py-2 bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white hover:bg-[#333333] transition-colors disabled:opacity-50"
                  >
                    <TestTube size={14} />
                    {apiTesting ? '测试中...' : '测试连接'}
                  </button>
                  {apiTestResult === 'success' && (
                    <span className="flex items-center gap-1 text-[12px] text-green-400">
                      <Check size={13} /> 连接成功
                    </span>
                  )}
                  {apiTestResult === 'error' && (
                    <span className="flex items-center gap-1 text-[12px] text-red-400">
                      <AlertCircle size={13} /> 连接失败
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Web Search Configuration */}
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-[13px] text-[#8B8B8B] uppercase tracking-wider">
                <Wifi size={13} />
                <span>联网功能配置</span>
              </div>
              <div className="space-y-3">
                <div>
                  <label className="block text-[12px] text-[#8B8B8B] mb-1.5">联网服务地址</label>
                  <input
                    type="text"
                    value={localSettings.webSearchUrl}
                    onChange={(e) => handleChange('webSearchUrl', e.target.value)}
                    className="w-full px-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
                    placeholder="https://search.example.com/api"
                  />
                </div>
                <div>
                  <label className="block text-[12px] text-[#8B8B8B] mb-1.5">联网服务密钥</label>
                  <input
                    type="password"
                    value={localSettings.webSearchKey}
                    onChange={(e) => handleChange('webSearchKey', e.target.value)}
                    className="w-full px-3 py-2 bg-[#111111] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white placeholder-[#4D4D4D] focus:border-[#E8D5B5]/40 focus:outline-none transition-colors"
                    placeholder="输入联网服务密钥"
                  />
                </div>
                <div className="flex items-center gap-3">
                  <button
                    onClick={handleTestWebSearch}
                    disabled={webTesting}
                    className="flex items-center gap-2 px-4 py-2 bg-[#2A2A2A] border border-[rgba(255,255,255,0.08)] rounded text-[13px] text-white hover:bg-[#333333] transition-colors disabled:opacity-50"
                  >
                    <TestTube size={14} />
                    {webTesting ? '测试中...' : '测试链接'}
                  </button>
                  {webTestResult === 'success' && (
                    <span className="flex items-center gap-1 text-[12px] text-green-400">
                      <Check size={13} /> 连接成功
                    </span>
                  )}
                  {webTestResult === 'error' && (
                    <span className="flex items-center gap-1 text-[12px] text-red-400">
                      <AlertCircle size={13} /> 连接失败
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="flex items-center justify-end gap-3 px-6 py-4 border-t border-[rgba(255,255,255,0.08)]">
            <button
              onClick={() => {
                setLocalSettings(settings);
                dispatch({ type: 'TOGGLE_SETTINGS' });
              }}
              className="px-4 py-2 text-[13px] text-[#8B8B8B] hover:text-white transition-colors"
            >
              取消
            </button>
            <button
              onClick={handleSave}
              disabled={saveLoading}
              className="px-5 py-2 bg-[#E8D5B5] text-[#111111] text-[13px] font-medium rounded hover:bg-[#d9c9a8] transition-colors disabled:opacity-50"
            >
              {saveLoading ? '保存中...' : '保存设置'}
            </button>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
