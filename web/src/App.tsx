import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { PanelLeft } from 'lucide-react';
import { StoreProvider, useStore } from '@/store/useStore';
import LiquidChromeBackground from '@/components/LiquidChromeBackground';
import LeftSidebar from '@/components/LeftSidebar';
import ChatArea from '@/components/ChatArea';
import SettingsPanel from '@/components/SettingsPanel';
import AdminPanel from '@/components/AdminPanel';
import Login from '@/pages/Login';
import * as api from '@/lib/api';

function AppContent() {
  const { state, dispatch } = useStore();
  const { leftPanelCollapsed } = state;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        dispatch({ type: 'TOGGLE_LEFT_PANEL' });
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [dispatch]);

  return (
    <div className="relative w-screen h-screen overflow-hidden bg-[#111111]">
      <LiquidChromeBackground />

      <div className="relative z-10 flex h-full">
        {/* Left Panel */}
        <AnimatePresence>
          {!leftPanelCollapsed && (
            <motion.div
              initial={{ width: 0, opacity: 0 }}
              animate={{ width: 320, opacity: 1 }}
              exit={{ width: 0, opacity: 0 }}
              transition={{ duration: 0.4, ease: [0.25, 1, 0.5, 1] }}
              className="h-full flex-shrink-0"
            >
              <LeftSidebar />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Collapse Toggle - Left */}
        {leftPanelCollapsed && (
          <motion.button
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            onClick={() => dispatch({ type: 'TOGGLE_LEFT_PANEL' })}
            className="absolute left-0 top-1/2 -translate-y-1/2 z-20 p-2 bg-[#1E1E1E] border border-[rgba(255,255,255,0.08)] rounded-r hover:bg-[#2A2A2A] transition-colors"
          >
            <PanelLeft size={14} className="text-[#8B8B8B]" />
          </motion.button>
        )}

        {/* Center Chat Area */}
        <div className="flex-1 min-w-0">
          <ChatArea />
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsPanel />

      {/* Admin Panel Modal */}
      <AdminPanel />
    </div>
  );
}

export default function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getCurrentUser()
      .then(u => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
        <div className="text-white">加载中...</div>
      </div>
    );
  }

  if (!user) {
    return <Login onLoginSuccess={setUser} />;
  }

  return (
    <StoreProvider>
      <AppContent />
    </StoreProvider>
  );
}
