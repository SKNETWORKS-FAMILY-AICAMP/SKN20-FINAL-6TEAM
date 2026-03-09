import api from './api';
import type { Schedule } from '../types';

export interface ScheduleSaveData {
  company_id: number;
  schedule_name: string;
  start_date: string;
  end_date: string;
  memo: string;
}

export interface AnnounceScheduleData {
  company_id: number;
  announce_id: number;
  schedule_name: string;
  start_date: string;
  end_date: string;
  memo: string;
}

export const fetchSchedules = async (): Promise<Schedule[]> => {
  const response = await api.get('/schedules');
  return response.data;
};

export const createSchedule = async (data: ScheduleSaveData | AnnounceScheduleData): Promise<void> => {
  await api.post('/schedules', data);
};

export const updateSchedule = async (scheduleId: number, data: ScheduleSaveData): Promise<void> => {
  await api.put(`/schedules/${scheduleId}`, data);
};

export const deleteSchedule = async (scheduleId: number): Promise<void> => {
  await api.delete(`/schedules/${scheduleId}`);
};
