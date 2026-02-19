import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Typography, IconButton, Tooltip } from '@material-tailwind/react';
import { TrashIcon, ChatBubbleLeftIcon } from '@heroicons/react/24/outline';
import { useChatStore } from '../../stores/chatStore';
import type { ChatSession } from '../../types';

interface ChatHistoryPanelProps {
  collapsed?: boolean;
}

export const ChatHistoryPanel: React.FC<ChatHistoryPanelProps> = ({ collapsed = false }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const { sessions: allSessions, currentSessionId, switchSession, deleteSession } = useChatStore();

  // Filter out empty sessions (except current session)
  const sessions = allSessions.filter(
    (s) => s.messages.length > 0 || s.id === currentSessionId
  );

  // Don't highlight session when not on chat page
  const isOnChatPage = location.pathname === '/';
  const effectiveCurrentId = isOnChatPage ? currentSessionId : null;

  if (sessions.length === 0) {
    if (collapsed) {
      return <div className="flex-1" />;
    }
    return (
      <div className="px-3 py-4 text-center">
        <Typography variant="small" color="gray" className="text-xs">
          채팅 내역이 없습니다.
        </Typography>
      </div>
    );
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 px-1 overflow-auto">
        {sessions.map((session) => (
          <Tooltip key={session.id} content={session.title} placement="right">
            <button
              className={`p-2 rounded-lg transition-colors ${
                session.id === effectiveCurrentId
                  ? 'bg-blue-50 text-blue-700'
                  : 'hover:bg-gray-100 text-gray-500'
              }`}
              onClick={() => {
                switchSession(session.id);
                navigate('/');
              }}
            >
              <ChatBubbleLeftIcon className="h-5 w-5" />
            </button>
          </Tooltip>
        ))}
      </div>
    );
  }

  const grouped = groupSessionsByDate(sessions);

  return (
    <div className="flex-1 overflow-auto px-1">
      {grouped.map((group) => (
        <div key={group.label} className="mb-2">
          <Typography variant="small" color="gray" className="text-xs px-3 py-1 font-semibold !text-gray-600">
            {group.label}
          </Typography>
          {group.sessions.map((session) => (
            <div
              key={session.id}
              className={`group flex items-center gap-2 px-3 py-2 rounded-lg cursor-pointer transition-colors ${
                session.id === effectiveCurrentId
                  ? 'bg-blue-50 text-blue-700'
                  : 'hover:bg-gray-100 text-gray-700'
              }`}
              onClick={() => {
                switchSession(session.id);
                navigate('/');
              }}
            >
              <ChatBubbleLeftIcon className="h-4 w-4 flex-shrink-0" />
              <Typography variant="small" className="flex-1 truncate text-xs">
                {session.title}
              </Typography>
              <IconButton
                variant="text"
                size="sm"
                className="opacity-0 group-hover:opacity-100 transition-opacity h-6 w-6 min-w-0"
                onClick={(e) => {
                  e.stopPropagation();
                  deleteSession(session.id);
                }}
              >
                <TrashIcon className="h-3.5 w-3.5 text-gray-500" />
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
  if (groups.today.length > 0) result.push({ label: '오늘', sessions: groups.today });
  if (groups.yesterday.length > 0) result.push({ label: '어제', sessions: groups.yesterday });
  if (groups.older.length > 0) result.push({ label: '이전', sessions: groups.older });

  return result;
}
