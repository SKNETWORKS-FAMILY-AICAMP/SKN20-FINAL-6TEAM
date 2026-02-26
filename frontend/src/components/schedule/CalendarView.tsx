import React from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { DateClickArg } from '@fullcalendar/interaction';
import type { EventClickArg, EventInput } from '@fullcalendar/core';
import type { Schedule } from '../../types';

interface CalendarViewProps {
  schedules: Schedule[];
  onDateClick: (dateStr: string) => void;
  onEventClick: (scheduleId: number) => void;
  className?: string;
}

const EVENT_COLORS = [
  { bg: '#3b82f6', border: '#2563eb' },
  { bg: '#10b981', border: '#059669' },
  { bg: '#8b5cf6', border: '#7c3aed' },
  { bg: '#f59e0b', border: '#d97706' },
  { bg: '#ef4444', border: '#dc2626' },
  { bg: '#06b6d4', border: '#0891b2' },
];

function getEventColor(index: number) {
  return EVENT_COLORS[index % EVENT_COLORS.length];
}

const toDatePart = (value: unknown): string | null => {
  if (typeof value !== 'string' || value.trim() === '') {
    return null;
  }

  const datePart = value.includes('T') ? value.split('T')[0] : value;
  const parsed = new Date(datePart);
  if (Number.isNaN(parsed.getTime())) {
    return null;
  }

  return datePart;
};

const toExclusiveEndDate = (datePart: string): string => {
  const endDate = new Date(`${datePart}T00:00:00Z`);
  endDate.setUTCDate(endDate.getUTCDate() + 1);
  return endDate.toISOString().split('T')[0];
};

export const CalendarView: React.FC<CalendarViewProps> = ({
  schedules,
  onDateClick,
  onEventClick,
  className,
}) => {
  const events = schedules.reduce<Array<EventInput>>((acc, schedule, index) => {
    const startDatePart = toDatePart(schedule.start_date);
    const endDatePart = toDatePart(schedule.end_date);

    if (!startDatePart || !endDatePart) {
      return acc;
    }

    const color = getEventColor(index);
    acc.push({
      id: String(schedule.schedule_id),
      title: schedule.schedule_name || '일정',
      start: startDatePart,
      end: toExclusiveEndDate(endDatePart),
      backgroundColor: color.bg,
      borderColor: color.border,
      extendedProps: {
        schedule_id: schedule.schedule_id,
        company_id: schedule.company_id,
        memo: schedule.memo,
      },
    });

    return acc;
  }, []);

  const handleDateClick = (arg: DateClickArg) => {
    onDateClick(arg.dateStr);
  };

  const handleEventClick = (arg: EventClickArg) => {
    const scheduleId = arg.event.extendedProps.schedule_id as number;
    onEventClick(scheduleId);
  };

  return (
    <div className={`fc-container bg-white rounded-lg p-3 shadow-sm border ${className ?? ''}`}>
      <FullCalendar
        plugins={[dayGridPlugin, interactionPlugin]}
        initialView="dayGridMonth"
        locale="ko"
        events={events}
        dateClick={handleDateClick}
        eventClick={handleEventClick}
        headerToolbar={{
          left: '',
          center: 'title',
          right: 'prev,next today',
        }}
        buttonIcons={false}
        buttonText={{
          prev: '<',
          next: '>',
          today: '\uC624\uB298',
        }}
        aspectRatio={1.9}
        height="100%"
        dayMaxEvents={3}
        eventDisplay="block"
        displayEventTime={false}
      />
    </div>
  );
};
