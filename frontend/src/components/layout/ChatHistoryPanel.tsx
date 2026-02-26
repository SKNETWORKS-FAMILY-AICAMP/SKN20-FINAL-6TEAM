import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Typography, IconButton } from '@material-tailwind/react';
import { TrashIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline';
import { useChatStore } from '../../stores/chatStore';
import type { ChatSession } from '../../types';

interface ChatHistoryPanelProps {
  collapsed?: boolean;
  mobile?: boolean;
  onSelectSession?: () => void;
}

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = ({
  collapsed = false,
  mobile = false,
  onSelectSession,
}) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessions: allSessions, currentSessionId, switchSession, deleteSession } = useChatStore();

  // Filter out empty sessions (except current session)
  const sessions = allSessions.filter(
    (session) => session.messages.length > 0 || session.id === currentSessionId
  );

  // Don't highlight session when not on chat page
  const isOnChatPage = location.pathname === '/';
  const effectiveCurrentId = isOnChatPage ? currentSessionId : null;
  const handleSelectSession = (sessionId: string) => {
    switchSession(sessionId);
    navigate('/');
    onSelectSession?.();
  };

  // When sidebar is collapsed, hide accumulated history shortcuts.
  if (collapsed) {
    return <div className="flex-1" />;
  }

  if (sessions.length === 0) {
    return (
      <div className="px-3 py-4 text-center">
        <Typography variant="small" color="gray" className="text-xs !text-gray-700">
          채팅 내역이 없습니다.
        </Typography>
      </div>
    );
  }

  const grouped = groupSessionsByDate(sessions);

  return (
    <div className="flex-1 overflow-auto px-2">
      {grouped.map((group) => (
        <div key={group.label} className="mb-2">
          {group.label && (
            <Typography variant="small" color="gray" className="px-3 py-1 text-xs font-semibold !text-gray-600">
              {group.label}
            </Typography>
          )}
          {group.sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex h-10 w-full cursor-pointer items-center justify-start gap-0 rounded-lg px-2 transition-colors duration-150 ${
                session.id === effectiveCurrentId
                  ? 'bg-blue-50 text-blue-700'
                  : 'hover:bg-gray-100 text-gray-700'
              }`}
              onClick={() => handleSelectSession(session.id)}
            >
              <span className="flex h-10 w-10 items-center justify-center">
                <ChatBubbleLeftIcon className="h-5 w-5 flex-shrink-0" />
              </span>
              <Typography variant="small" className={`flex-1 truncate ${mobile ? 'text-sm' : 'text-xs'}`}>
                {session.title}
              </Typography>
              <IconButton
                variant="text"
                size="sm"
                aria-label="세션 삭제"
                className={`ml-1 min-w-0 transition-opacity ${
                  mobile ? 'h-8 w-8 opacity-100' : 'h-6 w-6 opacity-0 group-hover:opacity-100'
                }`}
                onClick={(event) => {
                  event.stopPropagation();
                  deleteSession(session.id);
                }}
              >
                <TrashIcon className={mobile ? 'h-4 w-4 text-gray-500' : 'h-3.5 w-3.5 text-gray-500'} />
              </IconButton>
            </div>
          ))}
        </div>
      ))}
    </div>
  );
};

interface GroupedSessions {
  label: string;
  sessions: ChatSession[];
}

function groupSessionsByDate(sessions: ChatSession[]): GroupedSessions[] {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 86400000);

  const groups: Record<string, ChatSession[]> = {
    today: [],
    yesterday: [],
    older: [],
  };

  sessions.forEach((session) => {
    const sessionDate = new Date(session.updated_at);
    const sessionDay = new Date(sessionDate.getFullYear(), sessionDate.getMonth(), sessionDate.getDate());

    if (sessionDay.getTime() >= today.getTime()) {
      groups.today.push(session);
    } else if (sessionDay.getTime() >= yesterday.getTime()) {
      groups.yesterday.push(session);
    } else {
      groups.older.push(session);
    }
  });

  const result: GroupedSessions[] = [];
  // Do not show "오늘" header.
  if (groups.today.length > 0) result.push({ label: '', sessions: groups.today });
  if (groups.yesterday.length > 0) result.push({ label: '', sessions: groups.yesterday });
  if (groups.older.length > 0) result.push({ label: '', sessions: groups.older });

  return result;
}
