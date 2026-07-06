"use client";

import { useEffect, useState } from "react";
import { Bell, Check, CheckCheck, MessageSquareText } from "lucide-react";
import { useRouter } from "next/navigation";
import {
  fetchNotifications, markNotificationRead, markAllNotificationsRead,
} from "@/app/actions";
import type { NotificationItem } from "@/app/actions";

const ENTITY_ROUTES: Record<string, string> = {
  punch_adjustment_request: "/ponto/ajustes",
  punch_excusal: "/ponto/ajustes",
};

export function NotificationPanel() {
  const router = useRouter();
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);

  async function load() {
    const data = await fetchNotifications();
    setItems(data.items);
    setUnread(data.unread);
    setLoading(false);
  }

  useEffect(() => { load(); }, []);

  useEffect(() => {
    const interval = setInterval(load, 30_000);
    return () => clearInterval(interval);
  }, []);

  async function handleRead(id: number) {
    await markNotificationRead(id);
    setItems((prev) => prev.map((n) => n.id === id ? { ...n, read_at: new Date().toISOString() } : n));
    setUnread((prev) => Math.max(0, prev - 1));
  }

  async function handleReadAll() {
    await markAllNotificationsRead();
    setItems((prev) => prev.map((n) => ({ ...n, read_at: n.read_at ?? new Date().toISOString() })));
    setUnread(0);
  }

  function handleOpen(n: NotificationItem) {
    if (!n.read_at) handleRead(n.id);
    const route = n.entity_type ? ENTITY_ROUTES[n.entity_type] : undefined;
    if (route) router.push(route);
  }

  function categoryIcon(category: string) {
    if (category === "create") return <Bell size={16} />;
    if (category === "comment") return <MessageSquareText size={16} />;
    return <Bell size={16} />;
  }

  function timeAgo(dateStr: string) {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "agora";
    if (minutes < 60) return `há ${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `há ${hours}h`;
    const days = Math.floor(hours / 24);
    return `há ${days}d`;
  }

  if (loading) {
    return <div className="notification-list"><p className="notification-empty">Carregando...</p></div>;
  }

  return (
    <div className="notification-list" role="region" aria-label="Notificações" aria-live="polite">
      {unread > 0 && (
        <div className="notification-actions">
          <span aria-live="polite">{unread} não lida{unread > 1 ? "s" : ""}</span>
          <button onClick={handleReadAll} aria-label="Marcar todas como lidas"><CheckCheck size={14} /> Marcar todas</button>
        </div>
      )}
      {items.length === 0 ? (
        <p className="notification-empty">Nenhuma notificação.</p>
      ) : (
        items.map((n) => (
          <article
            key={n.id}
            className={n.read_at ? "notification-item read" : "notification-item"}
            onClick={() => handleOpen(n)}
            role="button"
            tabIndex={0}
            onKeyDown={(e) => { if (e.key === "Enter") handleOpen(n); }}
            aria-label={`${n.title}${n.read_at ? "" : " — não lida"}`}
          >
            <span className={`notification-icon ${n.read_at ? "" : "blue"}`}>
              {categoryIcon(n.category)}
            </span>
            <div className="notification-body">
              <strong>{n.title}</strong>
              {n.body && <p>{n.body.split("\n")[0]}</p>}
              <time>{timeAgo(n.created_at)}</time>
            </div>
            {!n.read_at && (
              <button
                className="notification-read-btn"
                onClick={(e) => { e.stopPropagation(); handleRead(n.id); }}
                aria-label="Marcar como lida"
              >
                <Check size={14} />
              </button>
            )}
          </article>
        ))
      )}
    </div>
  );
}

export function NotificationBadge() {
  const [unread, setUnread] = useState(0);

  useEffect(() => {
    fetchNotifications().then((data) => setUnread(data.unread));
    const interval = setInterval(() => {
      fetchNotifications().then((data) => setUnread(data.unread));
    }, 30_000);
    return () => clearInterval(interval);
  }, []);

  return unread > 0 ? <span className="notification-badge">{unread > 99 ? "99+" : unread}</span> : null;
}
