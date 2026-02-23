import React from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';
import type { DateClickArg } from '@fullcalendar/interaction';
import type { EventClickArg } from '@fullcalendar/core';
import type { Schedule } from '../../types';

interface CalendarViewProps {
  schedules: Schedule[];
  onDateClick: (dateStr: string) => void;
  onEventClick: (scheduleId: number) => void;
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

export const CalendarView: React.FC<CalendarViewProps> = ({
  schedules,
  onDateClick,
  onEventClick,
}) => {
  const events = schedules.map((schedule, index) => {
    const color = getEventColor(index);
    // FullCalendar end date is exclusive, so add one day
    const endDate = new Date(schedule.end_date);
    endDate.setDate(endDate.getDate() + 1);

    return {
      id: schedule.schedule_id.toString(),
      title: schedule.schedule_name,
      start: schedule.start_date.split('T')[0],
      end: endDate.toISOString().split('T')[0],
      backgroundColor: color.bg,
      borderColor: color.border,
      extendedProps: {
        schedule_id: schedule.schedule_id,
        company_id: schedule.company_id,
        memo: schedule.memo,
      },
    };
  });

  const handleDateClick = (arg: DateClickArg) => {
    onDateClick(arg.dateStr);
  };

  const handleEventClick = (arg: EventClickArg) => {
    const scheduleId = arg.event.extendedProps.schedule_id as number;
    onEventClick(scheduleId);
  };

  return (
    <div className="fc-container bg-white rounded-lg p-4 shadow-sm border">
      <FullCalendar
        plugins={[dayGridPlugin, interactionPlugin]}
        initialView="dayGridMonth"
        locale="ko"
        events={events}
        dateClick={handleDateClick}
        eventClick={handleEventClick}
        headerToolbar={{
          left: 'prev,next today',
          center: 'title',
          right: '',
        }}
        buttonIcons={false}
        buttonText={{
          prev: '<',
          next: '>',
          today: '\uC624\uB298',
        }}
        height="auto"
        dayMaxEvents={3}
        eventDisplay="block"
        displayEventTime={false}
      />
    </div>
  );
};
