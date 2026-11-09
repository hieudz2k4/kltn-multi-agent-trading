import { api } from "./base";
import type { Notification } from "./types";

export async function fetchNotifications(params?: {
  type?: Notification["type"];
  read?: boolean;
  priority?: Notification["priority"];
  limit?: number;
  offset?: number;
}): Promise<Notification[]> {
  const { data } = await api.get<Notification[]>("/notifications", { params });
  return data;
}

export async function fetchNotificationUnreadCount(): Promise<number> {
  const { data } = await api.get<{ count: number }>("/notifications/unread-count");
  return Number(data.count || 0);
}

export async function markNotificationRead(notificationId: number): Promise<Notification> {
  const { data } = await api.put<Notification>(`/notifications/${notificationId}/read`);
  return data;
}

export async function markAllNotificationsRead(): Promise<void> {
  await api.put("/notifications/read-all");
}

export async function deleteNotification(notificationId: number): Promise<void> {
  await api.delete(`/notifications/${notificationId}`);
}
