# 功能实施指南

本文档说明了用户认证系统和相关功能的实施进度和剩余工作。

## 已完成的工作

### 后端 (Python/FastAPI)

1. ✅ **用户数据库模型** (`app/database.py`)
   - 用户表、用户技能关联表
   - 密码哈希、用户CRUD操作
   - 默认管理员账户 (admin/admin2025)

2. ✅ **认证API** (`app/web/routers/auth.py`)
   - POST `/api/auth/register` - 注册（需@fanvil.com邮箱）
   - POST `/api/auth/login` - 登录
   - POST `/api/auth/logout` - 登出
   - GET `/api/auth/me` - 获取当前用户
   - GET `/api/admin/users` - 管理员获取所有用户
   - PUT `/api/admin/users/{id}` - 管理员更新用户
   - DELETE `/api/admin/users/{id}` - 管理员删除用户

3. ✅ **技能上传API** (`app/web/routers/skills.py`)
   - POST `/api/skills/upload` - 上传ZIP格式的skill文件夹
   - GET `/api/skills` - 根据用户过滤skill列表
   - GET `/api/skills/{id}/intro` - 获取skill的intro.md

4. ✅ **主应用集成** (`app/web/main.py`)
   - 已添加auth路由

### 前端 (React/TypeScript)

1. ✅ **登录注册页面** (`web/src/pages/Login.tsx`)
   - 登录/注册切换
   - 表单验证
   - 错误提示

2. ✅ **管理员后台组件** (`web/src/components/AdminPanel.tsx`)
   - 用户列表展示
   - 编辑用户信息
   - 删除用户

3. ✅ **API函数扩展** (`web/src/lib/api.ts`)
   - login, register, logout, getCurrentUser
   - uploadSkill, getAdminUsers, updateAdminUser, deleteAdminUser

4. ✅ **UI优化**
   - EmptyState显示skill图标
   - 左侧栏展开/收起
   - "新会话"改为"清空会话"

## 需要手动完成的工作

### 1. 修改左侧栏导入按钮 (`web/src/components/LeftSidebar.tsx`)

在 `handleImport` 函数中，将原来的 `prompt` 方式改为文件上传：

```typescript
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
```

### 2. 在左侧栏添加管理员后台入口 (`web/src/components/LeftSidebar.tsx`)

在"用户设置"按钮上方添加管理员后台按钮（仅管理员可见）：

```typescript
import { Shield } from 'lucide-react';
import AdminPanel from './AdminPanel';

// 在组件中添加状态
const [showAdminPanel, setShowAdminPanel] = useState(false);
const [currentUser, setCurrentUser] = useState<any>(null);

// 在useEffect中获取当前用户
useEffect(() => {
  api.getCurrentUser().then(user => setCurrentUser(user)).catch(() => {});
}, []);

// 在"用户设置"按钮上方添加
{currentUser?.is_admin && (
  <div className="px-4 py-3 border-t border-[rgba(255,255,255,0.08)]">
    <button
      onClick={() => setShowAdminPanel(true)}
      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-full bg-[#2A2A2A] hover:bg-[#333333] transition-colors group"
    >
      <Shield size={14} className="text-[#E8D5B5]" />
      <span className="text-[13px] text-[#8B8B8B] group-hover:text-white transition-colors">
        管理员后台
      </span>
    </button>
  </div>
)}

// 在组件末尾添加
{showAdminPanel && <AdminPanel onClose={() => setShowAdminPanel(false)} />}
```

### 3. 修改App.tsx集成登录逻辑 (`web/src/App.tsx`)

```typescript
import { useState, useEffect } from 'react';
import Login from './pages/Login';
import Home from './pages/Home';
import * as api from './lib/api';

function App() {
  const [user, setUser] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 检查是否已登录
    api.getCurrentUser()
      .then(u => setUser(u))
      .catch(() => setUser(null))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="min-h-screen bg-[#0A0A0A] flex items-center justify-center">
      <div className="text-white">加载中...</div>
    </div>;
  }

  if (!user) {
    return <Login onLoginSuccess={setUser} />;
  }

  return <Home user={user} onLogout={() => {
    api.logout().then(() => setUser(null));
  }} />;
}

export default App;
```

### 4. 更新store添加用户状态 (`web/src/store/useStore.tsx`)

在 `AppState` 接口中添加：

```typescript
export interface AppState {
  // ... 现有字段
  currentUser: any | null;
}

// 在 initialState 中添加
currentUser: null,

// 在 reducer 中添加
case 'SET_CURRENT_USER':
  return { ...state, currentUser: action.payload };
```

### 5. 初始化数据库

在首次运行后端时，数据库会自动初始化。默认管理员账户：
- 邮箱：admin
- 密码：admin2025

### 6. 测试流程

1. 启动后端：`cd /home/fanvil/Agent_Immortal && python -m app.web`
2. 启动前端：`cd /home/fanvil/Agent_Immortal/web && npm run dev`
3. 访问 http://localhost:5173
4. 使用 admin/admin2025 登录测试管理员功能
5. 注册新用户测试（需@fanvil.com邮箱）
6. 测试上传skill（准备一个包含SKILL.md的文件夹，压缩为ZIP）

## 文件上传格式要求

用户上传的skill文件夹需要：
1. 压缩为ZIP格式
2. ZIP内包含一个文件夹，文件夹内必须有 `SKILL.md` 文件
3. `SKILL.md` 不能为空
4. 可选包含 `icon/` 文件夹存放头像图片
5. 可选包含 `intro.md` 文件作为自我介绍

## 注意事项

1. 密码验证：至少6位，必须包含英文和数字
2. 邮箱验证：必须是 @fanvil.com 后缀
3. 管理员账户不能被删除
4. 每个用户的skill列表是独立的（除了内置skill）
5. 文件上传大小限制可在FastAPI中配置

## 故障排查

如果遇到问题：

1. **数据库错误**：删除 `users.db` 文件重新初始化
2. **登录失败**：检查cookie是否被浏览器阻止
3. **上传失败**：检查skill_lib路径是否正确配置
4. **权限错误**：确认用户是否有管理员权限

## 后续优化建议

1. 使用JWT替代cookie session
2. 添加邮箱验证功能
3. 添加密码重置功能
4. 添加用户头像上传
5. 添加skill预览功能
6. 添加批量导入功能
